"""Provides wrappers for New European Wind Atlas API calls."""
from config import settings
import requests
import tempfile
import netCDF4
import xarray as xr
from typing import Literal, get_args


def _request_timeout() -> tuple[float, float]:
    """The (connect, read) timeout (s) of requests to the NEWA API, from the NEWA_TIMEOUT_S setting."""
    connect, read = settings.get('NEWA_TIMEOUT_S', [10, 300])
    return float(connect), float(read)

_MICRO_VARS = Literal['power_dens',
                      'wind_speed',
                      'weib_A_combined',
                      'weib_k_combined',
                      'air_dens',
                      'rix',
                      'elevation']

def get_newa_micro_point(lat, lon, height=50.0, 
                         variables=['power_dens',
                                    'wind_speed',
                                    'weib_A_combined',
                                    'weib_k_combined',
                                    'air_dens',
                                    'rix',
                                    'elevation'],
                         as_nc=False):
    """New European Wind Atlas micro-scale statistics for a single point.

    Args:
        lat: Latitude of the point.
        lon: Longitude of the point.
        height: Height above ground in meters.
        variables: List of micro-scale variables to retrieve.
        as_nc: If True, return the NetCDF response object.

    Returns:
        The API response parsed as an xarray Dataset or raw NetCDF content.
    """
    entry_point = settings.get('NEWAEntryPoint')

    # For this entry point, the variables require no translation
    variables = set(variables)
    assert all(var in get_args(_MICRO_VARS) for var in variables), "One or more variables not recognized for micro-scale data."

    query = (
        entry_point
        + "get-data-point?"
        + "latitude=" + str(lat)
        + "&" + "longitude=" + str(lon)
        + "&" + "height=" + f"{height:0.1f}"
        + '&' + '&'.join(["variable=" + var for var in variables])
    )

    response = requests.get(query, timeout = _request_timeout())

    if response.status_code == 200:
        hd = response.headers
        if hd.get('Content-Type') == 'application/x-netcdf':
            tmp = tempfile.NamedTemporaryFile(suffix='.nc', delete=False)
            tmp.write(response.content)
            tmp.flush()
            tmp.close()
            
            if as_nc:
                nc = netCDF4.Dataset(tmp.name)
                return nc
            else:
                ds = xr.open_dataset(tmp.name)
                return (ds.to_dataframe().reset_index())
        else:
            raise ValueError("Unexpected content type: " + str(hd.get('Content-Type')))
    else:
        raise ConnectionError(f"Error {response.status_code} from NEWA API: {response.text}")

_MESO_VARS_STAT = Literal['power_density',
                          'wind_speed',
                          'WS10',
                          'T2',
                          'T100',
                          'tke50',
                          'rho',
                          'Q100',
                          'Q2',
                          'pbl_height']

_MESO_VARS_STAT_LIST = list(get_args(_MESO_VARS_STAT))

_MESO_VARS_SING = Literal['elevation',
                          'lu_index',
                          'landmask']

_MESO_VARS_SING_LIST = list(get_args(_MESO_VARS_SING))

