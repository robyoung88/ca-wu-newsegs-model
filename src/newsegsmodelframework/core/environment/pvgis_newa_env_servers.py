"""An implementation of NewsegsLocalEnvironment using PVGIS and NEWA environmental data.

The data fetched are kept in the persistent environment cache (see `environment_cache`), keyed by
the location (to 3 dp), the time span, the height (to the nearest metre) or plane orientation (to
the nearest degree), and the class name and version of the server. Data are fetched at the
rounded location, height and orientation, so that they do not depend on the order of requests.

Wind speeds and directions come from the same NEWA request, so both are cached when either is
requested. The horizon, from PVGIS, does not depend on time, so is keyed by the location only.

If PVGIS or NEWA does not respond within its timeout (the `PVGIS_TIMEOUT_S` and `NEWA_TIMEOUT_S`
settings), cannot be reached, or refuses the request, an `EnvironmentDataUnavailableError` is
raised; nothing is cached, so the data are fetched again on the next request.
"""

from typing import Callable, Sequence, TypeVar, overload, override

import diskcache
import numpy as np
import pandas as pd
import pvlib
import requests

from config import settings
from newsegsmodelframework.core.environment import environment_cache
from newsegsmodelframework.core.environment.environment_servers import LOCAL_ENVIRONMENT_MEASURE, EnvironmentDataUnavailableError, NewsegsLocalEnvironment, RealArrayLike
from newsegsmodelframework.core.location.location import AspectLocation, Location, RaisedLocation
from newsegsmodelframework.core.timespan.timespan import RegTimeSpan, TimeSpan
from newsegsmodelframework.util import wind_resource_helpers

T = TypeVar('T')

# The columns of the PVGIS data that are served
_PVGIS_COLUMNS = ['timestamp', 'poa_global', 'poa_direct', 'temp_air']

def _fetch_or_raise(service: str, description: str, fetch: Callable[[], T]) -> T:
    """Fetch data from a remote service, raising `EnvironmentDataUnavailableError` if it fails."""
    def unavailable(reason: str) -> EnvironmentDataUnavailableError:
        return EnvironmentDataUnavailableError(f'Unable to obtain {description} from {service}: {reason}')

    try:
        return fetch()
    except requests.Timeout as e:
        raise unavailable('the service did not respond in time') from e
    except requests.ConnectionError as e:
        raise unavailable('the service could not be reached') from e
    except (requests.RequestException, ConnectionError) as e:
        # Includes the errors returned by the services, e.g. for a location they do not cover
        raise unavailable(str(e)) from e

def _pvgis_timeout() -> tuple[float, float]:
    connect, read = settings.get('PVGIS_TIMEOUT_S', [10, 120])
    return float(connect), float(read)

def _fetch_pvgis_data(
    lat: float,
    lon: float,
    start: pd.Timestamp,
    end: pd.Timestamp,
    surface_tilt: float | None = None,
    surface_azimuth: float | None = None,
) -> pd.DataFrame:
    if surface_tilt is None or surface_azimuth is None:
        description = f'solar data for ({lat}, {lon})'
        fetch = lambda: pvlib.iotools.get_pvgis_hourly(
            lat, lon,
            start = start, end = end,
            components = False,
            raddatabase = 'PVGIS-ERA5',
            timeout = _pvgis_timeout()
        )
    else:
        description = f'solar data for ({lat}, {lon}) at pitch {surface_tilt}, azimuth {surface_azimuth}'
        fetch = lambda: pvlib.iotools.get_pvgis_hourly(
            lat, lon,
            start = start, end = end,
            surface_tilt = surface_tilt, surface_azimuth = surface_azimuth,
            components = False,
            raddatabase = 'PVGIS-ERA5',
            timeout = _pvgis_timeout()
        )
    pvg_data, pvg_meta = _fetch_or_raise('PVGIS', description, fetch)

    odata = (
        pvg_data
        .reset_index()
        .rename(
            columns = {
                'time': 'timestamp'
            }
        )
    )
    # Only the served columns are kept, to limit the size of the cache
    return odata.loc[:, [col for col in _PVGIS_COLUMNS if col in odata.columns]]

