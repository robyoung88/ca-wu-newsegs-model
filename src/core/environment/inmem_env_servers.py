from __future__ import annotations
# Very simple environment servers that provide in-memory stores for timeseries data which are returned on request

from src.core.environment import NewsegsLocalEnvironment,NewsegsWiderEnvironment
from src.core.location import Location,RaisedLocation,AspectLocation
from src.core.timespan import TimeSpan, RegTimeSpan, OffsetRegTimeSpan
import numpy as np
import numpy.typing as npt
import pandas as pd
from collections.abc import Iterable

def _get_true_datetimes_srs(
    srs: dict,
    timespan: TimeSpan
) -> pd.DatetimeIndex:
    if srs is None:
        return None
    idx = srs['timespan'].get_local_index(timespan)

    return srs['timespan'].to_pandas()[idx]

class InMemoryLocalEnv(NewsegsLocalEnvironment):
    _version = '0.0.1'
    _name = 'Local environment'

    def __init__(self):
        self._wind_series = {}
        self._horizontal_solar_flux_series = {}
        self._external_temperature_series = {}
        self._solar_flux_on_plane_series = {}
    
    # TODO - have a think about if we want to implement a change of timestep
    #        bear in mind that we'd need to interpolate or scarcify the time series
    #        Maybe it'd be better to have a different accessor for interpolated data
    #def change_timestep(self,
    #                    timestep:TimedeltaScalar):
    #    for k in self._wind_series.keys():
    #        self._wind_series[k].timestep = timestep
    #    for k in self._horizontal_solar_flux_series.keys():
    #        self._horizontal_solar_flux_series[k].timestep = timestep
    #    for k in self._external_temperature_series.keys():
    #        self._external_temperature_series[k].timestep = timestep
    #    for k in self._solar_flux_on_plane_series.keys():
    #        for j in self._solar_flux_on_plane_series[k].keys():
    #            self._solar_flux_on_plane_series[j][k].timestep = timestep

    def set_wind_speed(self,
                       wind_speeds:npt.ArrayLike,
                       location:RaisedLocation,
                       timespan:OffsetRegTimeSpan):
        height = location.height_agl
        self._wind_series[height] = {
            'timespan': timespan,
            'timeseries': wind_speeds
        }

    def access_wind_series(self,location:RaisedLocation):
        """
        Providing an accessor just in case we need to tweak the timespan offsets after the fact
        """
        height = location.height_agl
        return self._wind_series.get(height, None)
    
    def get_wind_speeds(self, 
                        location:RaisedLocation|tuple[RaisedLocation, ...]|list[RaisedLocation], 
                        timespan: TimeSpan):
        if (isinstance(location, Iterable)):
            olist = [self.get_wind_speeds(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        srs = self.access_wind_series(location)
        if srs is None:
            return srs
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    def get_wind_timestep(self) -> pd.TimeDelta|None:
        return next(iter(self._wind_series.values())).get('timespan').timestep

    def set_horizontal_solar_flux(self,
                       horizontal_solar_flux:npt.ArrayLike,
                       location:AspectLocation,
                       timespan:OffsetRegTimeSpan):
        # Only store a single series for horizontal solar flux
        self._horizontal_solar_flux_series[None] = {
            'timespan': timespan,
            'timeseries': horizontal_solar_flux
        }

    def access_horizontal_solar_flux_series(self,location:Location):
        return self._horizontal_solar_flux_series[None]

    def get_horizontal_solar_flux(self,
                                  location:Location|tuple[Location, ...]|list[Location],
                                  timespan:TimeSpan):
        if (isinstance(location, Iterable)):
            olist = [self.get_horizontal_solar_flux(x) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        srs = self.access_horizontal_solar_flux_series(location)
        if srs is None:
            return srs
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    def get_horizontal_solar_flux_timestep(self) -> pd.TimeDelta|None:
        return next(iter(self._horizontal_solar_flux_series.values())).get('timespan').timestep

    def set_external_temperature(self,
                       external_temperature:npt.ArrayLike,
                       location:RaisedLocation,
                       timespan:OffsetRegTimeSpan):
        # Only store a single series for temperature
        self._external_temperature_series[None] = {
            'timespan': timespan,
            'timeseries': external_temperature
        }

    def access_external_temperature_series(self,location:Location):
        return self._external_temperature_series[None]

    def get_external_temperature(self,
                                 location:Location|tuple[Location, ...]|list[Location],
                                 timespan:TimeSpan):
        if (isinstance(location, Iterable)):
            olist = [self.get_external_temperature(x) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        srs = self.access_external_temperature_series(location)
        if srs is None:
            return srs
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    def get_external_temperature_timestep(self) -> pd.TimeDelta|None:
        return None

    def set_solar_flux_on_plane(self,
                                solar_flux:npt.ArrayLike,
                                location:AspectLocation,
                                timespan:OffsetRegTimeSpan):
        az = location.azimuth
        pitch = location.pitch
        if not az in self._solar_flux_on_plane_series.keys():
            self._solar_flux_on_plane_series[az] = {}
        
        self._solar_flux_on_plane_series[az][pitch] = {
            'timespan': timespan,
            'timeseries': solar_flux
        }

    def access_solar_flux_on_plane_series(self,location:AspectLocation):
        az = location.azimuth
        pitch = location.pitch
        azd = self._solar_flux_on_plane_series.get(az, None)
        if azd is None:
            return azd
        return azd.get(pitch, None)

    def get_solar_flux_on_plane(self,
                                location:AspectLocation|tuple[AspectLocation, ...]|list[AspectLocation],
                                timespan:TimeSpan):
        if (isinstance(location, Iterable)):
            olist = [self.get_solar_flux_on_plane(x) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        srs = self.access_solar_flux_on_plane_series(location)
        if srs is None:
            return srs
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    def get_solar_flux_on_plane_timestep(self) -> pd.TimeDelta|None:
        return self._horizontal_solar_flux_series.values()[0].get('timespan').timestep

    def get_air_density(self,
                        location:AspectLocation|tuple[AspectLocation, ...]|list[AspectLocation],
                        timespan:TimeSpan):
        return 1.225
    
    def get_air_density_timestep(self) -> pd.TimeDelta|None:
        return None
    
    def get_true_datetimes(
        self,
        measure: Literal[
            'wind_speeds',
            'air_density',
            'horizontal_solar_flux',
            'external_temperature',
            'solar_flux_on_plane'
        ],
        location: Location|tuple[Location, ...]|list[Location],
        timespan: TimeSpan
    ) -> pd.DatetimeIndex|list[pd.DatetimeIndex]:
        if (isinstance(location, Iterable)):
            olist = [self.get_true_datetimes(measure, x, timespan = timespan) for x in location]
            return olist
        
        match measure:
            case 'wind_speeds':
                return _get_true_datetimes_srs(self.access_wind_series(location), timespan)
            case 'horizontal_solar_flux':
                return _get_true_datetimes_srs(self.access_horizontal_solar_flux_series(location), timespan)
            case 'external_temperature':
                return _get_true_datetimes_srs(self.access_external_temperature_series(location), timespan)
            case 'solar_flux_on_plane':
                return _get_true_datetimes_srs(self.access_solar_flux_on_plane_series(location), timespan)
            case _:
                timestep = self.get_wind_timestep()
                ts2 = RegTimeSpan(timespan)
                ts2.timestep = timestep
                return ts2.to_pandas()
    
    def __str__(self) -> str:
        return super().__str__() + "; name: " + self._name

class InMemoryWiderEnv(NewsegsWiderEnvironment):
    _version = '0.0.1'
    _name = 'Wider environment'

    def __init__(self):
        self._temperature_series = None
        self._horizontal_solar_flux_series = None
    
    def set_temperature_series(self,
                               effective_temperatures:npt.ArrayLike,
                               timespan:OffsetRegTimeSpan):
        self._temperature_series = {
            'timespan': timespan,
            'timeseries': effective_temperatures
        }

    def get_temperature(self, timespan:TimeSpan):
        srs = self._temperature_series
        if srs is None:
            return srs
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    def set_horizontal_solar_flux_series(self,
                                         horizontal_solar_flux:npt.ArrayLike,
                                         timespan=OffsetRegTimeSpan):
        self._horizontal_solar_flux_series = {
            'timespan': timespan,
            'timeseries': horizontal_solar_flux
        }
    
    def get_horizontal_solar_flux(self, timespan:TimeSpan):
        srs = self._horizontal_solar_flux_series
        if srs is None:
            return srs
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    def get_true_datetimes(
        self,
        measure: Literal[
            'temperature',
            'horizontal_solar_flux'
        ],
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        
        match measure:
            case 'temperature':
                return _get_true_datetimes_srs(self._temperature_series, timespan)
            case 'horizontal_solar_flux':
                return _get_true_datetimes_srs(self._horizontal_solar_flux_series, timespan)
            case _:
                return None

    def __str__(self) -> str:
        return super().__str__() + "; name: " + self._name