def get_newa_meso_point(lat, lon, height=50.0,
                        variables=['power_density', # Mean W/m^2 at height; mean, std, min, max
                                   'wind_speed', #  Mean m/s at height; mean, std, min, max
                                   'WS10', # Mean wind speed m/s at 10m; mean, std, min, max
                                   "T2", # Temperature at 2m;mmean, std, min, max
                                   "T100", # Temperature at 100m; mean, std, min, max
                                   "tke50", # Turbulent kinetic energy at 50m; mean, std, min, max
                                   "rho", # Air density kg/m3; mean, std, min, max
                                   "Q100", # Specific humidity at 100m; mean, std, min, max
                                   "Q2", # Specific humidity at 2m; mean, std, min, max
                                   "pbl_height", # Boundary layer height m; mean, std, min, max
                                   'elevation', # Surface elevation m
                                   'lu_index', # Land use index
                                   'landmask'], # Landmask (0=sea, 1=land)
                        as_nc=False):
    """Get New European Wind Atlas (NEWA) meso-scale statistics for a single point.

    Args:
        lat (float): Latitude of the point.
        lon (float): Longitude of the point.
        height (float, optional): Height above ground (m). Defaults to 50.0.
        variables (list[str], optional): Variables to request. Variables in
            the meso statistics set (e.g. 'power_density', 'wind_speed') are
            expanded to their mean/std/min/max forms. Single-value variables
            (e.g. 'elevation') are passed through. Defaults to a preset list.
        as_nc (bool, optional): If True, return raw NetCDF content. Defaults to False.

    Returns:
        pandas.DataFrame or xarray.Dataset or bytes: Depending on response and
            the as_nc flag, returns a pandas DataFrame (default), an xarray
            Dataset, or raw NetCDF bytes.
    """
    entry_point = settings.get('NEWAMesoEntryPoint')

    # For this entry point, variables in _MESO_VARS_STAT require translation to mean, std, min, max
    # and those in _MESO_VARS_SING can be passed directly
    variables = set(variables)
    all_vars = get_args(_MESO_VARS_STAT) + get_args(_MESO_VARS_SING)
    assert all(var in all_vars for var in variables), "One or more variables not recognized for meso-scale data."

    translated_vars = [ (lambda v: [f"{v}_mean", f"{v}_std", f"{v}_min", f"{v}_max"])(var) for var in variables ]
    translated_vars = [ x for xs in translated_vars for x in xs ] # flatten list
    single_vars = [var for var in variables if var in _MESO_VARS_SING]
    if single_vars:
        translated_vars = translated_vars + single_vars

    query = (
        entry_point
        + "get-data-point?"
        + "latitude=" + str(lat)
        + "&" + "longitude=" + str(lon)
        + "&" + "height=" + f"{height:0.1f}"
        + '&' + '&'.join(["variable=" + var for var in translated_vars])
    )

    response = requests.get(query, timeout = _request_timeout())

    if response.status_code == 200:
        hd = response.headers
        if hd.get('Content-Type') == 'application/x-netcdf':
            tmp = tempfile.NamedTemporaryFile(suffix='.nc', delete=False)
            tmp.write(response.content)
            tmp.flush()
            tmp.close()
            
            if as_nc:
                nc = netCDF4.Dataset(tmp.name)
                return nc
            else:
                ds = xr.open_dataset(tmp.name)
                return (ds.to_dataframe().reset_index())
        else:
            raise ValueError("Unexpected content type: " + str(hd.get('Content-Type')))
    else:
        raise ConnectionError(f"Error {response.status_code} from NEWA API: {response.text}")

_MESO_VAR_DESCRIPTIONS = {
    'power_density': 'Mean power density (W/m^2) at requested height (statistical)',
    'wind_speed': 'Mean wind speed (m/s) at requested height (statistical)',
    'WS10': 'Mean wind speed (m/s) at 10m (statistical)',
    'T2': 'Temperature at 2m (deg C) (statistical)',
    'T100': 'Temperature at 100m (deg C) (statistical)',
    'tke50': 'Turbulent kinetic energy at 50m (J/kg) (statistical)',
    'rho': 'Air density (kg/m^3) (statistical)',
    'Q100': 'Specific humidity at 100m (kg/kg) (statistical)',
    'Q2': 'Specific humidity at 2m (kg/kg) (statistical)',
    'pbl_height': 'Planetary  boundary layer height (m) (statistical)',
    'elevation': 'Surface elevation (m) (single value)',
    'lu_index':  'Land use index (single value)',
    'landmask': 'Landmask (0=sea, 1=land) (single value)'
}

_stat_list = "\n         - ".join(_MESO_VARS_STAT_LIST)
_sing_list = "\n         - ".join(_MESO_VARS_SING_LIST)

_detail_lines = []
for v in (_MESO_VARS_STAT_LIST + _MESO_VARS_SING_LIST):
    desc = _MESO_VAR_DESCRIPTIONS.get(v, '')
    _detail_lines.append(f" - {v}: {desc}")


_generated_doc_meso = f"""New European Wind Atlas meso-scale statistics for a single point.

Parameters
- lat, lon, height: location and sampling height (m).
- variables: list of variable name strings to request from the NEWA meso API.
- as_nc: if True, return a netCDF4.Dataset object; otherwise return a pandas DataFrame; default is False

Allowed values (variables):

Statistical variables (each returns summary statistics: mean, std, min, max)
         - {_stat_list}

Single-value variables
         - {_sing_list}

Details:
{chr(10).join(_detail_lines)}

Defaults: the function's default `variables` list requests all of the above.

Notes:
- The function asserts that every requested variable is one of the allowed names.
- Statistical variables are translated by the API into their summary components (mean, std, min, max).
"""