class HourlyPVGISNEWALocalEnv(NewsegsLocalEnvironment):
    _version = '0.0.1'
    _name = 'Hourly PVGIS-NEWA Local Environment'

    def __init__(self, cache: diskcache.Cache | None = None):
        """
        Args:
            cache: The cache of the data fetched; defaults to the persistent environment cache.
        """
        self._cache = cache

    @property
    def cache(self) -> diskcache.Cache:
        """The cache of the data fetched."""
        if self._cache is None:
            return environment_cache.get_environment_cache()
        return self._cache

    @property
    @override
    def cache_identity(self) -> tuple[str, str]:
        return (type(self).__name__, self._version)

    def _get_pvgis_data(self, location: Location, timespan: TimeSpan) -> pd.DataFrame:
        key = environment_cache.environment_cache_key(self.cache_identity, 'pvgis_hourly', location, timespan)
        lat, lon = environment_cache.round_location(location)
        return environment_cache.get_or_set(
            key,
            lambda: _fetch_pvgis_data(lat, lon, timespan.start, timespan.end - pd.Timedelta(0.5, 'h')),
            cache = self.cache
        )

    @override
    def get_wind_speeds(
        self,
        location: RaisedLocation | Sequence[RaisedLocation],
        timespan: TimeSpan
    ) -> RealArrayLike:
        if isinstance(location, Sequence):
            olist = [self.get_wind_speeds(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        # If height is 2m or less, we should probably return the pvgis wind speed

        speeds_key, _ = self._wind_keys(location, timespan)
        return environment_cache.get_or_set(
            speeds_key, lambda: self._fetch_hourly_wind(location, timespan)[0], cache = self.cache
        )

    @override
    def get_wind_directions(
        self,
        location: RaisedLocation | Sequence[RaisedLocation],
        timespan: TimeSpan
    ) -> RealArrayLike:
        if isinstance(location, Sequence):
            olist = [self.get_wind_directions(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        speeds_key, directions_key = self._wind_keys(location, timespan)
        # Locked on the speeds, as the speeds and directions are fetched together
        return environment_cache.get_or_set(
            directions_key, lambda: self._fetch_hourly_wind(location, timespan)[1],
            cache = self.cache, lock_key = speeds_key
        )

    def _wind_keys(self, location: RaisedLocation, timespan: TimeSpan):
        """Keys of the wind speeds and directions, which are fetched together; both are locked
        on the key of the speeds while fetched."""
        return tuple(
            environment_cache.environment_cache_key(
                self.cache_identity, measure, location, timespan, height = location.height_agl
            )
            for measure in ('wind_speeds', 'wind_directions')
        )

    def _fetch_hourly_wind(self, location: RaisedLocation, timespan: TimeSpan) -> tuple[np.ndarray, np.ndarray]:
        """Fetch the hourly mean wind speeds and directions from NEWA.

        Both are cached, whichever was requested, so that the other is not fetched again.
        """
        lat, lon = environment_cache.round_location(location)
        height = environment_cache.round_height(location.height_agl)

        # use random number generator to resolve tiebreaks when extrapolating
        # wind speeds
        rng = np.random.default_rng(260423)

        wind_resource = _fetch_or_raise(
            'NEWA',
            f'wind speeds for ({lat}, {lon}) at {height} m',
            lambda: wind_resource_helpers.get_wind_at_site(
                lat, lon,
                rng,
                dt_start = timespan.start,
                dt_stop = timespan.end,
                site_heights = [height]
            )
        )

        # Convert to hourly mean; directions are averaged as unit vectors
        wind_direction = np.deg2rad(wind_resource['wind_from_direction_10m'])
        wind_out = (
            wind_resource
            .assign(
                # Shift the times to the mid of their averaging interval
                time = lambda df: df['time'] - pd.Timedelta(15, 'm'),
                #
                datetime = lambda df: df['time'].dt.ceil('h'),
                wd_sin = np.sin(wind_direction),
                wd_cos = np.cos(wind_direction),
            )
            .loc[:, ['datetime', 'hub_height', 'ws_hub', 'wd_sin', 'wd_cos']]
            .groupby(['datetime', 'hub_height'])
            .mean()
        )
        speeds = wind_out['ws_hub'].values
        directions = np.rad2deg(np.arctan2(wind_out['wd_sin'].values, wind_out['wd_cos'].values)) % 360.

        speeds_key, directions_key = self._wind_keys(location, timespan)
        self.cache.set(speeds_key, speeds)
        self.cache.set(directions_key, directions)
        return speeds, directions

    @override
    def get_horizon(self, location: Location) -> pd.Series:
        key = environment_cache.environment_cache_key(self.cache_identity, 'pvgis_horizon', location, None)
        lat, lon = environment_cache.round_location(location)

        def fetch_horizon():
            horizon, _ = _fetch_or_raise(
                'PVGIS',
                f'the horizon of ({lat}, {lon})',
                lambda: pvlib.iotools.get_pvgis_horizon(lat, lon, timeout = _pvgis_timeout())
            )
            return horizon

        return environment_cache.get_or_set(key, fetch_horizon, cache = self.cache)

    @override
    def get_wind_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')

    @override
    def get_horizontal_solar_flux(
        self,
        location: Location | Sequence[Location],
        timespan: TimeSpan
    ) -> RealArrayLike:
        if isinstance(location, Sequence):
            olist = [self.get_horizontal_solar_flux(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        pv_data = self._get_pvgis_data(location, timespan)
        return np.append(pv_data['poa_global'].at[0], pv_data['poa_global'].to_numpy())

    @override
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        return pd.Timedelta(1, 'hour')

    @override
    def get_external_temperature(self, location, timespan):
        if isinstance(location, Sequence):
            olist = [self.get_external_temperature(x, timespan=timespan) for x in location]
            nrow = len(olist)
            return np.asarray(olist).reshape((nrow,-1))

        pv_data = self._get_pvgis_data(location, timespan)
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
        pitch = int(round(location.pitch))
        azimuth = int(round(location.azimuth))
        key = environment_cache.environment_cache_key(
            self.cache_identity, 'pvgis_hourly_on_plane', location, timespan,
            pitch = pitch, azimuth = azimuth
        )
        lat, lon = environment_cache.round_location(location)
        pv_data = environment_cache.get_or_set(
            key,
            lambda: _fetch_pvgis_data(lat, lon, timespan.start, timespan.end, pitch, azimuth),
            cache = self.cache
        )
        return np.append(pv_data['poa_direct'].at[0], pv_data['poa_direct'].to_numpy())

    @override
    def get_solar_flux_on_plane_timestep(self):
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
