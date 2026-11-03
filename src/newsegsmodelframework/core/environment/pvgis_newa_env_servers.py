"""An implementation of NewsegsLocalEnvironment using PVGIS and NEWA environmental data."""

from functools import lru_cache
from typing import Sequence, overload, override

import numpy as np
import pandas as pd
import pvlib

from newsegsmodelframework.core.environment.environment_servers import LOCAL_ENVIRONMENT_MEASURE, NewsegsLocalEnvironment, RealArrayLike
from newsegsmodelframework.core.location.location import AspectLocation, Location, RaisedLocation
from newsegsmodelframework.core.timespan.timespan import RegTimeSpan, TimeSpan
from newsegsmodelframework.util import wind_resource_helpers

def _fetch_pvgis_data(pvgis_key):
    if len(pvgis_key) == 4:
        pvg_data, pvg_meta = pvlib.iotools.get_pvgis_hourly(
            pvgis_key[0], pvgis_key[1],
            start = pvgis_key[2], end = pvgis_key[3],
            components = False,
            raddatabase = 'PVGIS-ERA5' 
        )
    else:
        pvg_data, pvg_meta = pvlib.iotools.get_pvgis_hourly(
            pvgis_key[0], pvgis_key[1],
            start = pvgis_key[2], end = pvgis_key[3],
            surface_tilt = pvgis_key[4], surface_azimuth = pvgis_key[5],
            components = False,
            raddatabase = 'PVGIS-ERA5' 
        )
    location = pvlib.location.Location(pvgis_key[0], pvgis_key[1])
    solarpos = location.get_solarposition(pvg_data.index, method = 'nrel_numba')
    
    odata = (
        pvg_data.join(solarpos)
        .reset_index()
        .rename(
            columns = {
                'time': 'timestamp'
            }
        )
    )
    return odata

class HourlyPVGISNEWALocalEnv(NewsegsLocalEnvironment):
    _version = '0.0.1'
    _name = 'Hourly PVGIS-NEWA Local Environment'

    def __init__(self):
        # TODO: manage these to prevent bloat
        self._ws_cache = {}
        self._pvgis_cache = {}

    @override
    @lru_cache 
    def get_wind_speeds(
        self,
        location: RaisedLocation | Sequence[RaisedLocation],
        timespan: TimeSpan
    ) -> RealArrayLike:
        if isinstance(location, Sequence):
            olist = [self.get_wind_speeds(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        ws_key = (location.lat, location.lon, timespan.start, timespan.end, location.height_agl)

        # If height is 2m or less, we should probably return the pvgis wind speed
        
        if not ws_key in self._ws_cache:
            # use random number generator to resolve tiebreaks when extrapolating
            # wind speeds
            rng = np.random.default_rng(260423)

            self._ws_cache[ws_key] = wind_resource_helpers.get_wind_at_site(
                location.lat, location.lon,
                rng,
                dt_start = timespan.start,
                dt_stop = timespan.end,
                site_heights = [location.height_agl]
            )

        wind_resource = self._ws_cache[ws_key]

        # Convert to hourly mean
        wind_out = (
            wind_resource
            .assign(
                # Shift the times to the mid of their averaging interval
                time = lambda df: df['time'] - pd.Timedelta(15, 'm'),
                # 
                datetime = lambda df: df['time'].dt.ceil('h')
            )
            .loc[:, ['datetime', 'hub_height', 'ws_hub']]
            .groupby(['datetime', 'hub_height'])
            .mean()
            # .reset_index()
            # .rename(
            #     columns={
            #         'datetime': 'timestamp',
            #         'ws_hub': 'wind_speed'
            #     }
            # )
            # .loc[:,['timestamp','wind_speed']]
        )
        return wind_out['ws_hub'].values

    @override
    def get_wind_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')

    @override
    @lru_cache
    def get_horizontal_solar_flux(
        self,
        location: Location | Sequence[Location],
        timespan: TimeSpan
    ) -> RealArrayLike:
        if isinstance(location, Sequence):
            olist = [self.get_horizontal_solar_flux(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        pvgis_key = (location.lat, location.lon, timespan.start, timespan.end - pd.Timedelta(0.5, 'h'))

        if not pvgis_key in self._pvgis_cache:
            self._pvgis_cache[pvgis_key] = _fetch_pvgis_data(pvgis_key)

        pv_data = self._pvgis_cache[pvgis_key]
        return np.append(pv_data['poa_global'].at[0], pv_data['poa_global'].to_numpy())

    @override
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')

    @override
    def get_external_temperature(self, location, timespan):
        if isinstance(location, Sequence):
            olist = [self.get_horizontal_solar_flux(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))
        
        pvgis_key = (location.lat, location.lon, timespan.start, timespan.end - pd.Timedelta(0.5, 'h'))

        if not pvgis_key in self._pvgis_cache:
            self._pvgis_cache[pvgis_key] = _fetch_pvgis_data(pvgis_key)

        pv_data = self._pvgis_cache[pvgis_key]
        return np.append(pv_data['temp_air'].at[0], pv_data['temp_air'].to_numpy())

    @override
    def get_external_temperature_timestep(self):
        return pd.Timedelta(1, 'hour')

    @override
    def get_solar_flux_on_plane(
        self, 
        location: AspectLocation | Sequence[AspectLocation],
        timespan: TimeSpan):
        if (isinstance(location, Sequence)):
            olist = [self.get_solar_flux_on_plane(x, timespan = timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        # For Sprake model, this is not necessary
        pvgis_key = (
            location.lat, location.lon,
            timespan.start, timespan.end,
            location.pitch, location.azimuth,
        )

        if not pvgis_key in self._pvgis_cache:
            self._pvgis_cache[pvgis_key] = _fetch_pvgis_data(pvgis_key)
            
        pv_data = self._pvgis_cache[pvgis_key]
        return np.append(pv_data['poa_direct'].at[0], pv_data['poa_direct'].to_numpy())

    @override
    def solar_flux_on_plane_timestep(self):
        return pd.Timedelta(1, 'hour')

    @override
    def get_air_density(self, location, timespan):
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

        # All data are at the requested times - 
        # offsets need to be applied by the consumer
        timestep = self.get_wind_timestep()
        ts2 = RegTimeSpan(timespan)
        ts2.timestep = timestep
        return ts2.to_pandas()
        
    def __str__(self) -> str:
        return super().__str__() + "; name: " + self._name
