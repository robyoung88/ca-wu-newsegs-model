import os
import numpy as np
import pandas as pd

from src.newsegsmodel import NewsegsModel

from src.newsegsgeneration import SprakeGeneration
from src.newsegsgrid import SprakeGrid
from src.newsegscs import SprakeCS
from src.core import ABCNewsegsModuleResult
from src.core.environment import NewsegsLocalEnvironment,InMemoryLocalEnv,NewsegsWiderEnvironment
from src.core.location import RaisedLocation, AspectLocation
from src.core.timespan import TimeSpan,RegTimeSpan,OffsetRegTimeSpan
from src.core.generation import WindTurbineElecGenerator

from config import settings
lookup_dir = settings.get('SprakeDataLoc')

_NOMINAL_WT_HEIGHT = 10.0
_DEFAULT_TS = pd.Timedelta(hours=1)

def get_sprake_environment_server():
    server = InMemoryLocalEnv()

    ### Wind
    wind_data = pd.read_excel(os.path.join(lookup_dir,
                                           'wind_resource.xlsx'),
                              sheet_name='Sheet1',
                              header=0)
    windloc = RaisedLocation()
    windloc.height_agl = _NOMINAL_WT_HEIGHT
    wind_ts = OffsetRegTimeSpan()
    wind_ts.start = pd.Timestamp(wind_data['timestamp'].iloc[0], tz='utc')
    wind_ts.end = pd.Timestamp(wind_data['timestamp'].iloc[-1], tz='utc')
    wind_ts.timestep = _DEFAULT_TS
    wind_ts.set_offset(wind_ts.start, wind_ts.start)

    server.set_wind_speed(wind_data['wind_speed'].values,
                          windloc,
                          wind_ts)
    
    ### Solar
    solar_data = pd.read_excel(os.path.join(lookup_dir,
                                            'solar_resource.xlsx'),
                               sheet_name='global_horizontal_radiation',
                               header=0)
    solarloc = AspectLocation()
    solar_ts = OffsetRegTimeSpan()
    solar_ts.start = pd.Timestamp(solar_data['timestamp'].iloc[0],tz='utc')
    solar_ts.end = pd.Timestamp(solar_data['timestamp'].iloc[-1],tz='utc')
    solar_ts.timestep = _DEFAULT_TS
    solar_ts.set_offset(solar_ts.start, solar_ts.start)

    server.set_horizontal_solar_flux(solar_data['horizontal_irradiation_per_hour_kJ_per_sqm'].values,
                                     solarloc,
                                     solar_ts)

    return server

def get_sprake_gamesa_126():
    pcurve = pd.read_excel(os.path.join(lookup_dir,
                                         'wind_power_curve_investigation.xlsx'),
                           sheet_name="gamesa_25_power_curve",
                           header=0)
    tloc = RaisedLocation()
    tloc.height_agl = _NOMINAL_WT_HEIGHT
    turbine = WindTurbineElecGenerator.from_characteristics(
        cut_in=2.0,
        cut_out=21.0,
        rated_power=2500.0,
        swept_area=np.pi*(0.5 * 126)**2,
        hub_height=_NOMINAL_WT_HEIGHT,
        name="Gamesa 126 (Sprake)",
        location = tloc,
        power_curve=pcurve.to_numpy().T
    )

    return turbine

class SprakeModel(NewsegsModel):
    _default_name = "Sprake Model"

    def __init__(self) -> None:
        self._name = self._default_name

        self._local_environment_server = get_sprake_environment_server()
        self._wider_environment_server = None

        self._mod_gen = SprakeGeneration(turbine=get_sprake_gamesa_126())
        self._mod_gen.model = self
        self._mod_gen.generator.generators[0].n_turbines=2.0
        self._mod_gen.generator.generators[1].n_arrays=0.0
        
        self._mod_grid = SprakeGrid()
        self._mod_grid.model = self

        self._mod_cs = SprakeCS()
        self._mod_cs.model = self

        self._default_timestep = _DEFAULT_TS
        self._run_period = RegTimeSpan()
        self._run_period.start = pd.Timestamp('2002-01-01T00:00:00',tz='utc')
        self._run_period.end = pd.Timestamp('2012-01-01T00:00:00', tz='utc')
        self._run_period.timestep = self._default_timestep

        self._generation_result = None
        self._grid_result = None
        self._cs_result = None

    def set_run_period(self, timespan:TimeSpan) -> None:
        self._run_period = RegTimeSpan(timespan)
        self._run_period.timestep = self._default_timestep

    def get_run_period(self) -> TimeSpan:
        return self._run_period

    @property
    def generation(self) -> SprakeGeneration:
        return self._mod_gen
    
    @generation.setter
    def generation(self, generation_module:SprakeGeneration):
        self._mod_gen = generation_module
        self._mod_gen.model = self

    @property
    def grid(self) -> SprakeGrid:
        return self._mod_grid

    @grid.setter
    def grid(self, grid_module:SprakeGrid):
        self._mod_grid = grid_module
        self._mod_grid.model = self

    @property
    def consumption_storage(self) -> SprakeCS:
        return self._mod_cs

    @consumption_storage.setter
    def consumption_storage(self, cs_module:SprakeCS):
        self._mod_cs = cs_module
        self._mod_cs.model = self

    @property
    def local_env(self) -> NewsegsLocalEnvironment:
        return self._local_environment_server

    @local_env.setter
    def local_env(self, local_environment_server:NewsegsLocalEnvironment):
        self._local_environment_server = local_environment_server

    @property
    def wider_env(self):
        return self._wider_environment_server
    
    @wider_env.setter
    def wider_env(self, wider_env_server:NewsegsWiderEnvironment):
        self._wider_environment_server = wider_env_server

    def get_default_timestep(self) -> pd.Timedelta:
        return self._default_timestep

    def get_generation_result(self) -> ABCNewsegsModuleResult|None:
        return self._generation_result

    def get_grid_result(self) -> ABCNewsegsModuleResult|None:
        return self._grid_result

    def get_cs_result(self) -> ABCNewsegsModuleResult|None:
        return self._cs_result

    def get_consumption_storage_result(self):
        return self._cs_result

    def run(self):
        self._generation_result = self._mod_gen.run(self._run_period)
        self._grid_result = self._mod_grid.run(self._run_period)
        self._cs_result = self._mod_cs.run(self._run_period)
