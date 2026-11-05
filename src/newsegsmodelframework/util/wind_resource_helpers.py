"""Helpers for wind resource assessment from the New European Wind Atlas: wind speeds at a site and heights, and
compass point categories.

The wind rose, energy rose and wind speed profile plots are in `newsegsmodelutils.plots.wind_resource`.
"""
import datetime
import itertools
from typing import Any, Literal, Sequence, overload

import numpy as np
import pandas as pd

from newa import get_newa_micro_point, get_newa_meso_ts_point
from scipy.stats import weibull_min

_bearing_names = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW']
_bearing_max_angle = np.arange(len(_bearing_names)) * 360.0 / len(_bearing_names) + 0.5 * (360.0 / len(_bearing_names))
BEARING_DICT = dict(zip(_bearing_names,_bearing_max_angle))
_WS_BINS = [0,1,2,3,4,5,10,15,20,25,30,50]

BEARING_POLAR_ANGLES = (pd.DataFrame.from_dict(BEARING_DICT,
                                               orient='index',
                                               columns=['max_angle'])
                        .assign(theta=lambda df:2.*np.pi*(df['max_angle']-df['max_angle'].min())/360.0)
                        .reset_index()
                        .rename(columns={'index':'bearing_cat'})
                        .loc[:,['bearing_cat','theta']]
                        )

#wind_res_dir = settings.get('SiteResourceWindDirectory')

# 15 m height for 6kW (e.g. SD6) or 12 kW (e.g. SD12) turbine
# 35 m height for 50 - 250 kW (e.g. Norvento nED 100)
EVAL_HEIGHTS = [15, 35]

# REVIEW (unreferenced): no references to `get_cp` found in src/, scripts/ or data/.
def get_cp(file_name):
    """Read a power coefficient curve and return a function interpolating it.

    The file is an Excel file with `wind_speed` and `coeff_power` columns. The function gives zero outside the range of the curve.

    Args:
        file_name: Path of the file.

    Returns:
        Function of wind speed returning the power coefficient.
    """
    cp_file = pd.read_excel(file_name)
    def interpolant(x):
        return np.interp(x, cp_file['wind_speed'], cp_file['coeff_power'], left=0.0, right=0.0)
    return interpolant

#_cp_small = get_cp(os.path.join('data','power-curve-proven-6.xlsx'))
#_cp_med = get_cp(os.path.join('data','power-curve-ned-100.xlsx'))

#CPS = (_cp_small, _cp_med)

def bearing_to_category(bearings,
                        categories=BEARING_DICT,
                        offset=None):
    """Categorise bearings into compass points.

    Args:
        bearings: Bearings in degrees.
        categories: Dictionary of the maximum angle of each category.
        offset: Offset (degrees) of the categories; by default half a category width.

    Returns:
        Ordered categorical of the compass points.
    """
    if offset is None:
        offset = (360.0 / len(categories)) / 2.0
    
    b = (bearings + 360.0 + offset)%360.0 
    o = np.zeros_like(b, dtype=str)
    for cat, max_angle in reversed(categories.items()):
        ma = max_angle + offset
        o = np.where(b < ma, cat, o)
    o = pd.Categorical(o,categories=list(categories.keys()),ordered=True)
    return o

def expand_grid(data_dict):
    """Dataframe of all combinations of the values in a dictionary.

    Args:
        data_dict: Dictionary of the values of each column.

    Returns:
        The dataframe.
    """
    rows = itertools.product(*data_dict.values())
    return pd.DataFrame.from_records(rows, columns=data_dict.keys())