# assign the generated docstring so tooling / intellisense show the up-to-date list
get_newa_meso_point.__doc__ = _generated_doc_meso   

_MESOTS_VARS = Literal[
    'ground_level_altitude',
    'landmask',
    'surface_roughness_length',
    'sensible_heat_flux',
    'latent_heat_flux',
    'planetary_boundary_layer_height',
    'precipitation_amount',
    'air_pressure',
    'air_density',
    'inverse_obukhov_length',
    'sea_ice_area_fraction',
    'shortwave_direct_normal_radiation',
    'surface_temperature',
    'friction_velocity',
    'specific_humidity_2m',
    'air_temperature_2m',
    'wind_from_direction_10m',
    'wind_speed_10m',
    'ice_accretion_standard_cylinder',
    'power_density',
    'humidity_mixing_ratio',
    'air_temperature',
    'turbulent_kinetic_energy',
    'wind_from_direction',
    'wind_speed',
]

_MESOTS_VARS_LIST = list(get_args(_MESOTS_VARS))

_MESOTS_VAR_TRANSLATION = {
    'ground_level_altitude': 'HGT',
    'lu_index': 'LU_INDEX',
    'landmask': 'LANDMASK',
    'surface_roughness_length': 'ZNT',
    'sensible_heat_flux': 'HFX',
    'latent_heat_flux': 'LH',
    'planetary_boundary_layer_height': 'PBLH',
    'precipitation_amount': 'PRECIP',
    'air_pressure': 'PSFC',
    'air_density': 'RHO',
    'inverse_obukhov_length': 'RMOL',
    'sea_ice_area_fraction': 'SEAICE',
    'shortwave_direct_normal_radiation': 'SWDDNI',
    'surface_temperature': 'TSK',
    'friction_velocity':  'UST',
    'specific_humidity_2m': 'Q2',
    'air_temperature_2m': 'T2',
    'wind_from_direction_10m': 'WD10',
    'wind_speed_10m': 'WS10',
    'ice_accretion_standard_cylinder': 'ACCRE_CYL',
    'power_density': 'PD',
    'humidity_mixing_ratio': 'QVAPOR',
    'air_temperature': 'T',
    'turbulent_kinetic_energy': 'TKE',
    'wind_from_direction': 'WD',
    'wind_speed': 'WS'
    }

_MESOTS_VAR_REVERSE_TRANSLATION = {v: k for k, v in _MESOTS_VAR_TRANSLATION.items()}

def get_newa_meso_ts_point(lat, lon, height=50.0,
                           dt_start='1994-12-31T00:00:00',
                           dt_stop='2022-12-31T23:30:00',
                           variables=['power_density',
                                      'wind_speed',
                                      'wind_from_direction'],
                           as_nc=False):
    """New European Wind Atlas meso-scale time series for a single point"""
    entry_point = settings.get('NEWAMesoTSEntryPoint')

    variables = set(variables)
    assert all(var in get_args(_MESOTS_VARS) for var in variables), "One or more variables not recognized for meso-scale time series data."

    # Need to translate these variable names to their NEWA API codes, which 
    # differ in this time-series api to the statistical values
    translated_vars = [ _MESOTS_VAR_TRANSLATION[var] for var in variables ]

    dt_start = dt_start if isinstance(dt_start, str) else dt_start.isoformat()
    dt_stop = dt_stop if isinstance(dt_stop, str) else dt_stop.isoformat()

    dt_start = dt_start.replace(':', '%3A')
    dt_stop = dt_stop.replace(':', '%3A')
    
    query = (
        entry_point
        + "get-data-point?"
        + "latitude=" + str(lat)
        + "&" + "longitude=" + str(lon)
        + "&" + "height=" + f"{height:0.1f}"
        + "&" + "dt_start=" + dt_start
        + "&" + "dt_stop=" + dt_stop
        + '&' + '&'.join(["variable=" + var for var in translated_vars])
    )   

    response = requests.get(query, timeout = _request_timeout())

    if response.status_code == 200:
        hd = response.headers
        if hd.get('Content-Type') == 'application/x-netcdf':
            tmp = tempfile.NamedTemporaryFile(suffix='.nc', delete=False)
            tmp.write(response.content)
            tmp.flush()
            tmp.close()
            
            if as_nc:
                nc = netCDF4.Dataset(tmp.name)
                return nc
            else:
                ds = xr.open_dataset(tmp.name)
                return (ds
                        .to_dataframe()
                        .reset_index()
                        .rename(columns=_MESOTS_VAR_REVERSE_TRANSLATION))
        else:
            raise ValueError("Unexpected content type: " + str(hd.get('Content-Type')))
    else:
        raise ConnectionError(f"Error {response.status_code} from NEWA API: {response.text}")

    #also 'time' variable as minutes since 1989-01-01
    #and we seem to be updating every 30 minutes

