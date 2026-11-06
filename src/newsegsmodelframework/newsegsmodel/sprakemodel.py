"""The Sprake NewSEGS Energy Model.

An implementation of the model of Dr David Sprake as a `NewsegsModel`, using `SprakeGeneration`, `SprakeGrid` and `SprakeCS`
modules, an in-memory local environment holding the default Sprake weather data and no wider environment.
"""
from __future__ import annotations
from contextlib import contextmanager
from dataclasses import asdict, field
import os
import copy
from typing import Callable, Iterator, cast, override
from functools import singledispatchmethod, lru_cache

import numpy as np
import pandas as pd

from newsegsmodelframework.core.environment.dummy_env_servers import DummyWiderEnv
from newsegsmodelframework.core.location.location import RaisedLocation
from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.core import location as modlocation
from newsegsmodelframework.core.environment import environment_progress, environment_servers
from newsegsmodelframework.core.environment import inmem_env_servers
from newsegsmodelframework.core.timespan.timespan import SECONDS_TO_DAYS
from newsegsmodelframework.core.trackeddata import revision_dataclass
from newsegsmodelframework.newsegsmodel import newsegsmodel
from newsegsmodelframework.newsegsgeneration import newsegsgeneration
from newsegsmodelframework.newsegsgrid import newsegsgrid
from newsegsmodelframework.newsegscs import newsegscs
from newsegsmodelframework.newsegsgeneration import sprakegeneration
from newsegsmodelframework.newsegsgrid import sprakegrid
from newsegsmodelframework.newsegscs import sprakecs

from config import settings
from newsegsmodelframework import STATICDATA
lookup_dir = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

_DEFAULT_TS = pd.Timedelta(hours=1)
_DEFAULT_TIMESPAN = modtimespan.RegTimeSpan(
    pd.Timestamp('2005-01-01T00:00:00', tz='utc'),
    pd.Timestamp('2015-01-01T00:00:00', tz='utc'),
)
_DEFAULT_TIMESPAN.timestep = _DEFAULT_TS

_DEFAULT_LOCATION = modlocation.Location(
    settings.get('SprakeValidationLat'),
    settings.get('SprakeValidationLon')
)

# REVIEW (unreferenced): no references to `_get_sprake_wind_speeds` found in src/, scripts/ or data/.
@lru_cache
def _get_sprake_wind_speeds():
    return(
        pd.read_csv(
            os.path.join(
                lookup_dir,
                'default_wind_speeds.csv'
            )
        )
        .rename(
            columns={
                'datetime': 'timestamp',
                'ws_hub': 'wind_speed'
            }
        )
        .query('hub_height==20')
        .loc[:,['timestamp','wind_speed']]
    )

@lru_cache
def get_sprake_environment_server():
    """The local environment server of the Sprake NewSEGS Energy Model.

    An in-memory server holding the default wind speed, solar flux and temperature series of the Sprake model (cached).

    Returns:
        The server.
    """
    server = inmem_env_servers.InMemoryLocalEnv()

    ### Wind
    wind_data = (
        pd.read_csv(
            os.path.join(
                lookup_dir,
                'default_wind_speeds.csv'
            )
        )
        .rename(
            columns={
                'datetime': 'timestamp',
                'ws_hub': 'wind_speed'
            }
        )
        .query('hub_height==20')
        .loc[:,['timestamp','wind_speed']]
    )
   
    windloc = modlocation.RaisedLocation.from_none()
    windloc.height_agl = sprakegeneration.NOMINAL_WT_HEIGHT
    wind_ts = modtimespan.OffsetRegTimeSpan(
        pd.Timestamp(wind_data['timestamp'].iloc[0], tz='utc'),
        pd.Timestamp(wind_data['timestamp'].iloc[-1], tz='utc')
    )
    wind_ts.timestep = _DEFAULT_TS
    wind_ts.set_offset(wind_ts.start, wind_ts.start)

    server.set_wind_speed(
        wind_data['wind_speed'].values, # pyright: ignore[reportArgumentType]
        windloc,
        wind_ts
    )
    
    ### Solar
    pv_data = (
        pd.read_parquet(
            os.path.join(
                lookup_dir,
                'default_irradiance.parquet'
            )
        )
    )

    pvloc = modlocation.AspectLocation(
        settings.get('SprakeValidationLat'),
        settings.get('SprakeValidationLon'), 
        height_agl = 2
    )
    
    # The PV time series holds mean values at half past the hour.
    # Need to extend back one (first obs carried back)
    pv_ts = modtimespan.OffsetRegTimeSpan(
        pd.Timestamp(pv_data['timestamp'].iloc[0]) - pd.Timedelta(30, 'm'),
        pd.Timestamp(pv_data['timestamp'].iloc[-1]) + pd.Timedelta(30, 'm')
    )
    pv_ts.timestep = _DEFAULT_TS
    pv_ts.set_offset(pv_ts.start, pv_ts.start)

    server.set_horizontal_solar_flux(
        np.append(pv_data['poa_global'].values[0], pv_data['poa_global'].to_numpy()),  # type: ignore
        pvloc,
        pv_ts)
    
    server.set_wind_speed(
        np.append(pv_data['wind_speed'].values[0], pv_data['wind_speed'].to_numpy()), # type: ignore
        pvloc,
        pv_ts
    )

    server.set_external_temperature(
        np.append(pv_data['temp_air'].values[0], pv_data['temp_air'].to_numpy()), # type: ignore
        pvloc,
        pv_ts
    )

    return server