def get_alpha_distribution(newa_meso_data):
    """Get the value of the Prandtl log-law scaling parameter from NEWA mesoscale data"""
    z_ref = newa_meso_data.height.unique()
    assert len(z_ref) == 1, "Please provide only a single wind speed height in NEWA data"
    z_ref = z_ref[0]

    # Remove unstable atmospheres, leaving neutral and stable
    idf = newa_meso_data.query('inverse_obukhov_length >= 0.0')

    # Categorise wind speed and direction
    idf = (
        idf
        .assign(
            wd_10_cat=lambda df: bearing_to_category(df['wind_from_direction_10m']),
            ws_10_cat=lambda df: pd.cut(df['wind_speed_10m'], _WS_BINS)
        )
    )

    # Calculate alpha
    denom = np.log(z_ref) - np.log(10.0)
    idf = (
        idf
        .assign(
            alpha = lambda df: (np.log(df['wind_speed']) - np.log(df['wind_speed_10m']))/denom
        )
    )
    
    o1 = idf.groupby(['wd_10_cat','ws_10_cat'])['alpha'].mean()

    all_cats = expand_grid({'wd_10_cat':BEARING_DICT.keys(),
                            'ws_10_cat':pd.cut([], _WS_BINS).categories})
    o2 = (
        pd.merge(
            all_cats,
            o1,
            on=['wd_10_cat','ws_10_cat'],
            how='left'
        )
        .ffill()
        .set_index(['wd_10_cat','ws_10_cat'])
    )

    return o2

def get_alphas(wd_10, ws_10, alpha_dist):
    """The wind shear exponent for each wind direction and speed.

    Looked up from the distribution by compass point and wind speed bin.

    Args:
        wd_10: Wind directions at 10 m.
        ws_10: Wind speeds at 10 m.
        alpha_dist: Distribution of the shear exponent by wind direction and speed bin.

    Returns:
        Array of shear exponents.
    """
    idf = (
        pd.DataFrame({
            'wd_10': wd_10,
            'ws_10': ws_10
            })
        .assign(
            wd_10_cat=lambda df: bearing_to_category(df['wd_10']),
            ws_10_cat=lambda df: pd.cut(df['ws_10'], _WS_BINS)
        )
    )

    return (idf.set_index(['wd_10_cat','ws_10_cat']).join(alpha_dist)['alpha'].values)

NewaDatetime = str | datetime.datetime | pd.Timestamp
"""A datetime accepted by `get_wind_at_site`: a string, `datetime.datetime` or `pd.Timestamp`."""

_NEWA_DATETIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

def to_newa_datetime_string(dt: NewaDatetime) -> str:
    """Format a datetime as the New European Wind Atlas API requires, e.g. `'2005-01-01T00:00:00'`.

    The API takes UTC times without a timezone, to the second, so a timezone-aware datetime is converted to UTC
    and a naive one is taken to be UTC already.

    Args:
        dt: The datetime; a string is parsed by `pd.Timestamp`.

    Returns:
        The formatted datetime.
    """
    ts = pd.Timestamp(dt)
    if ts.tz is not None:
        ts = ts.tz_convert('UTC').tz_localize(None)
    return ts.strftime(_NEWA_DATETIME_FORMAT)

@overload
def get_wind_at_site(
    lat: float, lon: float,
    rng: np.random.Generator,
    meso_reference_height: float = ...,
    micro_reference_height: float = ...,
    dt_start: NewaDatetime = ...,
    dt_stop: NewaDatetime = ...,
    site_heights: Sequence[float] = ...,
    return_working: Literal[False] = ...
) -> pd.DataFrame: ...

@overload
def get_wind_at_site(
    lat: float, lon: float,
    rng: np.random.Generator,
    meso_reference_height: float = ...,
    micro_reference_height: float = ...,
    dt_start: NewaDatetime = ...,
    dt_stop: NewaDatetime = ...,
    site_heights: Sequence[float] = ...,
    *,
    return_working: Literal[True]
) -> dict[str, Any]: ...

