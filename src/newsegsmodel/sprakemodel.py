from __future__ import annotations
import os
import copy
import datetime
from typing import cast, override, Any, Mapping, Sequence
from functools import singledispatchmethod
from functools import lru_cache

import numpy as np
import pandas as pd

from core.environment.dummy_env_servers import DummyWiderEnv
from core.location.location import RaisedLocation
from core.newsegsmoduleresult import NewsegsModuleResult
from core import timespan as modtimespan
from core import location as modlocation
from core.generation import generators
from core.environment import environment_servers
from core.environment import inmem_env_servers
from core.timespan.timespan import SECONDS_TO_DAYS
from newsegsmodel import newsegsmodel
from newsegsgeneration import newsegsgeneration
from newsegsgrid import newsegsgrid
from newsegscs import newsegscs
from newsegsgeneration import sprakegeneration
from newsegsgrid import sprakegrid
from newsegscs import sprakecs

from config import settings
lookup_dir = settings.get('SprakeDataLoc')

# TODO: Fix that changing this prevents construction. Hub height must be somewhere fixed at 10m before location is set.

_DEFAULT_TS = pd.Timedelta(hours=1)

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
        pd.read_csv(
            os.path.join(
                lookup_dir,
                'default_irradiance.csv'
            )
        )
        .rename(
            columns = {
                'time': 'timestamp'
            }
        )
    )

    pvloc = modlocation.AspectLocation(
        settings.get('SprakeValidationLat'),
        settings.get('SprakeValidationLon'), 
        height_agl = 2
    )
    
    #solar_data = pd.read_excel(os.path.join(lookup_dir,
    #                                        'solar_resource.xlsx'),
    #                           sheet_name='global_horizontal_radiation',
    #                           header=0)
    #solarloc = AspectLocation()
    
    # The PV time series holds mean values at half past the hour.
    # Need to extend back one (first obs carried back)
    pv_ts = modtimespan.OffsetRegTimeSpan(
        pd.Timestamp(pv_data['timestamp'].iloc[0], tz='utc') - pd.Timedelta(30, 'm'),
        pd.Timestamp(pv_data['timestamp'].iloc[-1], tz='utc') + pd.Timedelta(30, 'm')
    )
    pv_ts.timestep = _DEFAULT_TS
    pv_ts.set_offset(pv_ts.start, pv_ts.start)

    server.set_horizontal_solar_flux(
        np.append(pv_data['poa_global'].values[0], pv_data['poa_global'].to_numpy()),
        pvloc,
        pv_ts)
    
    server.set_wind_speed(
        np.append(pv_data['wind_speed'].values[0], pv_data['wind_speed'].to_numpy()),
        pvloc,
        pv_ts
    )

    server.set_external_temperature(
        np.append(pv_data['temp_air'].values[0], pv_data['temp_air'].to_numpy()),
        pvloc,
        pv_ts
    )

    return server

def get_sprake_wider_env_server():
    return DummyWiderEnv()