def get_sprake_wider_env_server():
    """The wider environment server of the Sprake NewSEGS Energy Model.

    The Sprake model does not use a wider environment, so a placeholder is used.

    Returns:
        The server.
    """
    return DummyWiderEnv()

def _timespan_to_horizon_years(timespan: modtimespan.TimeSpan) -> int:
    return int(round((timespan.end - timespan.start).total_seconds() * SECONDS_TO_DAYS / 365.25))


@revision_dataclass
class SprakeModelConfig(newsegsmodel.NewsegsModelConfig):
    """Configuration of the Sprake NewSEGS Energy Model.

    Attributes:
        timestep: Timestep of the model.
        run_period: The time span over which the model is run.
    """
    timestep: pd.Timedelta = pd.Timedelta(_DEFAULT_TS)
    run_period: modtimespan.TimeSpan = field(default_factory = lambda: copy.copy(_DEFAULT_TIMESPAN))


class SprakeModel(newsegsmodel.NewsegsModel):
    """Implementation of the model of Dr David Sprake as a NewsegsModel."""
    _name = 'Sprake Energy Model'
    model_type = 'sprake'
    _version = '0.0.1'

    _excluded_attributes = newsegsmodel.NewsegsModel._excluded_attributes.union({
        '_local_environment_server',
        '_wider_environment_server'
    })

    generation = newsegsmodel.NewsegsModelProperty(
        default = sprakegeneration.SprakeGeneration.from_none, 
        oftype = sprakegeneration.SprakeGeneration
    ) # pyright: ignore[reportAssignmentType]

    grid = newsegsmodel.NewsegsModelProperty(
        default = sprakegrid.SprakeGrid.from_none,
        oftype = sprakegrid.SprakeGrid
    ) # pyright: ignore[reportAssignmentType]

    consumption_storage = newsegsmodel.NewsegsModelProperty(
        default = sprakecs.SprakeCS.from_none,
        oftype = sprakecs.SprakeCS
    ) # pyright: ignore[reportAssignmentType]

    _generation_result: sprakegeneration.SprakeGenerationResult
    _grid_result: sprakegrid.SprakeGridResult
    _cs_result: sprakecs.SprakeCSResult

    def _generate_config(self, *args, **kwargs) -> SprakeModelConfig:
        return SprakeModelConfig(*args, **kwargs)
    _config: SprakeModelConfig # pyright: ignore[reportIncompatibleVariableOverride]

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: str | SprakeModel | newsegsgeneration.NewsegsGeneration,
        *args,
        **kwargs,
    ) -> None:
        raise ValueError('First argument must be string or SprakeModel or NewsegsGeneration, is %s', type(dispatch_arg))
    
    # Copy constructor is registered underneath class definition for late-bind
    
    @__init__.register(newsegsgeneration.NewsegsGeneration)
    def _from_NewsegsGeneration(
        self,
        generation: newsegsgeneration.NewsegsGeneration,
        *args, 
        grid: newsegsgrid.NewsegsGrid | None = None,
        consumption_storage: newsegscs.NewsegsCS | None = None,
        local_environment_server: environment_servers.NewsegsLocalEnvironment | str | None = None,
        wider_environment_server: environment_servers.NewsegsWiderEnvironment | str | None = None,
        loc: modlocation.Location | None = None,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)

        if not isinstance(generation, sprakegeneration.SprakeGeneration):
            raise TypeError(f'"generation" must be of type SprakeGeneration, is {type(generation)}')
        self.generation = generation # pyright: ignore[reportIncompatibleMethodOverride]

        if grid:
            if not isinstance(grid, sprakegrid.SprakeGrid):
                raise TypeError(f'"grid2 must be of type SprakeGrid, is {type(grid)}')
            self.grid = grid
        else:
            self.grid = sprakegrid.SprakeGrid.from_none() # pyright: ignore[reportIncompatibleMethodOverride]
        
        if consumption_storage:
            if not isinstance(consumption_storage, sprakecs.SprakeCS):
                raise TypeError(f'"consumption_storage" must be of type SprakeCS, is {type(consumption_storage)}')
            self.consumption_storage = consumption_storage
        else:
            self.consumption_storage = sprakecs.SprakeCS.from_none() # pyright: ignore[reportIncompatibleMethodOverride]

        if loc:
            self.consumption_storage.location = loc

    @__init__.register(str)
    def _from_str(
        self,
        name: str,
        *args,
        **kwargs,
    ) -> None:

        mod_gen = sprakegeneration.SprakeGeneration(sprakegeneration.get_sprake_ned100())
        mod_gen.location = copy.copy(_DEFAULT_LOCATION)
        cast(RaisedLocation, mod_gen.generator.generators[1].location).height_agl = 2.

        # Re-dispatch to SprakeGeneration singledispatchmethod
        self.__init__(mod_gen, name = name, *args, **kwargs)
    
    # We can do the from_none using the _from_str init
    @classmethod
    def from_none(cls):
        """Create a Sprake NewSEGS Energy Model with default modules.

        Returns:
            The model.
        """
        return cls('Sprake Energy Model')

    # REVIEW (unreferenced): no references to `set_run_period` found in src/, scripts/ or data/.
    def set_run_period(self, timespan: modtimespan.TimeSpan) -> None:
        """Set the time span over which the model is run, with the timestep of the model.

        Args:
            timespan: The period of time to run.
        """
        new_timespan = modtimespan.RegTimeSpan(timespan)
        new_timespan.timestep = self.timestep
        self._config.run_period = new_timespan
        
    def get_run_period(self) -> modtimespan.TimeSpan:
        """The time span over which the model is run.

        Returns:
            The time span.
        """
        return self.run_period
    
    @property
    def horizon(self) -> int:
        """Time horizon in years."""
        return _timespan_to_horizon_years(self._config.run_period)
    
    @horizon.setter
    def horizon(self, new_horizon: int):
        ts = modtimespan.RegTimeSpan(self.get_run_period())
        ts.end = ts.start + pd.Timedelta(new_horizon*365, unit='d') 
        while ts.end.day != ts.start.day:
            ts.end = ts.end + pd.Timedelta(1, unit='d')
        ts.timestep = self.get_default_timestep()
        self.run_period = ts

    @property
    def local_env(self) -> environment_servers.NewsegsLocalEnvironment:
        """The local environment server; the default Sprake server is created on first use.
        """
        try:
            return self._local_environment_server
        except AttributeError:
            self._local_environment_server = get_sprake_environment_server()
            return self._local_environment_server
        

    @local_env.setter
    def local_env(
        self,
        local_environment_server: environment_servers.NewsegsLocalEnvironment
    ):
        self._local_environment_server = local_environment_server

    @property
    def wider_env(self) -> environment_servers.NewsegsWiderEnvironment:
        """The wider environment server; the default Sprake server is created on first use.
        """
        try:
            return self._wider_environment_server
        except AttributeError:
            self._wider_environment_server = get_sprake_wider_env_server()
            return self._wider_environment_server
    
    @wider_env.setter
    def wider_env(
        self,
        wider_env_server: environment_servers.NewsegsWiderEnvironment
    ):
        self._wider_environment_server = wider_env_server

    def get_default_timestep(self) -> pd.Timedelta:
        """The timestep of the model.

        Returns:
            The timestep.
        """
        return self.timestep

    @property
    @override
    def location(self) -> modlocation.Location:
        return self.consumption_storage.location
    
    @location.setter
    @override
    def location(self, loc: modlocation.Location):
        """
        The location has no impact on the Sprake model; store with the 
        consumption-storage module.
        """
        self.consumption_storage.location = loc

    def get_generation_result(self) -> NewsegsModuleResult:
        """The result of the last run of the generation module.

        Returns:
            The result.
        """
        return self._generation_result

    def get_grid_result(self) -> NewsegsModuleResult:
        """The result of the last run of the grid module.

        Returns:
            The result.
        """
        return self._grid_result

    # REVIEW (redundant): duplicates `get_consumption_storage_result`, and no references to `get_cs_result` found in src/, scripts/ or data/.
    def get_cs_result(self) -> NewsegsModuleResult:
        """The result of the last run of the consumption and storage module.

        The same as `get_consumption_storage_result`.

        Returns:
            The result.
        """
        return self._cs_result

    def get_consumption_storage_result(self) -> NewsegsModuleResult:
        """The result of the last run of the consumption and storage module.

        Returns:
            The result.
        """
        return self._cs_result

    @override
    def run(
        self,
        run_from = 'start',
        progress_callback: Callable[[float, str], None] | None = None,
    ):
        """Run the modules of the model in order: the grid, the generation, and the consumption
        and storage.

        Args:
            run_from: The last module whose result is current. 'start' runs every module, 'grid'
                runs from the generation module, and 'generation' runs only the consumption and
                storage module.
            progress_callback: Told the progress of the run as each module starts: the fraction
                of the modules run (from 0 to 1), and a message. While a module waits for
                environmental data, such as from a remote service, the message says so (see
                `environment_progress`).

        Returns:
            Hash of the run.
        """
        super().run()

        stages: list[tuple[str, Callable[[], object]]] = []
        if run_from == 'start':
            stages.append(('Running the grid module', self._run_grid))
        if run_from in ('start', 'grid'):
            stages.append(('Running the generation module', self._run_generation))
        if run_from in ('start', 'grid', 'generation'):
            stages.append(('Running the consumption and storage module', self._run_consumption_storage))

        for i, (message, run_module) in enumerate(stages):
            with _module_progress(progress_callback, i / len(stages), message):
                run_module()

        self._last_hash = hash((self.id, str(self.last_run)))
        return self._last_hash

    def _run_grid(self) -> None:
        self._grid_result = cast(
            sprakegrid.SprakeGridResult,
            self.grid.run(self.run_period)
        )

    def _run_generation(self) -> None:
        self._generation_result = cast(
            sprakegeneration.SprakeGenerationResult,
            self.generation.run(self.run_period)
        )

    def _run_consumption_storage(self) -> None:
        self._cs_result = cast(
            sprakecs.SprakeCSResult,
            self.consumption_storage.run(self.run_period)
        )

@contextmanager
def _module_progress(
    progress_callback: Callable[[float, str], None] | None,
    fraction: float,
    message: str,
) -> Iterator[None]:
    """Report the start of a module of a run, and the waits for environmental data within it."""
    if progress_callback is None:
        yield
        return
    progress_callback(fraction, message)
    def on_wait(wait_message: str | None) -> None:
        progress_callback(fraction, message if wait_message is None else f'{message} - {wait_message}')
    with environment_progress.reporting_waits(on_wait):
        yield
    

# SprakeModel copy constructor
@SprakeModel.__init__.register(SprakeModel) # pyright: ignore[reportFunctionMemberAccess]
def _SprakeModel_from_other(
    self,
    other: SprakeModel
) -> None:
    super(SprakeModel, self).__init__()
    self.local_env = other.local_env
    self.wider_env = other.wider_env
    self.name = other.name

    for k in asdict(other._config).keys(): # pyright: ignore[reportArgumentType]
        setattr(self, k, copy.copy(getattr(other, k)))

    self.generation = copy.deepcopy(other.generation)
    self.grid = copy.deepcopy(other.grid)
    self.consumption_storage = copy.deepcopy(other.consumption_storage)