def get_wind_at_site(
    lat: float, lon: float,
    rng: np.random.Generator,
    meso_reference_height: float = 50,
    micro_reference_height: float = 50,
    dt_start: NewaDatetime = '2005-01-01T00:00:00',
    dt_stop: NewaDatetime = '2022-12-31T23:30:00',
    site_heights: Sequence[float] = EVAL_HEIGHTS,
    #site_cps = CPS,
    return_working: bool = False
) -> pd.DataFrame | dict[str, Any]:

    """Wind speeds at a site, at heights, from the New European Wind Atlas.

    Takes the mesoscale wind speed series at the reference height and maps its Weibull distribution onto the microscale Weibull distribution of the site, then scales the result to each site height by the power law with a shear exponent which depends upon the wind direction and speed.

    Args:
        lat: Latitude (degrees).
        lon: Longitude (degrees).
        rng: Random number generator, which resolves ties when the wind speeds are sorted.
        meso_reference_height: Height (m) of the mesoscale data used as reference.
        micro_reference_height: Height (m) of the microscale data used as reference.
        dt_start: Start of the period; see `to_newa_datetime_string`.
        dt_stop: End of the period; see `to_newa_datetime_string`.
        site_heights: Heights (m) at which to give the wind speeds.
        return_working: Return the intermediate data as well.

    Returns:
        The wind speed series at each height; with `return_working`, a dictionary which also holds the intermediate data.
    """
    meso_data = get_newa_meso_ts_point(lat, lon,
                                       height=meso_reference_height,
                                       dt_start=to_newa_datetime_string(dt_start),
                                       dt_stop=to_newa_datetime_string(dt_stop),
                                       variables=['wind_speed',
                                                  'wind_from_direction_10m',
                                                  'wind_speed_10m',
                                                  'inverse_obukhov_length'])
    
    alpha_dist = get_alpha_distribution(meso_data)

    micro_data = get_newa_micro_point(lat, lon,
                                      height=micro_reference_height,
                                      variables=['weib_A_combined',
                                                 'weib_k_combined',
                                                 'air_dens'])
    
    rho = micro_data['air_dens'].values[0]

    # Our reference wind time series is the mesoscale at ref height.
    ref_ts = meso_data.loc[:,['time','wind_speed','wind_speed_10m','wind_from_direction_10m']]

    # First, let's sort the wind speeds, as will need to do so regardless
    ref_ts = (
        ref_ts
        .sample(frac=1,random_state=rng)
        .sort_values('wind_speed')
    )

    # Determine Weibull parameters for this ts
    # Now get the reference Weibull parameters
    ws_ref_wb_pars = weibull_min.fit(ref_ts['wind_speed'],floc=0.0)
    ws_ref_wb_pars = dict(zip(('c','loc','scale'), ws_ref_wb_pars))
    # Based on this, we can find the empirical maximum value of the CDF achieved
    max_cdf = weibull_min.cdf(x=ref_ts['wind_speed'].max(),**ws_ref_wb_pars)

    # Generate the wind speeds across the probability distribution at micro reference height
    ws_site_ref = weibull_min.ppf(q=np.linspace(0,max_cdf,len(ref_ts)),
                                  c=micro_data['weib_k_combined'].values[0],
                                  loc=0.0,
                                  scale=micro_data['weib_A_combined'].values[0])
    
    # Augment ref ts with the local 50 m wind speed and the alpha parameter
    ref_ts = (
        ref_ts
        .assign(
            ws_ref_local=ws_site_ref,
            alpha=lambda df:get_alphas(df['wind_from_direction_10m'].values, df['wind_speed_10m'].values, alpha_dist)
        )
    )

    # Extrapolation function
    def get_wind_speed_at_height(z):
        return (
            ref_ts
            .copy()
            .assign(
                ws_hub = lambda df: df['ws_ref_local'] * (z / micro_reference_height) ** df['alpha'],
            )
            .sort_values('time')
            .assign(hub_height=z)
    )

    #def get_specific_wind_power_at_height(z, cp_func):
    #    return (
    #        ref_ts
    #        .copy()
    #        .assign(
    #            ws_hub = lambda df: df['ws_ref_local'] * (z / micro_reference_height) ** df['alpha'],
    #            sp_power = lambda df: 0.001 * 0.5 * rho * cp_func(df['ws_hub']) * df['ws_hub']**3
    #        )
    #        .sort_values('time')
    #        .assign(hub_height=z)
    #)

    olist = []
    for z in site_heights:
        olist.append(get_wind_speed_at_height(z))


    odata = pd.concat(olist)

    if return_working:
        return {
            'site_ts': odata,
            'ref_ts': ref_ts,
            'alpha_dist': alpha_dist,
            'micro_weibull_pars': micro_data,
            'meso_weibull_pars': ws_ref_wb_pars
        }
    else :
        return odata
