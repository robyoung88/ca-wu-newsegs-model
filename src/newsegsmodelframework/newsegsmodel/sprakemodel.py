from __future__ import annotations
from dataclasses import asdict, field
import os
import copy
from typing import cast, override, Any
from functools import singledispatchmethod

import numpy as np
import pandas as pd

from newsegsmodelframework.core.environment.dummy_env_servers import DummyWiderEnv
from newsegsmodelframework.core.location.location import RaisedLocation
from newsegsmodelframework.core.newsegscomponent import ComponentProperty
from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.core import location as modlocation
from newsegsmodelframework.core.environment import environment_servers
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
lookup_dir = settings.get('SprakeDataLoc')

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

def get_sprake_environment_server():
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
                          wind_ts)
    
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
    return DummyWiderEnv()

def _timespan_to_horizon_years(timespan: modtimespan.TimeSpan) -> int:
    return int(round((timespan.end - timespan.start).total_seconds() * SECONDS_TO_DAYS / 365.25))


@revision_dataclass
class SprakeModelConfig(newsegsmodel.NewsegsModelConfig):
    timestep: pd.Timedelta = pd.Timedelta(_DEFAULT_TS)
    run_period: modtimespan.TimeSpan = field(default_factory = lambda: copy.copy(_DEFAULT_TIMESPAN))


class SprakeModel(newsegsmodel.NewsegsModel):
    """Implementation of the model of Dr David Sprake as a NewsegsModel."""
    _name = 'Sprake Energy Model'
    model_type = 'sprake'
    _version = '0.0.1'

    generation = newsegsmodel.NewsegsModelProperty(
        default = sprakegeneration.SprakeGeneration, 
        oftype = sprakegeneration.SprakeGeneration
    ) # pyright: ignore[reportAssignmentType]

    grid = newsegsmodel.NewsegsModelProperty(
        default = sprakegrid.SprakeGrid,
        oftype = sprakegrid.SprakeGrid
    ) # pyright: ignore[reportAssignmentType]

    consumption_storage = newsegsmodel.NewsegsModelProperty(
        default = sprakecs.SprakeCS,
        oftype = sprakecs.SprakeCS
    ) # pyright: ignore[reportAssignmentType]

    _generation_result: sprakegeneration.SprakeGenerationResult
    _grid_result: sprakegrid.SprakeGridResult
    _cs_result: sprakecs.SprakeCSResult

    def _generate_config(self, *args, **kwargs) -> SprakeModelConfig:
        return SprakeModelConfig(*args, **kwargs)

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

        if local_environment_server:
            if isinstance(local_environment_server, str):
                testenv = get_sprake_environment_server()
                if str(testenv) != local_environment_server:
                    raise ValueError('Mismatched local environments')
                self.local_env = testenv
            else:
                self.local_env = local_environment_server
        else:
            self.local_env = get_sprake_environment_server()
        
        if wider_environment_server:
            if isinstance(wider_environment_server, str):
                testenv = get_sprake_wider_env_server()
                if str(testenv) != wider_environment_server:
                    raise ValueError('Mismatched wider environments')
                self.wider_env = testenv
            else:
                self.wider_env = wider_environment_server
        else:
            self._wider_environment_server = get_sprake_wider_env_server()

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
        return cls('Sprake Energy Model')

    def set_run_period(self, timespan: modtimespan.TimeSpan) -> None:
        new_timespan = modtimespan.RegTimeSpan(timespan)
        new_timespan.timestep = self.timestep
        new_horizon = _timespan_to_horizon_years(new_timespan)
        self.run_period = new_timespan
        self._horizon = new_horizon
        
    def get_run_period(self) -> modtimespan.TimeSpan:
        return self.run_period
    
    @property
    def horizon(self) -> int:
        """Time horizon in years."""
        return self._horizon
    
    @horizon.setter
    def horizon(self, new_horizon: int):
        if hasattr(self, '_horizon') and new_horizon == self._horizon:
            return
        ts = modtimespan.RegTimeSpan(self.get_run_period())
        ts.end = ts.start + pd.Timedelta(new_horizon*365, unit='d') 
        while ts.end.day != ts.start.day:
            ts.end = ts.end + pd.Timedelta(1, unit='d')
        ts.timestep = self.get_default_timestep()

        self.run_period = ts
        self._horizon = new_horizon

    @property
    def local_env(self) -> environment_servers.NewsegsLocalEnvironment:
        return self._local_environment_server

    @local_env.setter
    def local_env(
        self,
        local_environment_server: environment_servers.NewsegsLocalEnvironment
    ):
        self._local_environment_server = local_environment_server

    @property
    def wider_env(self) -> environment_servers.NewsegsWiderEnvironment:
        return self._wider_environment_server
    
    @wider_env.setter
    def wider_env(
        self,
        wider_env_server: environment_servers.NewsegsWiderEnvironment
    ):
        self._wider_environment_server = wider_env_server

    def get_default_timestep(self) -> pd.Timedelta:
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
        return self._generation_result

    def get_grid_result(self) -> NewsegsModuleResult:
        return self._grid_result

    def get_cs_result(self) -> NewsegsModuleResult:
        return self._cs_result

    def get_consumption_storage_result(self) -> NewsegsModuleResult:
        return self._cs_result

    @override
    def run(self):
        super().run()
        self._generation_result = cast(
            sprakegeneration.SprakeGenerationResult,
            self.generation.run(self.run_period)
        )
        self._grid_result = cast(
            sprakegrid.SprakeGridResult,
            self.grid.run(self.run_period)
        )

        self._cs_result = cast(
            sprakecs.SprakeCSResult,
            self.consumption_storage.run(self.run_period)
        )
        
        self._last_hash = hash((self.id, str(self.last_run)))
        return self._last_hash
    
    @override
    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        
        odict['local_environment_server'] = str(self._local_environment_server)
        odict['wider_environment_server'] = str(self._wider_environment_server)

        return odict
    
    @classmethod
    @override
    def from_dict(cls: type[SprakeModel], config: dict[str, Any]) -> SprakeModel:
        config = config.copy()
        local_environment_server = config.pop('local_environment_server', None)
        wider_environment_server = config.pop('wider_environment_server', None)

        inst = super().from_dict(config)

        if local_environment_server:
            if isinstance(local_environment_server, str):
                testenv = get_sprake_environment_server()
                if str(testenv) != local_environment_server:
                    raise ValueError('Mismatched local environments')
                inst.local_env = testenv
            else:
                inst.local_env = local_environment_server
        else:
            inst.local_env = get_sprake_environment_server()
        
        if wider_environment_server:
            if isinstance(wider_environment_server, str):
                testenv = get_sprake_wider_env_server()
                if str(testenv) != wider_environment_server:
                    raise ValueError('Mismatched wider environments')
                inst._wider_environment_server = testenv
            else:
                inst.wider_env = wider_environment_server
        else:
            inst._wider_environment_server = get_sprake_wider_env_server()

        inst.grid.model = inst
        inst.generation.model = inst
        inst.consumption_storage.model = inst
        
        return inst

SprakeModel._excluded_attributes = tuple(newsegsmodel.NewsegsModel._excluded_attributes) + (
    '_local_environment_server',
    '_wider_environment_server'
)

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
