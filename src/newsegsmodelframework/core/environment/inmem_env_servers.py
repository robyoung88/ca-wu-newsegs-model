"""Implementations of NewsegsLocalEnvironment and NewsegsWiderEnvironment holding static data."""
from __future__ import annotations
from typing import Any, Sequence, cast, overload, override

from useful_types import SequenceNotStr
# Very simple environment servers that provide in-memory stores for timeseries data which are returned on request

from newsegsmodelframework.core.environment import NewsegsLocalEnvironment,NewsegsWiderEnvironment
from newsegsmodelframework.core.environment.environment_servers import LOCAL_ENVIRONMENT_MEASURE, WIDER_ENVIRONMENT_MEASURE, RealArrayLike
from newsegsmodelframework.core.location import Location,RaisedLocation,AspectLocation
from newsegsmodelframework.core.timespan import TimeSpan, RegTimeSpan, OffsetRegTimeSpan
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
    """In-memory implementation of local environment data.
    
    Holds static timeseries data for wind speeds, solar flux, external temperature,
    and solar flux on plane. Provides accessor methods to retrieve data for specified
    locations and timespans.
    
    Attributes:
        _version: Version identifier for the environment.
        _name: Human-readable name of the environment.
        _wind_series: Dictionary mapping heights to wind speed timeseries data.
        _horizontal_solar_flux_series: Dictionary storing horizontal solar flux data.
        _external_temperature_series: Dictionary storing external temperature data.
        _solar_flux_on_plane_series: Nested dictionary storing solar flux on plane data
            by azimuth and pitch.
    """
    _version = '0.0.1'
    _name = 'Local environment'

    _wind_series: dict[float, dict[str, Any]]

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
    
    def set_wind_speed(
        self,
        wind_speeds: npt.ArrayLike,
        location: RaisedLocation,
        timespan: OffsetRegTimeSpan
    ):
        """Set wind speed series data for a location.

        Args:
            wind_speeds: Timeseries of wind speeds (m/s).
            location: Raised location for which the timeseries applies.
            timespan: Timespan corresponding to the timeseries.
        """
        height = location.height_agl
        self._wind_series[height] = {
            'timespan': timespan,
            'timeseries': wind_speeds
        }

    def access_wind_series(
        self,
        location: RaisedLocation
    ) -> dict[str, Any] | None:
        """Access wind series data for a given location.
        
        Provides an accessor in case we need to tweak the timespan offsets after the fact.
        
        Args:
            location: The raised location for which to access wind series data.
            
        Returns:
            A dictionary containing wind series data, or None if not available.
        """
        height = location.height_agl
        return self._wind_series.get(height, None)
    
    @override
    def get_wind_speeds(
        self, 
        location: RaisedLocation | Sequence[RaisedLocation], 
        timespan: TimeSpan
    ) -> RealArrayLike:
        if (isinstance(location, Sequence)):
            olist = [self.get_wind_speeds(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        srs = self.access_wind_series(location)
        if srs is None:
            raise ValueError(f'Wind speed data not available for location {str(location)}')
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    @override
    def get_wind_timestep(self) -> pd.Timedelta:
        try:
            return next(iter(self._wind_series.values())).get('timespan').timestep # pyright: ignore[reportOptionalMemberAccess]
        except:
            return pd.Timedelta(1, 'hour')

    def set_horizontal_solar_flux(
        self,
        horizontal_solar_flux:npt.ArrayLike,
        location:AspectLocation,
        timespan:OffsetRegTimeSpan
    ):
        """Set the horizontal solar flux (W/m²) time series.

        NB: Only a single timeseries will be stored and will be returned
        for all locations.

        Args:
            horizontal_solar_flux (npt.ArrayLike): Timeseries of horizontal solar flux (W/m²).
            location (AspectLocation): Location - not used.
            timespan (OffsetRegTimeSpan): Timespan for which the timeseries applies.
        """
        # Only store a single series for horizontal solar flux
        self._horizontal_solar_flux_series[None] = {
            'timespan': timespan,
            'timeseries': horizontal_solar_flux
        }

    def access_horizontal_solar_flux_series(self, location: Location) -> dict[str, Any]:
        """Access horizontal solar flux data for a given location.
        
        Provides an accessor in case we need to tweak the timespan offsets after the fact.
        
        Args:
            location: Unused.
            
        Returns:
            A dictionary containing horizontal solar flux data, or None if not available.
        """
        return self._horizontal_solar_flux_series[None]
    
    @override
    def get_horizontal_solar_flux(
        self,
        location: Location | Sequence[Location],
        timespan:TimeSpan
    ) -> RealArrayLike:
        if (isinstance(location, Sequence)):
            olist = [self.get_horizontal_solar_flux(x, timespan = timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        srs = self.access_horizontal_solar_flux_series(location)
        if srs is None:
            raise ValueError(f'Horizontal solar flux data not available for location {str(location)}')
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    @override
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        try:
            return next(iter(self._horizontal_solar_flux_series.values())).get('timespan').timestep
        except:
            return pd.Timedelta(1, 'hour')

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

    @override
    def get_external_temperature(
        self,
        location: Location | Sequence[Location],
        timespan:TimeSpan
    ) -> RealArrayLike:
        if (isinstance(location, Iterable)):
            olist = [self.get_external_temperature(x, timespan = timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        srs = self.access_external_temperature_series(location)
        if srs is None:
            raise ValueError(f'Temperature data not available for location {str(location)}')
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    @override
    def get_external_temperature_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(100*365, 'days')

    def set_solar_flux_on_plane(
        self,
        solar_flux: npt.ArrayLike,
        location: AspectLocation,
        timespan: OffsetRegTimeSpan
    ):
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

    @override
    def get_solar_flux_on_plane(
        self,
        location: AspectLocation | Sequence[AspectLocation],
        timespan:TimeSpan
    ) -> RealArrayLike:
        if (isinstance(location, Iterable)):
            olist = [self.get_solar_flux_on_plane(x, timespan = timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        srs = self.access_solar_flux_on_plane_series(location)
        if srs is None:
            raise ValueError(f'Solar flux data not available for location {str(location)}')
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    @override
    def get_solar_flux_on_plane_timestep(self) -> pd.Timedelta:
        try:
            return next(iter(self._solar_flux_on_plane_series.values())).get('timespan').timestep
        except:
            return pd.Timedelta(1, 'h')

    @override
    def get_air_density(
        self,
        location: RaisedLocation | Sequence[RaisedLocation],
        timespan:TimeSpan
    ) -> RealArrayLike:
        return 1.225
    
    @override
    def get_air_density_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(100*365, 'days')
    
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
        if (isinstance(location, Sequence)):
            olist = [
                self.get_true_datetimes(measure, x, timespan = timespan)
                for x in location
            ]
            return olist
        
        match measure:
            case 'wind_speeds':
                srs = self.access_wind_series(cast(RaisedLocation, location))
                if srs is None:
                    raise ValueError(f'Wind series has not been set for location {str(location)}')
                return _get_true_datetimes_srs(srs, timespan)
            case 'horizontal_solar_flux':
                return _get_true_datetimes_srs(self.access_horizontal_solar_flux_series(location), timespan)
            case 'external_temperature':
                return _get_true_datetimes_srs(self.access_external_temperature_series(location), timespan)
            case 'solar_flux_on_plane':
                srs = self.access_solar_flux_on_plane_series(cast(AspectLocation, location))
                if srs is None:
                    raise ValueError(f'Solar flux on plane has not been set for location {str(location)}')
                return _get_true_datetimes_srs(srs, timespan)
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
    
    def set_temperature_series(
        self,
        effective_temperatures: npt.ArrayLike,
        timespan: OffsetRegTimeSpan
    ):
        self._temperature_series = {
            'timespan': timespan,
            'timeseries': effective_temperatures
        }

    @override
    def get_temperature(self, timespan: TimeSpan) -> RealArrayLike:
        srs = self._temperature_series
        if srs is None:
            raise AttributeError('temperature series has not been set')
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    @override
    def get_temperature_timestep(self) -> pd.Timedelta:
        srs = self._temperature_series
        if srs is None:
            return pd.Timedelta(1, 'h')
        return srs['timespan'].timestep

    def set_horizontal_solar_flux_series(
        self,
        horizontal_solar_flux: npt.ArrayLike,
        timespan = OffsetRegTimeSpan
    ):
        self._horizontal_solar_flux_series = {
            'timespan': timespan,
            'timeseries': horizontal_solar_flux
        }
    
    @override
    def get_horizontal_solar_flux(self, timespan: TimeSpan) -> RealArrayLike:
        srs = self._horizontal_solar_flux_series
        if srs is None:
            raise AttributeError('horizontal solar flux series has not been set')
        idxs = srs['timespan'].get_local_index(timespan)
        return(srs['timeseries'][idxs])

    @override
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        srs = self._horizontal_solar_flux_series
        if srs is None:
            return pd.Timedelta(1, 'h')
        return srs['timespan'].timestep

    @override
    def get_true_datetimes(
        self,
        measure: WIDER_ENVIRONMENT_MEASURE,
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        
        match measure:
            case 'temperature':
                if self._temperature_series is None:
                    raise AttributeError('temperature series has not been set')
                return _get_true_datetimes_srs(self._temperature_series, timespan)
            case 'horizontal_solar_flux':
                if self._horizontal_solar_flux_series is None:
                    raise AttributeError('horizontal solar fluz series has not been set')
                return _get_true_datetimes_srs(self._horizontal_solar_flux_series, timespan)
            case _:
                return None

    def __str__(self) -> str:
        return super().__str__() + "; name: " + self._name