class SprakeModel(newsegsmodel.NewsegsModel):
    _name = 'Sprake Model'
    _version = '0.0.1'

    _generation_result: sprakegeneration.SprakeGenerationResult
    _grid_result: sprakegrid.SprakeGridResult
    _cs_result: sprakecs.SprakeCSResult

    @singledispatchmethod
    def __init__(
        self,
        mod_gen: str | SprakeModel | newsegsgeneration.NewsegsGeneration,
        mod_grid: newsegsgrid.NewsegsGrid | None = None,
        mod_cs: newsegscs.NewsegsCS | None = None,
        local_environment_server: environment_servers.NewsegsLocalEnvironment | None = None,
        timestep: modtimespan.TimedeltaScalar | None = None,
        run_period: modtimespan.TimeSpan | None = None,
        name: str | None = None,
    ) -> None:
        raise ValueError('First argument must be string or SprakeModel or NewsegsGeneration, is %s', type(mod_gen))
    
    # Copy constructor is registered underneath class definition for late-bind
    
    @__init__.register(newsegsgeneration.NewsegsGeneration)
    def _from_NewsegsGeneration(
        self,
        mod_gen: newsegsgeneration.NewsegsGeneration,
        mod_grid: newsegsgrid.NewsegsGrid | None = None,
        mod_cs: newsegscs.NewsegsCS | None = None,
        local_environment_server: environment_servers.NewsegsLocalEnvironment | str| None = None,
        wider_environment_server: environment_servers.NewsegsWiderEnvironment | str | None = None,
        timestep: modtimespan.TimedeltaScalar | None = None,
        run_period: modtimespan.TimeSpan | None = None,
        loc: modlocation.Location | None = None,
        name: str | None = None,
    ) -> None:
        super().__init__()

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

        if not isinstance(mod_gen, sprakegeneration.SprakeGeneration):
            raise TypeError(f'mod_gen must be of type SprakeGeneration, is {type(mod_gen)}')
        self.generation = mod_gen

        if mod_grid:
            if not isinstance(mod_grid, sprakegrid.SprakeGrid):
                raise TypeError(f'mod_grid must be of type SprakeGrid, is {type(mod_grid)}')
            self.grid = mod_grid
        else:
            self.grid = sprakegrid.SprakeGrid.from_none()
        
        if mod_cs:
            if not isinstance(mod_cs, sprakecs.SprakeCS):
                raise TypeError(f'mod_cs must be of type SprakeCS, is {type(mod_cs)}')
            self.consumption_storage = mod_cs
        else:
            self.consumption_storage = sprakecs.SprakeCS.from_none()

        if timestep:
            self._default_timestep = pd.Timedelta(timestep)
        else:
            self._default_timestep = _DEFAULT_TS
        
        if run_period:
            self.set_run_period(modtimespan.RegTimeSpan(run_period))
        else:
            self.set_run_period(modtimespan.RegTimeSpan(
                pd.Timestamp('2005-01-01T00:00:00', tz='utc'),
                pd.Timestamp('2015-01-01T00:00:00', tz='utc')
                        ))
        self._run_period.timestep = self._default_timestep

        if loc:
            self._mod_cs.location = loc

        if name is not None:
            self.name = name

        self._dirty = True

    @__init__.register(str)
    def _from_str(
        self,
        name: str
    ) -> None:

        mod_gen = sprakegeneration.SprakeGeneration(sprakegeneration.get_sprake_ned100())
        mod_gen.set_location(
            modlocation.Location(
                settings.get('SprakeValidationLat'),
                settings.get('SprakeValidationLon')
            )
        )
        cast(RaisedLocation, mod_gen.generator.generators[1].location).height_agl = 2.

        # Re-dispatch to SprakeGeneration singledispatchmethod
        self.__init__(mod_gen, name = name)
    
    # We can do the from_none using the _from_str init
    @classmethod
    def from_none(cls):
        return cls('Sprake Model')

    def set_run_period(self, timespan: modtimespan.TimeSpan) -> None:
        self._run_period = modtimespan.RegTimeSpan(timespan)
        self._run_period.timestep = self._default_timestep
        self._horizon = int(round((self._run_period.end - self._run_period.start).total_seconds() * SECONDS_TO_DAYS / 365.25))
        self._dirty = True

    def get_run_period(self) -> modtimespan.TimeSpan:
        return self._run_period
    
    @property
    def horizon(self) -> int:
        return self._horizon
    
    @horizon.setter
    def horizon(self, new_horizon: int):
        if hasattr(self, '_horizon') and new_horizon == self._horizon:
            return
        ts = modtimespan.RegTimeSpan(self.get_run_period())
        ts.end = ts.start + pd.Timedelta(new_horizon*365, unit='d') 
        while ts.end.day != ts.start.day:
            ts.end = ts.end + pd.Timedelta(1, unit='d')
        ts.timestep = self._default_timestep
        self._run_period = ts
        self._horizon = new_horizon
        self._dirty = True

    @property
    def generation(self) -> sprakegeneration.SprakeGeneration:
        return self._mod_gen
    
    @generation.setter
    def generation(self, generation_module: newsegsgeneration.NewsegsGeneration):
        if not isinstance(generation_module, sprakegeneration.SprakeGeneration):
            raise TypeError(f'Sprake model only compatible with SprakeGeneration - {type(generation_module)} provided')
        self._mod_gen = generation_module
        self._mod_gen.model = self

    @property
    def grid(self) -> sprakegrid.SprakeGrid:
        return self._mod_grid

    @grid.setter
    def grid(self, grid_module: newsegsgrid.NewsegsGrid):
        if not isinstance(grid_module, sprakegrid.SprakeGrid):
            raise TypeError(f'Sprake model only compatible with SprakeGrid - {type(grid_module)} provided')
        self._mod_grid = grid_module
        self._mod_grid.model = self

    @property
    def consumption_storage(self) -> sprakecs.SprakeCS:
        return cast(sprakecs.SprakeCS, self._mod_cs)

    @consumption_storage.setter
    def consumption_storage(self, cs_module: newsegscs.NewsegsCS):
        if not isinstance(cs_module, sprakecs.SprakeCS):
            raise TypeError(f'Sprake model only compatible with SprakeCS - {type(cs_module)} provided')
        self._mod_cs = cs_module
        self._mod_cs.model = self

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
        return self._default_timestep

    @property
    @override
    def location(self) -> modlocation.Location:
        return self._mod_cs.location
    
    @location.setter
    @override
    def location(self, loc: modlocation.Location):
        """
        The location has no impact on the Sprake model; store with the 
        consumption-storage module.
        """
        self._mod_cs.location = loc

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
        self.last_run = datetime.datetime.now()
        self._generation_result = self._mod_gen.run(self._run_period)
        self._grid_result = self._mod_grid.run(self._run_period)
        self._cs_result = self._mod_cs.run(self._run_period)
        self._dirty = False
        
        self._last_hash = hash((self.id, str(self.last_run)))
        return self._last_hash
    
    @override
    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        
        odict['local_environment_server'] = str(self._local_environment_server)
        odict['wider_environment_server'] = str(self._wider_environment_server)

        #odict['mod_gen'] = self._mod_gen.to_dict()
        #odict['mod_grid'] = self._mod_grid.to_dict()
        #odict['mod_cs'] = self._mod_cs.to_dict()

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
        
        return inst

    
    # @classmethod
    # def from_dict(cls, config: dict) -> SprakeModel:
    #     from newsegsgeneration import constructors as genmodconstructors
    #     from newsegsgrid import constructors as gridmodconstructors
    #     from newsegscs import constructors as csmodconstructors

    #     config = copy.copy(config)
    #     config.pop('class', None)

    #     model_version = config.pop('model_version', None)
    #     if model_version != cls._model_version:
    #         raise ValueError('Config has inconsistent model version: %s vs %s', model_version, cls._model_version)
        
    #     config['mod_gen'] = genmodconstructors.generation_module_from_dict(config['mod_gen'])
    #     config['mod_grid'] = gridmodconstructors.grid_module_from_dict(config['mod_grid'])
    #     config['mod_cs'] = csmodconstructors.cs_module_from_dict(config['mod_cs'])

    #     mod_gen = config.pop('mod_gen')

    #     return cls(mod_gen, **config)

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

    self.generation = copy.deepcopy(other.generation)
    self.grid = copy.deepcopy(other.grid)
    self.consumption_storage = copy.deepcopy(other.consumption_storage)

    self._default_timestep = other.get_default_timestep()
    self.set_run_period(other.get_run_period())
    self._dirty = True
