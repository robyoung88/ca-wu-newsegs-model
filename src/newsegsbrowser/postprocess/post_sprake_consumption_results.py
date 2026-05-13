import numpy as np
import pandas as pd

from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegscs import newsegscs
from src.core.timespan import SEASON_NAMES
from src.stats.core import assign_year_index, assign_season_index, assign_day_index
from src.stats.core import assign_delta_hours
from src.stats import basic_summary_stats
from src.stats import self_consumption
from src.stats import locate_timeseries_extrema
from src.stats import agg_meters_daily

from src.util.admd_helpers import get_admd_model_driver
from src.admdspenmw import ASHP_count
from src.admdspenmw.model_config import default_model_config, default_model_inputs, default_model_outputs
from src.stats import locate_timeseries_extrema
from src.newsegscs import elexon_profiles

SEASON_NAMES_MAP = (
    pd.DataFrame(
        {
            'season_index': np.arange(len(SEASON_NAMES)),
            'season': SEASON_NAMES
        }
    )
    .set_index('season_index')
)

_ADMD_CONF = default_model_config.copy()
_ADMD_DR = get_admd_model_driver(_ADMD_CONF)

def calculate_sprake_admd(n_units, n_evs):
    site_details = {
        'N_customers': int(n_units),
        'N_EV_chargers': np.min([n_evs, n_units]),
        'N_EV_and_HP': np.min([n_evs, n_units])
    }

    ASHP_dist = {
        'N_ASHP_5kW': float(0),
        'N_ASHP_8kW': float(n_units),
        'N_ASHP_16kW': float(0)
    }

    ip = default_model_inputs.copy()
    ip.update(site_details)
    ip.update(ASHP_dist)
    
    op = default_model_outputs.copy()
    dr = _ADMD_DR

    o = dr.execute(op, inputs = ip)

    return o.get('ADMD_standard')

def seasonal_and_profile_consumption_summary(grp):
    summary_consumption_year = (
        grp
        .loc[:,['consumption', 'year_index']]
        .pipe(basic_summary_stats.meter_annual_summary)
        .assign(season = 'Year')
        .reset_index(names='statistic')
    )

    summary_consumption_perday = (
        grp
        .loc[:,['consumption', 'day_index']]
        .pipe(basic_summary_stats.meter_perday_summary)
        .rename(columns={'consumption':'per_day'})
        .assign(season = 'Year')
        .reset_index(names='statistic')
    )

    summary_consumption_year_season = (
        grp
        .loc[:,['consumption', 'year_index', 'season']]
        .groupby('season')
        .apply(basic_summary_stats.meter_annual_summary)
        .reset_index(names=['season','statistic'])
    )

    summary_consumption_perday_season = (
        grp
        .loc[:,['consumption', 'day_index', 'season']]
        .groupby('season')
        .apply(basic_summary_stats.meter_perday_summary)
        .reset_index(names=['season','statistic'])
        .rename(columns={'consumption':'per_day'})
    )

    odf = pd.concat([
        pd.merge(summary_consumption_year, summary_consumption_perday, on = ['statistic','season']),
        pd.merge(summary_consumption_year_season, summary_consumption_perday_season, on = ['statistic','season'])
    ]).reset_index(drop=True)

    return odf

def consumption_results_to_interface_sprake(
    mdl: SprakeModel
) -> dict:
    """
    Extracts the consumption results required for the Dash interface to Sprake model.
    """
    # This holds our final returned data structure
    results_to_interface = {}

    conr = mdl.get_consumption_storage_result()
    n_units = mdl.consumption_storage.n_units
    n_evs = mdl.consumption_storage.ev_params.get('n_evs')

    cons_data = (
        newsegscs.get_consumption_meters(conr)
        .assign(
            residential = lambda df: df['appliance_import'] + df['dhw_import'] + df['spaceheat_import'],
            residential_pu = lambda df: df['residential'] / n_units
        )
    )
    cons_data_ann = cons_data.pipe(assign_year_index).query('year_index>=0')
    cons_data_day = (
        agg_meters_daily.agg_meters_daily(cons_data.loc[:,'consumption'])
        .query('day_index >= 0')
    )

    results_to_interface['consumption_meter_summaries'] = (
        cons_data_ann
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    ### Extreme values #####
    results_to_interface['max_consumption_day'] = locate_timeseries_extrema.report_ts_max(
        cons_data_day.set_index('datetime')['consumption']
    )

    results_to_interface['min_consumption_day'] = locate_timeseries_extrema.report_ts_min(
        cons_data_day.set_index('datetime')['consumption']
    )

    #### ADMD calculations #####
    results_to_interface['admd_calculated'] = {'value':calculate_sprake_admd(n_units, n_evs)}

    cons_data_power = (
        cons_data.loc[:,'consumption']
        .pipe(assign_delta_hours)
        .query('delta_hours > 0')
        .assign(power = lambda df: df['consumption'] / df['delta_hours'])
    )

    results_to_interface['admd_observed'] = locate_timeseries_extrema.report_ts_max(cons_data_power['power'])

    ##### Seasonal summaries ####
    cons_data_season = (
        pd.merge(
            cons_data.loc[:,['consumption']],
            (
                elexon_profiles.characterise_dates_elexon(cons_data.index)
                .set_index('datetime')
                .assign(elexon_day = lambda df: df['elexon_day'].shift(1, fill_value='wd'))
            ),
            left_index = True,
            right_index = True
        )
        .loc[:,['consumption','elexon_day']]
        .pipe(assign_year_index)
        .pipe(assign_season_index)
        .pipe(assign_day_index)
        .query('year_index >= 0')
        .assign(season = lambda df: SEASON_NAMES_MAP.loc[df['season_index'],'season'].values)
        .drop(columns='season_index')
    )

    seasonal_data = (
        cons_data_season
        .rename(columns={'elexon_day':'day'})
        .groupby('day')
        [['consumption','year_index','day_index','season']]
        .apply(seasonal_and_profile_consumption_summary)
        .droplevel(1,axis=0)
        .reset_index(drop=False)
    )

    # For per-day data, copy the mean across to the sum so we still get the mean consumption per day
    mn = (
        seasonal_data
        .query('statistic=="mean"')
        .loc[:,['day','season','per_day']]
        .rename(columns={'per_day': 'pd_mean'})
    )
    seasonal_data = (
        pd.merge(
            seasonal_data, mn, on=['day','season']
        )
        .assign(
            per_day = lambda df: np.where(df['statistic']=='sum', df['pd_mean'], df['per_day'])
        )
        .drop(columns=['pd_mean'])
        .set_index('day')
    )

    results_to_interface['seasonal_consumption'] = {
        k: (seasonal_data.loc[k,:].to_dict(orient='tight')) for k in np.unique(seasonal_data.index)
    }

    return results_to_interface
