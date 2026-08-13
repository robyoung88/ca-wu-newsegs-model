"""
Minimal implementation of environment servers for placeholding.
"""

from typing import Sequence, overload, override

import pandas as pd

from newsegsmodelframework.core.environment.environment_servers import LOCAL_ENVIRONMENT_MEASURE, WIDER_ENVIRONMENT_MEASURE, NewsegsLocalEnvironment, NewsegsWiderEnvironment, RealArrayLike
from newsegsmodelframework.core.location.location import AspectLocation, Location, RaisedLocation
from newsegsmodelframework.core.timespan.timespan import TimeSpan


class DummyLocalEnv(NewsegsLocalEnvironment):
    _version = '0.0.1'
    _name = 'Dummy local environment'

    @override
    def get_wind_speeds(
        self, 
        location: RaisedLocation | Sequence[RaisedLocation], 
        timespan: TimeSpan
    ) -> RealArrayLike:
        return 0
    
    @override
    def get_wind_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')
    
    @override
    def get_air_density(
        self, 
        location: RaisedLocation | Sequence[RaisedLocation],
        timespan: TimeSpan
    ) -> RealArrayLike:
        return 1.225
    
    @override
    def get_air_density_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')
    
    @override
    def get_horizontal_solar_flux(
        self, 
        location: Location | Sequence[Location], 
        timespan: TimeSpan
    ) -> RealArrayLike:
        return 0
    
    @override
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')
    
    @override
    def get_external_temperature(
        self, 
        location: Location | Sequence[Location],
        timespan: TimeSpan
    ) -> RealArrayLike:
        return 15

    @override
    def get_external_temperature_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')
    
    @override
    def get_solar_flux_on_plane(
        self,
        location: AspectLocation | Sequence[AspectLocation],
        timespan: TimeSpan
    ) -> RealArrayLike:
        return 0
    
    @override
    def get_solar_flux_on_plane_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')
    
    # Annoyingly, have to re-define the overloads to avoid type errors being picked up.
    @overload
    def get_true_datetimes(
        self,
        measure: LOCAL_ENVIRONMENT_MEASURE,
        location: Location,
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        ...
    
    @overload
    def get_true_datetimes(
        self,
        measure: LOCAL_ENVIRONMENT_MEASURE,
        location: Sequence[Location],
        timespan: TimeSpan
    ) -> list[pd.DatetimeIndex]:
        ...

    @override
    def get_true_datetimes(
        self,
        measure: LOCAL_ENVIRONMENT_MEASURE,
        location: Location | Sequence[Location],
        timespan: TimeSpan
    ) -> pd.DatetimeIndex | list[pd.DatetimeIndex]:
        if isinstance(location, Sequence):
            return [self.get_true_datetimes(measure, x, timespan) for x in location]
        return pd.date_range('2020-01-01T00:00:00', '2020-01-01T01:00:00', freq= 'h')
    

class DummyWiderEnv(NewsegsWiderEnvironment):
    _version = '0.0.1'
    _name = 'Dummy wider environment'

    @override
    def get_temperature(self, timespan: TimeSpan) -> RealArrayLike:
        return 15
    
    @override
    def get_temperature_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'h')
    
    @override
    def get_horizontal_solar_flux(
        self, 
        timespan: TimeSpan
    ) -> RealArrayLike:
        return 0

    @override
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'h')

    @override
    def get_true_datetimes(
        self,
        measure: WIDER_ENVIRONMENT_MEASURE,
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        return pd.date_range('2020-01-01T00:00:00', '2020-01-01T01:00:00', freq= 'h')