_MESOTS_VAR_DESCRIPTIONS = {
    'ground_level_altitude': 'Height of ground above sea level (m)',
    'lu_index': 'Dominant land use category (USGS)',
    'landmask': 'Landmask (0=sea, 1=land)',
    'surface_roughness_length': 'Aerodynamic surface roughness length (m)',
    'sensible_heat_flux': 'Sensible upwards heat flux (W/m^2)',
    'latent_heat_flux': 'Latent upwards heat flux (W/m^2)',
    'planetary_boundary_layer_height': 'Planetary boundary layer height (m)',
    'precipitation_amount': 'Total precipitation for last 30 minutes (kg/m^2)',
    'air_pressure': 'Surface air Pressure (Pa)',
    'air_density': 'Air density (kg/m^3)',
    'inverse_obukhov_length': 'Inverse Obukhov length (1/m)',
    'sea_ice_area_fraction': 'Sea ice area fraction (0-1)',
    'shortwave_direct_normal_radiation': 'Shortwave direct normal radiation (W/m^2)',
    'surface_temperature': 'Skin temperature (K)',
    'friction_velocity':  'Friction velocity (m/s)',
    'specific_humidity_2m': 'Specific humidity at 2m (kg/kg)',
    'air_temperature_2m': 'Air temperature at 2m (K)',
    'wind_from_direction_10m': 'Wind from direction at 10 m (degrees)',
    'wind_speed_10m': 'Wind speed at 10 m (m/s)',
    'ice_accretion_standard_cylinder': 'Ice Accretion on standard cylinder (kg)',
    'power_density': 'Wind power density at height (W/m^2)',
    'humidity_mixing_ratio': 'Humidity mixing ratio (kg/kg)',
    'air_temperature': 'Air temperature at height (K)',
    'turbulent_kinetic_energy': 'Turbulent kinetic energy at height (m^2/s^2)',
    'wind_from_direction': 'Wind from direction at height (degrees)',
    'wind_speed': 'Wind speed at height (m/s)'
}

_mesots_var_list = "\n         - ".join(_MESOTS_VARS_LIST)

_mesots_detail_lines = []
for v in _MESOTS_VARS_LIST:
    desc = _MESOTS_VAR_DESCRIPTIONS.get(v, '')
    _mesots_detail_lines.append(f" - {v}: {desc}")

_generated_doc_mesots = f"""New European Wind Atlas meso-scale time series for a single point.

Parameters
- lat, lon, height: location (WGS84) and sampling height (m).
- dt_start, dt_stop: start and end datetimes for time series. At time of writing, limits are 1994-12-31T00:00:00 to 2022-12-31T23:30:00.
- variables: list of variable name strings to request from the NEWA meso time series API.
- as_nc: if True, return a netCDF4.Dataset object; otherwise return a pandas DataFrame; default is False

Allowed values (variables):

            - {_mesots_var_list}

Details:
{chr(10).join(_mesots_detail_lines)}

Defaults:
['power_density', 'wind_speed', 'wind_from_direction']

Notes:
- The function asserts that every requested variable is one of the allowed names.
- Names returned by "as_NC" are the API-translated versions of the variable names.
- Timestamp resolution is 30 minutes and time is given as minutes since 1989-01-01.
"""

# assign the generated docstring so tooling / intellisense show the up-to-date list
get_newa_meso_ts_point.__doc__ = _generated_doc_mesots
