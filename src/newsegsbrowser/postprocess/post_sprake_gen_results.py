"""
Convert Sprake model generation results to interface-readable dictionary
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from newsegsmodel.sprakemodel import SprakeModel
from newsegsgeneration.newsegsgeneration import get_generation_meters
from core.timespan import SEASON_NAMES
from newsegsstats.core import assign_year_index, assign_season_index
from newsegsstats import basic_summary_stats
from newsegsstats import categorise_meter
from newsegsstats import time_in_range
from newsegsstats import self_consumption
from newsegsstats import agg_meters_daily
from newsegsstats import locate_timeseries_extrema

SEASON_NAMES_MAP = (
    pd.DataFrame(
        {
            'season_index': np.arange(len(SEASON_NAMES)),
            'season': SEASON_NAMES
        }
    )
    .set_index('season_index')
)

@lru_cache
def gen_results_to_interface_sprake(
    mdl: SprakeModel
) -> dict:
    """
    Extracts the generation results required for the Dash interface to Sprake model.
    """

    # This holds our final returned data structure
    results_to_interface = {}

    genr = mdl.get_generation_result()
    conr = mdl.get_consumption_storage_result()

    gen_data = get_generation_meters(genr)

    rated_capacity_wind = \
        mdl.generation.generator.generators[0].nameplate_capacity
    rated_capacity_pv = \
        mdl.generation.generator.generators[1].nameplate_capacity
    ts = mdl.get_default_timestep()

    gen_data_ann = gen_data.pipe(assign_year_index).query('year_index >= 0')

    gen_dailies = (
        agg_meters_daily.agg_meters_daily(gen_data)
        .query('day_index >= 0')
    )

    results_to_interface['generator_meter_summary'] = (
        gen_data_ann
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    ##### WIND-SPECIFIC RESULTS #####

    results_to_interface['wind_production_categorised'] = (
        gen_data['wind_export']
        .pipe(
            categorise_meter.categorise_meter_by_capacity, 
            rated_capacity=rated_capacity_wind, 
            meter_variable='wind_export'
        )
        .pipe(
            categorise_meter.capacity_categorised_meter_summary,
            rated_capacity=rated_capacity_wind
        )
        .pipe(categorise_meter.capacity_categorised_meter_summary_to_interface)
    )

    results_to_interface['wind_continuous_hours_below_5pc'] = (
        time_in_range.max_continuous_time_in_range(
            gen_data['wind_export'], 
            0, 
            rated_capacity_wind * 0.05 * ts.seconds / 3600.0
        )
    )

    results_to_interface['wind_continuous_hours_above_95pc'] = (
        time_in_range.max_continuous_time_in_range(
            gen_data['wind_export'], 
            rated_capacity_wind * 0.95 * ts.seconds / 3600.0, 
            rated_capacity_wind * 9.99 * ts.seconds / 3600.0
        )
    )

    ##### PV-SPECIFIC RESULTS #####
    max_solar_day = locate_timeseries_extrema.report_ts_max(
        gen_dailies.set_index('datetime')['solar_export']
    )
    min_solar_day = locate_timeseries_extrema.report_ts_min(
        gen_dailies.set_index('datetime')['solar_export']
    )

    results_to_interface['max_solar_day'] = max_solar_day
    results_to_interface['min_solar_day'] = min_solar_day

    results_to_interface['pv_production_categorised'] = (
        gen_dailies['solar_export']
        .pipe(
            categorise_meter.categorise_meter_by_max_record, 
            max_record=max_solar_day['value'], 
            meter_variable='solar_export'
        )
        .pipe(
            categorise_meter.max_record_categorised_meter_summary,
            max_record=max_solar_day['value']
        )
        .pipe(categorise_meter.max_record_categorised_meter_summary_to_interface)
    )

    ##### TOTAL-GENERATION RESULTS #####
    max_generation_day = locate_timeseries_extrema.report_ts_max(
        gen_dailies.set_index('datetime')['generation_export']
    )
    min_generation_day = locate_timeseries_extrema.report_ts_min(
        gen_dailies.set_index('datetime')['generation_export']
    )

    results_to_interface['max_generation_day'] = max_generation_day
    results_to_interface['min_generation_day'] = min_generation_day

    results_to_interface['generation_production_categorised'] = (
        gen_dailies['generation_export']
        .pipe(
            categorise_meter.categorise_meter_by_max_record, 
            max_record=max_generation_day['value'], 
            meter_variable='generation_export'
        )
        .pipe(
            categorise_meter.max_record_categorised_meter_summary,
            max_record=max_generation_day['value']
        )
        .pipe(categorise_meter.max_record_categorised_meter_summary_to_interface)
    )

    ##### SELF-CONSUMPTION RESULTS #####
    sc_raw = self_consumption.to_self_consumption(conr, genr)

    # 1) Stats for horizon
    selfcons_horizon_smry = (
        sc_raw
        .drop(columns=['season_index','year_index'])
        .pipe(self_consumption.selfcons_summary)
        .assign(season='Year')
    )

    # 2) Stats for yearly
    selfcons_byyear_smry = (
        sc_raw
        .drop(columns=['season_index'])
        .pipe(
            self_consumption.selfcons_summary,
            unit_grouping_variables='year_index')
        .assign(season='Year')
    )

    # 3) Stats for seasonal
    # NB - a join on the SEASONS_NAME_MAP is not working
    selfcons_horizon_season_smry = (
        sc_raw
        .drop(columns=['year_index'])
        .pipe(
            self_consumption.selfcons_summary,
            agg_grouping_variables='season_index'
        )
        .reset_index()
        .assign(season = lambda df: SEASON_NAMES_MAP.loc[df['season_index'],'season'].values)
        .drop(columns=[('season_index','')])
        .set_index('generator')
    )

    # 4) Stats for seasonal by year
    selfcons_byyear_season_smry = (
        sc_raw
        .pipe(
            self_consumption.selfcons_summary,
            unit_grouping_variables='year_index',
            agg_grouping_variables='season_index'
        )
        .reset_index()
        .assign(season = lambda df: SEASON_NAMES_MAP.loc[df['season_index'],'season'].values)
        .drop(columns=[('season_index','')])
        .set_index('generator')
    )

    selfcons_horizon_combined = pd.concat([
        selfcons_horizon_smry,
        selfcons_horizon_season_smry
    ])

    selfcons_byyear_combined = pd.concat([
        selfcons_byyear_smry,
        selfcons_byyear_season_smry
    ])

    results_to_interface['self-consumption'] = {}
    results_to_interface['self-consumption']['yearly'] = selfcons_byyear_combined.to_dict(orient='tight')
    results_to_interface['self-consumption']['horizon'] = selfcons_horizon_combined.to_dict(orient='tight')

    return results_to_interface

def gen_results_to_interface_sprake_factory(app):
    """
    Wrap gen_results_to_interface_sprake in a function taking the model hash.

    Allows for caching of the result.
    """
    _app_ref = app

    @lru_cache
    def wrapped_func(mdl_hash):
        mdl = _app_ref.model_from_hash(mdl_hash)
        if mdl is None:
            return None
        return gen_results_to_interface_sprake(mdl)
    
    return wrapped_func
