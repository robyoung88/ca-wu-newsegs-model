# A Dash Leaflet map browser for manipulating the Sprake Model
import os
import copy
import json
import uuid
import datetime
from collections.abc import Mapping
from functools import partial
from typing import Tuple
#from typing import Literal

from dash import Dash, html, Input, Output, dcc, State, ALL, no_update, ctx
from dash import clientside_callback, ClientsideFunction
import dash_bootstrap_components as dbc
import dash_daq as daq
from dash_extensions import Purify

# At the moment, use a diskcache cache for transferring models 
# regardless of background callback manager
import diskcache
from config import settings
cache = diskcache.Cache(settings.get('DiskcacheCache', './cache'))

# Manager for background callbacks
if 'REDIS_URL' in os.environ:
    # Use Redis & Celery if REDIS_URL is set
    from dash import CeleryManager
    from celery import Celery
    celery_app = Celery(
        __name__,
        broker = os.environ['REDIS_URL'],
        backend = os.environ['REDIS_URL']
    )
    background_callback_manager = CeleryManager(celery_app)
else:
    # Diskcache otherwise, for non-production and local dev.
    from dash import DiskcacheManager

    #cache = diskcache.Cache(settings.get('DiskcacheCache', './cache'))
    background_callback_manager = DiskcacheManager(cache, cache_by = [lambda: launch_uid])
    noncaching_background_callback_manager = DiskcacheManager(cache)

from src.newsegsmodel import newsegsmodel
from src.newsegsfinance import newsegsfinance
from src.newsegsmodel import sprakemodel
from src.newsegsfinance import sprakefinance

from src.newsegsbrowser import common as browser
from src.newsegsbrowser.common import get_icon, create_numeric_card_input, unescape_html_icons
from src.newsegsbrowser.map import create_site_selector_map, add_site_selector_callbacks
from src.newsegsbrowser.results_table import create_tbl_head, create_configuration_selector
from src.newsegsbrowser import results_table
from src.newsegsbrowser.stats import *
from src.newsegsbrowser.postprocess import post_sprake_gen_results, post_sprake_storage_results
from src.newsegsbrowser.postprocess import post_sprake_consumption_results, post_sprake_net_results
from src.newsegsbrowser.postprocess import post_sprake_finance_benefits_results, post_sprake_finance_costs_results
from src.newsegsbrowser.postprocess import post_sprake_finance_value_results

from src.newsegsbrowser import ROOTDIR, STATICDATA
#from config import settings

_CONST_FILE = os.path.join(ROOTDIR, 'constants', 'model_constants.json')

with open(_CONST_FILE, 'r') as f:
    MODEL_CONSTANTS = json.load(f)

launch_uid = uuid.uuid4()

# Locally (to app, not background callback managed) accessible dictionaries
# of models and finances. These should be keyed by their uuids.
models = {}
finances = {}
results = {}

def spawn_model():
    return sprakemodel.SprakeModel.from_none()

def get_model(model_id):
    mdl = models.get(model_id, None)
    if mdl is None:
        mdl = spawn_model()
        models[model_id] = mdl
    return mdl

def model_to_cache(model_id):
    mdl = get_model(model_id)
    cache[model_id] = mdl

def model_from_cache(model_id):
    mdl = cache.get(model_id)
    return mdl

def spawn_finance():
    return sprakefinance.SprakeFinance.from_none()

def get_finance(finance_id):
    fnc = finances.get(finance_id, None)
    if fnc is None:
        fnc = spawn_finance()
        finances[finance_id] = fnc
    return fnc

def finance_to_cache(finance_id):
    fnc = get_finance(finance_id)
    cache[finance_id] = fnc

def finance_from_cache(finance_id):
    fnc = cache.get(finance_id)
    return fnc

def compose_configuration(
    name: str,
    mdl: newsegsmodel.NewsegsModel | str,
    fnc: newsegsfinance.NewsegsFinance | str
) -> dict:
    if isinstance(mdl, newsegsmodel.NewsegsModel):
        mdl_uuid = mdl.uuid
    else:
        mdl_uuid = mdl
    if isinstance(fnc, newsegsfinance.NewsegsFinance):
        fnc_uuid = fnc.uuid
    else:
        fnc_uuid = fnc
    
    return {
        'uuid': str(uuid.uuid4()),
        'name': name,
        'model_uuid': mdl_uuid,
        'finance_uuid': fnc_uuid
    }

def create_default_model() -> newsegsmodel.NewsegsModel:
    # Load model
    with open(
        os.path.join(
            STATICDATA, 
            'sprakemodel-validation-config.json'
        ), 
    'r') as f:
        mdl_conf = json.load(f)
    return sprakemodel.SprakeModel.from_dict(mdl_conf)

def create_default_finance() -> newsegsfinance.NewsegsFinance:
    # Load finance configuration
    with open(
        os.path.join(
            STATICDATA,
            'sprakemodel-validation-finance-config.json'
        ),
    'r') as f:
        fnc_conf = json.load(f)
    
    return sprakefinance.SprakeFinance.from_dict(fnc_conf)

def create_wind_results(wind_data=None, annual=True) -> dbc.Table:
    """
    Create and format the wind generation results table
    """
    if wind_data is None:
        wind_data = {}

    if isinstance(wind_data, Mapping):
        n_configs = 1
        wind_data = [wind_data]
    else:
        n_configs = len(wind_data)

    tbl_head = create_tbl_head(n_configs)

    if (annual):
        ann_gen = present_stat_description(wind_data,
                                           ['generator_meter_summary','wind_export'],
                                           'Wind production (kWh/yr)',
                                           stat_list=ANNUAL_DEFAULT_STATS,
                                           fmt='{:,.0f}')
    else:
        ann_gen = present_stat_description(wind_data,
                                           ['generator_meter_summary', 'wind_export'],
                                           'Wind production (kWh)', 
                                           stat_list=TOTAL_DEFAULT_STATS, 
                                           fmt='{:,.0f}')

    hours_in_range = present_stat_description_compound(
        wind_data,
        'wind_production_categorised',
        'Hours in range',
        hours_in_range_formatter
    )

    longest_hours_below_5 = present_event_and_daterange(
        wind_data,
        'wind_continuous_hours_below_5pc', 
        r"Longest continuous hours <5%", 
        "hours",
        '{:,.1f}'.format
    )

    longest_hours_above_95 = present_event_and_daterange(
        wind_data,
        'wind_continuous_hours_above_95pc',
        r"Longest continuous hours ≥95%",
        "hours",
        '{:,.1f}'.format
    )

    if (annual):
        direct_sc = present_self_consumption_data(
            wind_data,
            ['self-consumption','yearly'],
            r'Wind-only self-consumption potential (kWh/yr (% production))',
            stat_list=ANNUAL_SC_STATS,
            index_filter='wind_export'
        )
    else:
        direct_sc = present_self_consumption_data(
            wind_data,
            ['self-consumption','horizon'],
            r'Wind-only self-consumption potential (kWh (% production))',
            stat_list=HORIZON_SC_STATS,
            index_filter='wind_export'
        )

    tab_body = [html.Tbody(ann_gen + hours_in_range + longest_hours_below_5 \
                           + longest_hours_above_95 + direct_sc)]

    return dbc.Table(tbl_head + tab_body)

def create_pv_results(pv_data=None, annual=True):
    if pv_data is None:
        pv_data = {}
    
    if isinstance(pv_data, Mapping):
        n_configs = 1
        pv_data = [pv_data]
    else:
        n_configs = len(pv_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        ann_gen = present_stat_description(
            pv_data,
            ['generator_meter_summary','solar_export'],
            'PV production (kWh/yr)',
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        ann_gen = present_stat_description(
            pv_data,
            ['generator_meter_summary','solar_export'],
            'PV production (kWh)',
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

    max_day = present_event_and_date(
        pv_data,
        'max_solar_day',
        r'Maximum daily production (kWh)',
        'value',
        '{:,.1f}'.format
    )

    min_day = present_event_and_date(
        pv_data,
        'min_solar_day',
        r'Minimum daily production (kWh)',
        'value',
        '{:,.1f}'.format
    )

    days_in_range = present_stat_description_compound(
        pv_data,
        'pv_production_categorised',
        r'Daily production distribution as % of max [kWh range] days (%days)',
        stat_formatter=days_in_range_formatter,
        stat_list=DEFAULT_DAYS_IN_RANGE_STATS
    )

    if (annual):
        direct_sc = present_self_consumption_data(
            pv_data,
            ['self-consumption','yearly'],
            r'PV-only self-consumption potential (kWh/yr (% production))',
            stat_list=ANNUAL_SC_STATS,
            index_filter='solar_export'
        )
    else:
        direct_sc = present_self_consumption_data(
            pv_data,
            ['self-consumption','horizon'],
            r'PV-only self-consumption potential (kWh (% production))',
            stat_list=HORIZON_SC_STATS,
            index_filter='solar_export'
        )
        
    tab_body = [html.Tbody(ann_gen + max_day + min_day + days_in_range + direct_sc)]

    return dbc.Table(tbl_head + tab_body)

def create_combined_generation_results(gen_data=None, annual=True):
    if gen_data is None:
        gen_data = {}
    if isinstance(gen_data, Mapping):
        n_configs = 1
        gen_data = [gen_data]
    else:
        n_configs = len(gen_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        ann_gen = present_stat_description(
            gen_data,
            ['generator_meter_summary','generation_export'],
            'Production (kWh/yr)',
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        ann_gen = present_stat_description(
            gen_data,
            ['generator_meter_summary','generation_export'],
            'Production (kWh/yr)',
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

    max_day = present_event_and_date(
        gen_data,
        'max_generation_day',
        r'Maximum daily production (kWh)',
        'value',
        lambda x: '{:,.1f}'.format(x)
    )

    min_day = present_event_and_date(
        gen_data,
        'min_generation_day',
        r'Minimum daily production (kWh)',
        'value',
        lambda x: '{:,.1f}'.format(x)
    )

    days_in_range = present_stat_description_compound(
        gen_data,
        'generation_production_categorised', 
        r'Daily production distribution (% of max) [kWh range] days (%days)', 
        stat_formatter=days_in_range_formatter,
        stat_list=DEFAULT_DAYS_IN_RANGE_STATS)

    if (annual):
        direct_sc = present_self_consumption_data(
            gen_data,
            ['self-consumption','yearly'],
            r'Without storage self-consumption potential (kWh/yr (% production))',
            stat_list=ANNUAL_SC_STATS,
            index_filter='generation_export'
        )
    else:
        direct_sc = present_self_consumption_data(
            gen_data,
            ['self-consumption','horizon'],
            r'Without storage self-consumption potential (kWh/yr (% production))',
            stat_list=HORIZON_SC_STATS,
            index_filter='generation_export'
        )

    tab_body = [html.Tbody(ann_gen + max_day + min_day + days_in_range + direct_sc)]

    return dbc.Table(tbl_head + tab_body)

def create_stor_results(stor_data=None, annual=True):
    if stor_data is None:
        stor_data = {}
    
    if isinstance(stor_data, Mapping):
        n_configs = 1
        stor_data = [stor_data]
    else:
        n_configs = len(stor_data)

    tbl_head = create_tbl_head(n_configs)

    if (annual):
        to_stor = present_stat_description(
            stor_data, 
            ['to_stor_meter_summary', 'storage_import'],
            'Units to storage (kWh/yr)',
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        from_stor = present_stat_description(
            stor_data,
            ['from_stor_meter_summary', 'storage_export'],
            'Units from storage (kWh/yr)',
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        loss_stor = present_stat_description(
            stor_data,
            ['loss_stor_meter_summary', 'storage_loss'],
            'Units lost (kWh/yr)',
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

        charge_cycles = present_stat_description(
            stor_data,
            ['no_charge_cycles', 'charge_cycles'],
            'Effective charge cycles (N/yr)',
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}')

        hrs_min_soc = present_stat_description_parallel(
            stor_data,
            'stor_hours_at_min',
            r'Hours at min SoC (hrs/yr, (%))',
            'hrs_at_min_soc',
            'prop_hrs_at_min_soc',
            stat_list=ANNUAL_DEFAULT_STATS
        )

        hrs_max_soc = present_stat_description_parallel(
            stor_data,
            'stor_hours_at_max',
            r'Hours at max SoC (hrs/yr, (%))',
            'hrs_at_max_soc',
            'prop_hrs_at_max_soc',
            stat_list=ANNUAL_DEFAULT_STATS
        )
    else:
        to_stor = present_stat_description(
            stor_data, 
            ['to_stor_meter_summary', 'storage_import'],
            'Units to storage (kWh)',
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        from_stor = present_stat_description(
            stor_data,
            ['from_stor_meter_summary', 'storage_export'],
            'Units from storage (kWh)',
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        loss_stor = present_stat_description(
            stor_data,
            ['loss_stor_meter_summary', 'storage_loss'],
            'Units lost (kWh)',
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

        charge_cycles = present_stat_description(
            stor_data,
            ['no_charge_cycles','charge_cycles'],
            'Effective charge cycles (N)',
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}')

        hrs_min_soc = present_stat_description_parallel(
            stor_data,
            'stor_hours_at_min',
            r'Hours at min SoC (hrs, (%))',
            'hrs_at_min_soc',
            'prop_hrs_at_min_soc',
            stat_list=TOTAL_DEFAULT_STATS
        )

        hrs_max_soc = present_stat_description_parallel(
            stor_data,
            'stor_hours_at_max',
            r'Hours at max SoC (hrs, (%))',
            'hrs_at_max_soc',
            'prop_hrs_at_max_soc',
            stat_list=TOTAL_DEFAULT_STATS
        )
    
    longest_hrs_min_soc = present_event_and_daterange(
        stor_data, 
        'max_continuous_hours_min_soc',
        r'Longest continuous hours at min SoC',
        'hours',
        '{:,.1f}'.format)

    longest_hrs_max_soc = present_event_and_daterange(
        stor_data,
        'max_continuous_hours_max_soc',
        r'Longest continuous hours at max SoC',
        'hours', 
        '{:,.1f}'.format
    )

    max_charge_rate = present_event_and_date(
        stor_data,
        'max_charge_rate_time',
        r'Maximum charge rate (kW)',
        'value',
        '{:,.1f}'.format,
        trimdate=9
    )

    max_discharge_rate = present_event_and_date(
        stor_data,
        'max_discharge_rate_time',
        r'Maximum discharge rate (kW)',
        'value',
        '{:,.1f}'.format,
        trimdate=9
    )

    tab_body = [html.Tbody(to_stor + from_stor + loss_stor + charge_cycles + hrs_min_soc + longest_hrs_min_soc + hrs_max_soc + longest_hrs_max_soc + max_charge_rate + max_discharge_rate)]

    return dbc.Table(tbl_head + tab_body)

def create_cons_results(cons_data=None, annual=True):
    if cons_data is None:
        cons_data = {}
    
    if isinstance(cons_data, Mapping):
        n_configs = 1
        cons_data = [cons_data]
    else:
        n_configs = len(cons_data)

    tbl_head = create_tbl_head(n_configs)
    
    if annual:
        psd = partial(
            present_stat_description,
            data_list = cons_data,
            stat_list=ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        psd = partial(
            present_stat_description,
            data_list = cons_data,
            stat_list=TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

    if (annual):
        app_cons = psd( 
            stat_name=['consumption_meter_summaries','appliance_import'],
            stat_label='Appliance consumption (kWh/yr)'
        )
        dhw_cons = psd(
            stat_name=['consumption_meter_summaries','dhw_import'],
            stat_label='DHW consumption (kWh/yr)'
        )
        spaceheat_cons = psd(
            stat_name=['consumption_meter_summaries','spaceheat_import'],
            stat_label='Space heat consumption (kWh/yr)'
        )

        residential_cons = psd(
            stat_name=['consumption_meter_summaries','residential'],
            stat_label='Total residential consumption (kWh/yr)'
        )
        perunit_residential_cons = psd(
            stat_name=['consumption_meter_summaries','residential_pu'],
            stat_label='Per-unit residential consumption (kWh/yr)'
        )

        ev_cons = psd(
            stat_name=['consumption_meter_summaries','evcharge_import'],
            stat_label='EV consumption (kWh/yr)'
        )
        site_cons = psd(
            stat_name=['consumption_meter_summaries','consumption'],
            stat_label='Site consumption (kWh/yr)'
        )

    else:
        app_cons = psd( 
            stat_name=['consumption_meter_summaries','appliance_import'],
            stat_label='Appliance consumption (kWh)'
        )
        dhw_cons = psd(
            stat_name=['consumption_meter_summaries','dhw_import'],
            stat_label='DHW consumption (kWh)'
        )
        spaceheat_cons = psd(
            stat_name=['consumption_meter_summaries','spaceheat_import'],
            stat_label='Space heat consumption (kWh)'
        )

        residential_cons = psd(
            stat_name=['consumption_meter_summaries','residential'],
            stat_label='Total residential consumption (kWh)'
        )
        perunit_residential_cons = psd(
            stat_name=['consumption_meter_summaries','residential_pu'],
            stat_label='Per-unit residential consumption (kWh)'
        )

        ev_cons = psd(
            stat_name=['consumption_meter_summaries','evcharge_import'],
            stat_label='EV consumption (kWh)'
        )
        site_cons = psd(
            stat_name=['consumption_meter_summaries','consumption'],
            stat_label='Site consumption (kWh)'
        )

    max_day = present_event_and_date(
        cons_data,
        'max_consumption_day',
        r'Maximum daily consumption (kWh)',
        'value',
        '{:,.1f}'.format
    )

    min_day = present_event_and_date(
        cons_data,
        'min_consumption_day',
        r'Minimum daily consumption (kWh)',
        'value',
        '{:,.1f}'.format
    )

    admd = present_single_stat(
        cons_data,
        'admd_calculated',
        'ADMD - calculated (kW)',
        'value',
        fmt='{:,.0f}'
    )
    max_demand = present_event_and_date(
        cons_data, 
        'admd_observed',
        'Maximum demand (kW)',
        'value',
        '{:,.0f}'.format
    )
    
    tab_body = [html.Tbody(app_cons + dhw_cons + spaceheat_cons + residential_cons + perunit_residential_cons + ev_cons + site_cons + admd + max_demand + min_day + max_day)]

    return dbc.Table(tbl_head + tab_body)

def create_seasonal_cons_results(cons_data=None, annual=True):
    if cons_data is None:
        cons_data = {}
    
    if isinstance(cons_data, Mapping):
        n_configs = 1
        cons_data = [cons_data]
    else:
        n_configs = len(cons_data)

    tbl_head = create_tbl_head(n_configs)
    
    if (annual):
        weekday_sitecons = present_seasonal_consumption_data(
            cons_data,
            ['seasonal_consumption','wd'],
            r'Weekday site demand (kWh/yr | kWh/day)',
            stat_list=ANNUAL_CONS_STATS
        )

        sat_sitecons = present_seasonal_consumption_data(
            cons_data,
            ['seasonal_consumption','sat'],
            r'Saturday site demand (kWh/yr | kWh/day)',
            stat_list=ANNUAL_CONS_STATS
        )

        sun_sitecons = present_seasonal_consumption_data(
            cons_data,
            ['seasonal_consumption','sun'],
            r'Sunday/holiday site demand (kWh/yr | kWh/day)',
            stat_list=ANNUAL_CONS_STATS
        )

    else:
        weekday_sitecons = present_seasonal_consumption_data(
            cons_data,
            ['seasonal_consumption','wd'],
            r'Weekday site demand (kWh | kWh/day)',
            stat_list=HORIZON_CONS_STATS
        )

        sat_sitecons = present_seasonal_consumption_data(
            cons_data,
            ['seasonal_consumption','sat'],
            r'Saturday site demand (kWh | kWh/day)',
            stat_list=HORIZON_CONS_STATS
        )

        sun_sitecons = present_seasonal_consumption_data(
            cons_data,
            ['seasonal_consumption','sun'],
            r'Sunday/holiday site demand (kWh | kWh/day)',
            stat_list=HORIZON_CONS_STATS
        )

    tab_body = [html.Tbody(weekday_sitecons + sat_sitecons + sun_sitecons)]

    return dbc.Table(tbl_head + tab_body)

def create_net_results(net_data=None, annual=True):
    if net_data is None:
        net_data = {}
    
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    if isinstance(net_data, Mapping):
        n_configs = 1
        net_data = [net_data]
    else:
        n_configs = len(net_data)
    
    if (annual):
        meter_stats = present_single_stat_per_row(
            net_data,
            'meter_summaries',
            ['grid_export', 'grid_import', 'storage_loss', 'peak_grid_export', 'peak_grid_import'],
            statistic_names = DEFAULT_STATISTICS_ANNUAL,
            fmt='{:,.0f}',
            variable_mapper = {
                'grid_export' : 'Export to grid (kWh/yr)',
                'grid_import' : 'Import from grid (kWh/yr)',
                'storage_loss' : 'Storage losses (kWh/yr)',
                'peak_grid_export': 'Exports 5pm-8pm (kWh/yr)',
                'peak_grid_import': 'Imports 5pm-8pm (kWh/yr)',
            }
        )
        
    else:
        meter_stats = present_single_stat_per_row(
            net_data,
            'meter_summaries',
            ['grid_export', 'grid_import', 'storage_loss', 'peak_grid_export', 'peak_grid_import'],
            statistic_names = DEFAULT_STATISTICS_HORIZON,
            fmt='{:,.0f}',
            variable_mapper = {
                'grid_export' : 'Export to grid (kWh)',
                'grid_import' : 'Import from grid (kWh)',
                'storage_loss' : 'Storage losses (kWh)',
                'peak_grid_export': 'Exports 5pm-8pm (kWh)',
                'peak_grid_import': 'Imports 5pm-8pm (kWh)',
            }
        )

    out_table = meter_stats
    out_table.index.names = [None, None]
    out_table.columns = ['<i class="' + get_icon(x, style_name='raw') + ' p-1 m-2"></i>' for x in out_table.columns]

    return Purify(html = unescape_html_icons(out_table.to_html(classes='table', border=False)))

def create_seasonal_net_results(net_data=None, annual=True):
    if net_data is None:
        net_data = {}
    
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    if isinstance(net_data, Mapping):
        n_configs = 1
        net_data = [net_data]
    else:
        n_configs = len(net_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        export_stats = present_paired_seasonal_stats(
            net_data,
            'export_seasonal_statistics',
            'export_seasonal_statistics_normalised',
            ['grid_export', 'peak_grid_export'],
            statistic_names = DEFAULT_STATISTICS_ANNUAL,
            variable_mapper = {
                'grid_export': r'Export to grid (kWh/yr (% production))',
                'peak_grid_export': r'Exports 5pm-8pm (kWh/yr (% production))'
            }
        )

        import_stats = present_paired_seasonal_stats(
            net_data,
            'import_seasonal_statistics',
            'import_seasonal_statistics_normalised',
            ['grid_import', 'peak_grid_import'],
            statistic_names = DEFAULT_STATISTICS_ANNUAL,
            variable_mapper = {
                'grid_import': r'Import from grid (kWh/yr (% consumption))',
                'peak_grid_import': r'Imports 5pm-8pm (kWh/yr (% consumption))'
            }
        )
    else:
        export_stats = present_paired_seasonal_stats(
            net_data,
            'export_seasonal_statistics',
            'export_seasonal_statistics_normalised',
            ['grid_export', 'peak_grid_export'],
            statistic_names = DEFAULT_STATISTICS_HORIZON,
            variable_mapper = {
                'grid_export': r'Export to grid (kWh (% production))',
                'peak_grid_export': r'Exports 5pm-8pm (kWh (% production))'
            }
        )

        import_stats = present_paired_seasonal_stats(
            net_data,
            'import_seasonal_statistics',
            'import_seasonal_statistics_normalised',
            ['grid_import', 'peak_grid_import'],
            statistic_names = DEFAULT_STATISTICS_HORIZON,
            variable_mapper = {
                'grid_import': r'Import from grid (kWh (% consumption))',
                'peak_grid_import': r'Imports 5pm-8pm (kWh (% consumption))'
            }
        )

    out_table = pd.concat([
        export_stats,
        import_stats
    ])
    out_table.index.names = [None, None, None]
    out_table.columns = ['<i class="' + get_icon(x, style_name='raw') + ' p-1 m-2"></i>' for x in out_table.columns]

    return Purify(html = unescape_html_icons(out_table.to_html(classes='table', border=False)))

def create_so_benefits_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)

    if (annual):
        receipt_stats = present_single_stat_per_row(
            econ_data,
            'undiscounted_receipts_summaries',
            ['receipts_resident', 'receipts_resident_perunit', 'receipts_ev', 'receipts_exports'],
            statistic_names = DEFAULT_STATISTICS_ANNUAL,
            fmt='{:,.0f}',
            variable_mapper = {
                'receipts_resident': 'Resident receipts (£/yr)',
                'receipts_resident_perunit': 'Resident receipts (£/yr/household)',
                'receipts_ev': 'EV receipts (£/yr)',
                'receipts_exports': 'Export receipts (£/yr)',
            }
        )
    else:
        receipt_stats = present_single_stat_per_row(
            econ_data,
            'undiscounted_receipts_summaries',
            ['receipts_resident', 'receipts_resident_perunit', 'receipts_ev', 'receipts_exports'],
            statistic_names = DEFAULT_STATISTICS_HORIZON,
            fmt='{:,.0f}',
            variable_mapper = {
                'receipts_resident': 'Undiscounted resident receipts (£)',
                'receipts_resident_perunit': 'Undiscounted resident receipts (£/household)',
                'receipts_ev': 'Undiscounted EV receipts (£)',
                'receipts_exports': 'Undiscounted export receipts (£)',
            }
        )

    total_benefits = present_single_scalar(
        econ_data,
        'present_benefits_undiscounted',
        'Present benefits (undiscounted) (£)',
        'Total'
    )

    total_benefits_discounted = present_paired_scalars(
        econ_data,
        'present_benefits_discounted',
        'benefits_discount_rate',
        'Present benefits (discounted) (£)',
        'Total',
        fmt='{:,.2f} (@{:,.1%})'
    )

    out_table = pd.concat([
        receipt_stats,
        total_benefits,
        total_benefits_discounted
    ])

    out_table.index.names = [None, None]
    out_table.columns = ['<i class="' + get_icon(x, style_name='raw') + ' p-1 m-2"></i>' for x in out_table.columns]

    return Purify(html = unescape_html_icons(out_table.to_html(classes='table', border=False)))

def create_so_costs_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    
    if (annual):
        recurring_stats = present_single_stat_per_row(
            econ_data,
            'undiscounted_variable_costs_summaries',
            ['import_costs', 'om_costs_gen', 'om_costs_stor', 'variable_costs'],
            statistic_names = DEFAULT_STATISTICS_ANNUAL,
            fmt='{:,.0f}',
            variable_mapper = {
                'import_costs': 'Import costs (£/yr)',
                'om_costs_gen': 'O&M costs - generation (£/yr)',
                'om_costs_stor': 'O&M costs - storage (£/yr)',
                'variable_costs': 'Recurrent costs - total (£/yr)',
            }
        )
        
    else:
        recurring_stats = present_single_stat_per_row(
            econ_data,
            'undiscounted_variable_costs_summaries',
            ['import_costs', 'om_costs_gen', 'om_costs_stor', 'variable_costs'],
            statistic_names = DEFAULT_STATISTICS_HORIZON,
            fmt='{:,.0f}',
            variable_mapper = {
                'import_costs': 'Undiscounted import costs (£)',
                'om_costs_gen': 'Undiscounted O&M costs - generation (£)',
                'om_costs_stor': 'Undiscounted O&M costs - storage (£)',
                'variable_costs': 'Undiscounted recurrent costs - total (£)',
            }
        )

    
    capex_stats = present_single_stat_per_row(
        econ_data,
        'undiscounted_capex_summaries',
        ['capex_costs_gen', 'capex_costs_stor', 'capex_costs_dist', 'capex_costs_metering', 'capex_costs_total'],
        statistic_names = DEFAULT_STATISTICS_HORIZON,
        fmt='{:,.0f}',
        variable_mapper = {
            'capex_costs_gen': 'Capital costs - generation (£)',
            'capex_costs_stor': 'Capital costs - storage (£)',
            'capex_costs_dist': 'Capital costs - distribution and switching (£)',
            'capex_costs_metering': 'Capital costs - metering (£)',
            'capex_costs_total': 'Capital costs - total (£)'
        }
    )

    total_costs = present_single_scalar(
        econ_data,
        'present_costs_undiscounted',
        'Present costs (undiscounted) (£)',
        'Total'
    )

    total_costs_discounted = present_paired_scalars(
        econ_data,
        'present_costs_discounted',
        'costs_discount_rate',
        'Present costs (discounted) (£)',
        'Total',
        fmt='{:,.2f} (@{:,.1%})'
    )

    out_table = pd.concat([
        recurring_stats,
        capex_stats,
        total_costs,
        total_costs_discounted,
    ])

    out_table.index.names = [None, None]
    out_table.columns = ['<i class="' + get_icon(x, style_name='raw') + ' p-1 m-2"></i>' for x in out_table.columns]

    return Purify(html = unescape_html_icons(out_table.to_html(classes='table', border=False)))
    
def create_so_value_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}

    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    simple_stats = present_single_stat_per_row(
        econ_data,
        'value_summaries',
        ['benefit_cost_ratio_undiscounted', 'net_present_value_undiscounted', 'simple_payback_time_yrs'],
        statistic_names = DEFAULT_STATISTICS_HORIZON,
        fmt='{:,.2f}',
        variable_mapper = {
            'benefit_cost_ratio_undiscounted': 'Benefits/Costs (undiscounted)',
            'net_present_value_undiscounted': 'Net Present Value (£) (undiscounted)',
            'simple_payback_time_yrs': 'Simple payback time (years)'
        }
    )

    compound_stats = present_single_stat_per_row_plus_paired_scalars(
        econ_data,
        'value_summaries',
        ['benefit_cost_ratio_discounted', 'net_present_value_discounted'],
        'benefits_discount_rate',
        'costs_discount_rate',
        statistic_names = DEFAULT_STATISTICS_HORIZON,
        variable_mapper = {
            'benefit_cost_ratio_discounted': 'Benefits/Costs (benefit discount / cost discount)',
            'net_present_value_discounted': 'Net Present Value (£) (benefit discount / cost discount)',
        }
    )

    out_table = (
        pd.concat([
            simple_stats,
            compound_stats
        ])
        .iloc[[0,3,1,4,2],:]
    )

    out_table.index.names = [None, None]
    out_table.columns = ['<i class="' + get_icon(x, style_name='raw') + ' p-1 m-2"></i>' for x in out_table.columns]

    return Purify(html = unescape_html_icons(out_table.to_html(classes='table', border=False)))

def create_generation_input_card():
    """
    A Bootstrap card holding inputs for generation config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('generation'), 'Generation'], className='card-title'),
            html.H4([
                'Total generation: ',
                get_icon('gen-wind','p-1 my-1, ml-1', 'unpadded'),
                " = ",
                html.Span("0.0", id='gen-smry-wind-cap'),
                " kW; ",
                get_icon('gen-pv','p-1 my-1, ml-1', 'unpadded'),
                " = ",
                html.Span("0.0", id='gen-smry-pv-cap'),
                " kWp"
            ],
            className='card-subtitle'),
            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'gen-wind',
                            'Wind Capacity (kW rated)',
                            'input-model-config',
                            'wind_capacity',
                            section = 'gen_input',
                            max = 10000,
                            step = 5.0
                        )    
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'gen-pv',
                            'Solar PV Capacity (kWp)',
                            'input-model-config',
                            'pv_capacity',
                            section = 'gen_input',
                            max = 10000,
                            step = 5.0
                        )
                    )
                ])
            ])
        ])
    ])

def create_storage_input_card():
    """
    A Bootstrap card holding inputs for storage config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('storage'), "Storage"], 
            className='card-title'),
            
            html.H4([
                'Storage capacity: ',
                html.Span("0.0", id='stor-smry-cap'),
                " kWh"
            ],
            className='card-subtitle'),
            
            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'storage',
                            'Storage Capacity (kWh)',
                            'input-model-config',
                            'storage_capacity',
                            section = 'stor_input',
                            max = 10000,
                            step = 5.0
                        ),
                    ])
                ])
            ])
        ])
    ])

def create_building_consumption_input_card():
    """
    A Bootstrap card holding inputs for building consumption config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('consumption-building'), "Building Consumption"], 
            className='card-title'),
            
            html.H4([
                'Site size: ',
                html.Span("0", id="bc-smry-n-units"),
                " units"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-nunits',
                            'No. of households',
                            'input-model-config',
                            'n_units',
                            section = 'bc_input',
                            max = 1000,
                            step = 1
                        ),
                    ]),
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-hlp',
                            'HLP (W/m²/K)',
                            'input-model-config',
                            'hlp',
                            section = 'bc_input',
                            max = 3.0,
                            step = 0.1
                        ),
                    ]),
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-gfa',
                            'Mean GFA (m²/household)',
                            'input-model-config',
                            'gfa',
                            section = 'bc_input',
                            max = 300,
                            step = 1
                        ),
                    ]),
                    # TODO: Output Fabric Energy Efficiency here
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-dhw-ref',
                            'Reference hot water demand (kWh/day)',
                            'input-model-config',
                            'ref_daily_consumption',
                            section = 'bc_input',
                            max = 10.0,
                            step = 0.1
                        ),
                    ]),
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-dhw-var',
                            'Seasonal variation (%)',
                            'input-model-config',
                            'seasonal_variance',
                            section = 'bc_input',
                            max = 100.0,
                            step = 1
                        ),
                    ])
                    # TODO: Output annual DHW demand
                ])
            ])
        ])
    ])

def create_direct_consumption_input_card():
    """
    A Bootstrap card holding inputs for direct consumption config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('consumption-direct'), 'Direct Consumption'],
            className='card-title'),
            
            html.H4([
                get_icon('consumption-direct-appliance'),
                " = ",
                html.Span("0.0", id="cons-smry-app"),
                " kWh/yr/household; ",
                get_icon('consumption-direct-ev'),
                " = ",
                html.Span("0.0", id="cons-smry-ev"),
                " kWh/yr/household"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'consumption-direct-appliance-reduction',
                            'High-efficiency appliances consumption reduction (fraction)',
                            'input-model-config',
                            'efficiency_reduction',
                            section = 'dc_input',
                            max = 1,
                            step = 0.05
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'consumption-direct-ev-anncharge',
                            'Residential charging per EV (kWh/yr)',
                            'input-model-config',
                            'annual_residential_consumption_per_ev',
                            section = 'dc_input',
                            max = 4000,
                            step = 0.05,
                            placeholder = 2000
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'consumption-direct-ev-nperunit',
                            'EVs per household (n)',
                            'input-model-config',
                            'n_evs_per_household',
                            section = 'dc_input',
                            max = 3,
                            step = 0.05,
                            placeholder = 0.2
                        )
                    ),
                ])
            ])
        ])
    ])

def create_gen_cost_input_card():
    """
    HTML inputs for generation costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-generation'), 'Generation Costs'],
            className='card-title'),

            html.H4([
                "Capital cost = £",
                html.Span("0", id="cost-gen-smry-capex"),
                "; Ongoing costs = £",
                html.Span("0", id="cost-gen-smry-ongoing"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'gen-wind',
                            'Wind Capex (£/kW)',
                            'input-finance-config',
                            'wind_capex_per_kw',
                            section = 'unit_costs',
                            max = 10000,
                            step = 50
                        )
                        #create_numeric_card_input('gen-wind',
                        #                          'Wind Capex (£/kW)',
                        #                          'cost-gen-wind-capex-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            ['gen-wind','cost-recurrent'],
                            'Wind Ongoing (£/kW/yr)',
                            'input-finance-config',
                            'wind_om_per_kw_year',
                            section = 'unit_costs',
                            max = 5000,
                            step = 10
                        )
                        #create_numeric_card_input(['gen-wind','cost-recurrent'],
                        #                          'Wind Ongoing (£/kW/yr)',
                        #                          'cost-gen-wind-recurrent-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'gen-pv',
                            'Solar PV Capex (£/kWp)',
                            'input-finance-config',
                            'pv_capex_per_kw',
                            section = 'unit_costs',
                            max = 10000,
                            step = 50
                        )
                        #create_numeric_card_input('gen-pv',
                        #                          'Solar PV Capex (£/kWp)',
                        #                          'cost-gen-pv-capex-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            ['gen-pv','cost-recurrent'],
                            'Solar PV Ongoing (£/kWp/yr)',
                            'input-finance-config',
                            'pv_om_per_kw_year',
                            section = 'unit_costs',
                            max = 5000,
                            step = 10
                        )
                        #create_numeric_card_input(['gen-pv','cost-recurrent'],
                        #                          'Solar PV Ongoing (£/kWp/yr)',
                        #                          'cost-gen-pv-recurrent-input')
                    ),
                ])
            ])
        ]),
    ])

def create_storage_cost_input_card():
    """
    HTML inputs for storage costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-storage'), 'Storage Costs'],
            className='card-title'),

            html.H4([
                "Capital cost = £",
                html.Span("0", id="cost-stor-smry-capex"),
                "; Ongoing costs = £",
                html.Span("0", id="cost-stor-smry-ongoing"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'storage',
                            'BESS Capex (£/kWh)',
                            'input-finance-config',
                            'bess_capex_per_kwh',
                            section = 'unit_costs',
                            max = 10000,
                            step = 50
                        )
                        #create_numeric_card_input('storage',
                        #                          'BESS Capex (£/kWh)',
                        #                          'cost-stor-bess-capex-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            ['storage', 'cost-recurrent'],
                            'BESS Ongoing (£/kWh/yr)',
                            'input-finance-config',
                            'bess_om_per_kwh_year',
                            section = 'unit_costs',
                            max = 5000,
                            step = 10
                        )
                        #create_numeric_card_input(['storage', 'cost-recurrent'],
                        #                           'BESS Ongoing (£/kWh/yr)',
                        #                           'cost-stor-bess-recurrent-input')
                    ),
                ])
            ])
        ])
    ])

def create_sales_input_card():
    """
    HTML inputs for sales value (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-sales'), 'Sales'],
            className='card-title'),

            html.H4([
                get_icon('cost-residents'),
                " = £",
                html.Span("0", id="cost-sales-smry-residents"),
                "/yr; ",
                get_icon('cost-export'),
                " = £",
                html.Span("0", id="cost-sales-smry-export"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-residents-standing',
                            'Standing charge (£/household/day)',
                            'input-finance-config',
                            'resident_sc_per_unit_day',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                        #create_numeric_card_input('cost-residents-standing',
                        #                          'Standing charge (£/household/day)',
                        #                          'cost-resident-sc-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-residents-perunit',
                            'Per unit charge (£/kWh)',
                            'input-finance-config',
                            'resident_var_per_unit',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                        #create_numeric_card_input('cost-residents-perunit',
                        #                          'Per unit charge (£/kWh)',
                        #                          'cost-resident-var-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-export',
                            'Grid export - mean per unit (£/kWh)',
                            'input-finance-config',
                            'grid_export_var_per_unit',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                        #create_numeric_card_input('cost-export',
                        #                          'Grid export - mean per unit charge (£/kWh)',
                        #                          'cost-export-var-input')
                    ),
                ])
            ])
        ])
    ])

def create_import_cost_input_card():
    """
    HTML inputs for import costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-import'), 'Import Costs'],
            className='card-title'),

            html.H4([
                "Fixed costs = £",
                html.Span("0", id="cost-import-smry-fixed"),
                "/yr; Ongoing costs = £",
                html.Span("0", id="cost-import-smry-ongoing"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-import-fixed',
                            'Fixed costs for backup (£/site/day)',
                            'input-finance-config',
                            'grid_import_sc_per_day',
                            section = 'unit_costs',
                            max = 10000,
                            step = 10
                        )
                        #create_numeric_card_input('cost-import-fixed',
                        #                          'Fixed costs for backup (£/site/day)',
                        #                          'cost-import-sc-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-import-perunit',
                            'Per-unit costs for backup (£/kWh)',
                            'input-finance-config',
                            'grid_import_var_per_unit',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                        #create_numeric_card_input('cost-import-perunit',
                        #                          'Per-unit costs for backup (£/kWh)', 
                        #                          'cost-import-var-input')
                    ),
                ])
            ])
        ])
    ])

def create_model_settings_input_card():
    """
    HTML inputs for general model settings (e.g. time horizon)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('model-settings'), 'Model Settings'],
            className='card-title'),

            html.H4([
                get_icon('model-settings-time-horizon'),
                " = ",
                html.Span("10", id="mdl-smry-horizon"),
                " years"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'model-settings-time-horizon',
                            'Time horizon (years)',
                            'input-model-config',
                            'horizon',
                            section = 'mc_input',
                            max = 10,
                            step = 1
                        )
                    ),
                ])
            ])
        ]),
    ])

def create_finance_settings_input_card():
    """
    HTML inputs for general finance settings (e.g. discount rates)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('finance-settings'), 'Finance Settings'],
            className='card-title'),

            html.H4([
                get_icon('finance-settings-benefit-discount'),
                " = ",
                html.Span("0%", id="fnc-smry-benefit-dr"),
                "; ",
                get_icon('finance-settings-cost-discount'),
                " = ",
                html.Span("0%", id="fnc-smry-cost-dr"),
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'finance-settings-benefit-discount',
                            'Benefit discount rate (%)',
                            'input-finance-config',
                            'benefit_discount_rate',
                            section = None,
                            max = 100,
                            step = 1
                        )

                        #create_numeric_card_input('finance-settings-benefit-discount',
                        #                          'Benefit discount rate (%)',
                        #                          'fnc-benefit-dr-input')
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'finance-settings-cost-discount',
                            'Benefit discount rate (%)',
                            'input-finance-config',
                            'cost_discount_rate',
                            section = None,
                            max = 100,
                            step = 1
                        )

                        #create_numeric_card_input('finance-settings-cost-discount',
                        #                          'Cost discount rate (%)',
                        #                          'fnc-cost-dr-input')
                    )
                ])
            ])
        ]),
    ])

def create_results_header():
    """
    HTML separating the results and providing controls for setting result format per annum or
    to horizon
    """
    return html.Div(
        [
            html.Div(id='resize-handle'),

            html.Div(
                dbc.Container(
                    dbc.Row([
                        html.H1([get_icon('results'), 'Results'],
                        style={
                            'display': 'inline-block',
                            'width':'33%',
                            'float': 'left'
                        }),

                        html.Span([
                            dbc.Button(
                                html.I(
                                    className = get_icon('config-1', style_name = 'raw'),
                                    style={'display': 'inline'}
                                ),
                                color='primary',
                                id = {'type': 'config-hdrfocus-btn', 'index': 0},
                                outline = False
                            )
                        ],
                        id = 'config-selector-hdrcontainer',
                        style = {
                            'display': 'inline-block',
                            'width': '33%',
                            'float': 'left',
                            'vertical-align': 'bottom',
                            'padding-top': '10px',
                            #'alignItems': 'center',
                        }
                        ),

                        html.Span([
                            html.H5("Per year",style={'display': 'inline-block', 'verticalAlign': 'middle'}),
                            daq.ToggleSwitch(style={'display': 'inline-block',
                                                    'verticalAlign': 'middle',
                                                    'padding': "10px"},
                                            id='annual-horizon-toggle'),
                            html.H5('To horizon',style={'display': 'inline-block', 'verticalAlign': 'middle'})
                        ],
                        style={
                            'display': 'inline-block',
                            'width':'33%',
                            'float': 'right',
                            "justifyContent": "flex-end",
                            "alignItems": "center",
                            'textAlign': 'right'
                        },
                        id='annual-horizon-toggle-container'
                        ),
                    ]),
                ),
            id = 'drawer-title',
        )
        ],
    id='drawer-header'
    )

def create_generation_results_card():
    """
    A bootstrap card holding generation results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('generation'), 'Generation Results'],
            className='card-title'),

            html.H4([
                'Annual generation: ',
                get_icon('generation'),
                " = ",
                html.Span("0.0"),
                " kWh; ",
                get_icon('gen-wind'),
                " = ",
                html.Span("0.0"),
                " kWh; ",
                get_icon('gen-pv'),
                " = ",
                html.Span("0.0"),
                " kWh"
            ],
            id='gen-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary("Wind Generation"),
                html.Div([
                    create_wind_results()
                    ],
                    id="res-gen-wind-tbl")
            ]),
            html.Details([
                html.Summary("Solar PV Generation"),
                html.Div([
                    create_pv_results()
                    ],
                    id="res-gen-pv-tbl")
            ]),

            html.Details([
                html.Summary("Total Generation"),
                html.Div([
                    create_combined_generation_results()
                    ],
                    id="res-gen-combined-tbl")
            ])
        ])
    ])

def create_storage_results_card():
    """
    A bootstrap card holding storage results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('storage'), 'Storage Results'],
            className='card-title'),

            html.H4([
                'Hours full = ',
                html.Span("0"),
                "; Hours empty = ",
                html.Span("0"),
                "; Charge cycles = ",
                html.Span("0")
            ],
            id='stor-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary('Storage'),
                html.Div([
                    create_stor_results()
                ],
                id='res-stor-tbl')
            ])
        ])
    ])

def create_consumption_results_card():
    """
    A bootstrap card holding consumption results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('consumption-direct'), 'Consumption Results'],
            className='card-title'),

            html.H4([
                'Annual consumption: ',
                get_icon('consumption-building'),
                ' = ',
                html.Span('0.0'),
                ' kWh; ',
                get_icon('consumption-direct-ev'),
                ' = ',
                html.Span('0.0'),
                ' kWh'                
            ],
            id='cons-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary('Consumption'),
                html.Div([
                    create_cons_results()
                ],
                id='res-cons-tbl')
            ]),

            html.Details([
                html.Summary('Seasonal Consumption'),
                html.Div([
                    create_seasonal_cons_results()
                ],
                id='res-cons-seasonal-tbl')
            ])
        ])
    ])

def create_net_results_card():
    """
    A bootstrap card holding net energy flow results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('import-export'), 'Net Energy Results'],
            className='card-title'),

            html.H4([
                'Annual export = ',
                html.Span('0.0'),
                ' kWh; Annual import = ',
                html.Span('0.0'),
                ' kWh; Storage losses = ',
                html.Span('0.0'),
                ' kWh'
            ],
            id='net-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary('Overall net energy'),
                html.Div([
                    create_net_results()
                ],
                id='res-net-tbl')
            ]),

            html.Details([
                html.Summary('Seasonal net energy'),
                html.Div([
                    create_seasonal_net_results()
                ],
                id='res-net-seasonal-tbl')
            ])
        ])
    ])

def create_economic_results_so_card():
    """
    A bootstrap card holding economic results from the system owner perspective
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost'), 'Financial Results - System Owner'],
            className='card-title'),

            html.H4([
                'Total benefits (',
                html.Span('0%'),
                ') = ',
                html.Span('£0.00'),
                '; Total costs (',
                html.Span('0%'),
                ') = ',
                html.Span('£0.00'),
                '; NPV = ',
                html.Span('£0.00'),
            ],
            id='finance-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary('Benefits'),
                html.Div([
                    create_so_benefits_results()
                ],
                id='res-finance-so-benefits-tbl')
            ]),

            html.Details([
                html.Summary('Costs'),
                html.Div([
                    create_so_costs_results()
                ],
                id='res-finance-so-costs-tbl')
            ]),

            html.Details([
                html.Summary('Value'),
                html.Div([
                    create_so_value_results()
                ],
                id='res-finance-so-value-tbl')
            ]),
        ])
    ])

def create_layout():
    """
    Create Sprake Energy Model Interface Layout in HTML
    """
    mapview = html.Div([
        dbc.Row(dbc.Col(create_site_selector_map(),width=12)),
        
        html.Hr(),

        # Site details

        dbc.Row([
            dbc.Col([
                create_generation_input_card()
            ],
            lg = 6),
            dbc.Col([
                create_storage_input_card()
            ],
            lg = 6),
        ]),

        dbc.Row([
            dbc.Col([
                create_building_consumption_input_card()
            ],
            lg = 6
            ),
            dbc.Col([
                create_direct_consumption_input_card()
            ],
            lg = 6
            ),
        ]),

        html.Hr(),

        # Financial details

        dbc.Row([
            dbc.Col([
                create_gen_cost_input_card()
            ],
            lg=6),
            dbc.Col([
                create_storage_cost_input_card()
            ],
            lg=6),
        ]),

        dbc.Row([
            dbc.Col([
                create_sales_input_card()
            ],
            lg=6),
            dbc.Col([
                create_import_cost_input_card()
            ],
            lg=6),
        ]),

        html.Hr(),

        # Model settings

        dbc.Row([
            dbc.Col([
                create_model_settings_input_card()
            ],
            width=12)
        ]),

        # Finance settings

        dbc.Row([
            dbc.Col([
                create_finance_settings_input_card()
            ],
            width=12)
        ]),

        html.Hr(),

        # Results
      
        html.Div([
            dcc.Loading([
                create_results_header(),
                html.Div(
                    [
                        create_configuration_selector(),

                        dbc.Row([
                            dbc.Col([
                                create_generation_results_card()
                            ],
                                width=12),
                            dbc.Col([
                                create_storage_results_card()
                            ],
                                width=12),
                            dbc.Col([
                                create_consumption_results_card()
                            ],
                                width=12),
                            dbc.Col([
                                create_net_results_card()
                            ],
                                width=12),
                            dbc.Col([
                                create_economic_results_so_card()
                            ],
                                width=12)
                        ]),
                    ],
                    id = 'drawer-content',
                ),
                # To trigger resync of input fields from model, e.g. after a load
                dcc.Store(id='firstload-config-watcher'),
                dcc.Store(id='live-config-watcher'),

                ##### Queues
                
                # A queue of actions performed by the user
                # Generally will hold changes to model and finance configurations
                # to enact.
                dcc.Store(id = 'queue-action-user'),
                # A pre-queue holds individual actions on the way to the queue
                # manager
                dcc.Store(id = 'prequeue-action-user'),
                # A dispatch object holds actions that may be handled by the
                # dispatcher.
                dcc.Store(id = 'dispatchitem-action-user'),
                # An Interval element is necessary to trigger the queue until
                # it is cleared
                dcc.Interval(id = 'interval-action-user', interval = 1000, disabled = True),

                # A queue of model run requests
                # Will generally get added to when a configuration changes
                # but the running of the model is latched off
                dcc.Store(id = 'queue-model-run'),
                # A pre-queue to transfer model run requests to the queue
                # manager
                dcc.Store(id = 'prequeue-model-run'),
                # An Interval element to trigger the queue until it is cleared
                dcc.Interval(id = 'interval-model-run', interval = 1000, disabled = True),
                # A dispatch object holding id of a model permitted to run
                dcc.Store(id = 'dispatchitem-model-run'),
                # Trigger object for the model run
                dcc.Store(id = 'trigger-model-run'),
                # Trigger object for relocalising model after run
                dcc.Store(id = 'trigger-post-model-run'),
                # A store to trigger handling of model run completion
                dcc.Store(id = 'trigger-postprocess-model-run'),

                # A queue of finance run requests
                # A pre-queue to transfer finance run requests to the queue
                # manager
                dcc.Store(id = 'prequeue-finance-run'),
                # The queue to hold scheduled finance runs
                dcc.Store(id = 'queue-finance-run'),
                # An Interval to trigger the queue manager until queue is cleared
                dcc.Interval(id = 'interval-finance-run', interval = 1000, disabled = True),
                # A dispatch object holding id of a finance permitted to run
                dcc.Store(id = 'dispatchitem-finance-run'),
                # Trigger object for the finance run
                dcc.Store(id = 'trigger-finance-run'),
                # Trigger object for relocalising finance after run
                dcc.Store(id = 'trigger-post-finance-run'),
                # Trigger handling of finance run completion
                dcc.Store(id = 'trigger-postprocess-finance-run'),

                ##### Latches

                # A global switch to disable model runs
                dcc.Store(id = 'latch-model-run-global'),
                # A global switch to disable finance runs
                dcc.Store(id = 'latch-finance-run-global'),
                # A list of checked-out models whose configuration cannot be updated
                dcc.Store(id = 'latch-models-checkedout'),
                # A list of checked-out finances whose configuratoin cannot be updated
                dcc.Store(id = 'latch-finances-checkedout'),

                # Updated when the model configuration is updated.
                # Used to indicate that a new run is necessary to update results.
                dcc.Store(id='model-config-watcher'),

                # A store of the available and active configurations
                # As a JSON list of the results of `compose_configuration`
                dcc.Store(id = 'store-selected-configuration'),
                dcc.Store(id = 'store-configurations'),

                # Stores for the -to-interface configurations of the models
                # and finances that are in the current session.
                # These should only really be necessary to draw from when
                # recreating a model after a migration
                dcc.Store(id = 'store-model-interface-configurations'),
                dcc.Store(id = 'store-finance-interface-configurations'),

                # Updated when either:
                # 1) The finance module has been set to a new configuration or
                # 2) The model has finished running
                # In either case, a refresh of the financial results is required.
                dcc.Store(id='finance-config-watcher'),

                # To trigger resync of output fields after a model run
                # Holds the uuid of the model (not the configuration)
                dcc.Store(id='store-model-completed-run'),

                dcc.Store(id='model-config'),
                dcc.Store(id='finance-config'),
                dcc.Store(id='res-gen'),
                dcc.Store(id='res-stor'),
                dcc.Store(id='res-cons'),
                dcc.Store(id='res-net'),
                dcc.Store(id='res-finance-so-benefits'),
                dcc.Store(id='res-finance-so-costs'),
                dcc.Store(id='res-finance-so-value'),
                ],
                overlay_style={
                    'visibility': 'visible',
                    'filter': 'blur(2px)',
                    'display': 'block',
                },
                id = 'loading-results',
                parent_className = 'drawer-loading-container',
            ),
            ],
            id='drawer-container',
        ),
                    
        html.Div(
            id='post-drawer-attach',
            style={'display':'none'}
        ),

        html.Div(id='onload-div'), # To trigger first callback
    ],
    id='main-content-pane',
    )

    return dbc.Container(mapview, fluid=False, id='app-layout-wrapper',)

def sprake_model_set_gen_input(gen_input: dict, mdl: sprakemodel.SprakeModel):
    turbine_size = mdl.generation.generator.generators[0].turbine.nameplate_capacity
    n_turbines = gen_input.get('wind_capacity', 0.0) / turbine_size
    
    pv_size = mdl.generation.generator.generators[1].pv_array.nameplate_capacity
    n_arrays = gen_input.get('pv_capacity', 0.0) / pv_size

    mdl.generation.generator.generators[0].n_turbines = n_turbines
    mdl.generation.generator.generators[1].n_arrays = n_arrays
    
    mdl.generation.dirty = True

def sprake_model_set_stor_input(stor_input: dict, mdl: sprakemodel.SprakeModel):
    mdl.consumption_storage.set_storage_params(stor_input.copy())
    # consumption storage will be dirtied by this method

def sprake_model_set_bc_input(bc_input: dict, mdl: sprakemodel.SprakeModel):
    cs = mdl.consumption_storage
    spaceheat_p = cs.spaceheat_params
    dhw_p = cs.dhw_params

    cs.n_units = bc_input.get('n_units', 1.0)
    spaceheat_p['hlp'] = bc_input.get('hlp', 1.1)
    spaceheat_p['gfa'] = bc_input.get('gfa', 1.0)
    dhw_p['ref_daily_consumption'] = bc_input.get('ref_daily_consumption', 0.0)
    dhw_p['seasonal_variance'] = bc_input.get('seasonal_variance', 0.01)
    cs.dirty = True

def sprake_model_set_dc_input(dc_input: dict, mdl: sprakemodel.SprakeModel):
    cs = mdl.consumption_storage
    app_p = cs.appliance_params
    ev_p = cs.ev_params

    app_p['efficiency_reduction'] = dc_input.get('efficiency_reduction', 0.0)
    ev_p['annual_residential_consumption_per_ev'] = dc_input.get('annual_residential_consumption_per_ev', 0.0)
    ev_p['n_evs'] = dc_input.get('n_evs_per_household', 0.0) * cs.n_units
    cs.dirty = True

def sprake_model_set_mc_input(mc_input: dict, mdl: sprakemodel.SprakeModel):
    ts = mdl.get_run_period()
    ts.end = ts.start + pd.Timedelta(mc_input.get('horizon',1)*365, unit='d') 
    while ts.end.day != ts.start.day:
        ts.end = ts.end + pd.Timedelta(1, unit='d')
    mdl.set_run_period(ts)

def sprake_model_set_loc_input(loc_input: dict, mdl: sprakemodel.SprakeModel):
    loc_0 = mdl.location
    loc = location.Location(
        loc_input.get('lat', loc_0.lat),
        loc_input.get('lon', loc_0.lon),
        name = loc_input.get('name', loc_0.name)
    )
    mdl.location = loc

def sprake_finance_set_finance_config(fcfg: dict, fnc: sprakefinance.SprakeFinance):
    fnc.set_unit_costs_from_dict(fcfg.get('unit_costs'))
    fnc.benefit_discount_rate = float(fcfg.get('benefit_discount_rate', 0.0) / 100)
    fnc.cost_discount_rate = float(fcfg.get('cost_discount_rate', 0.0) / 100)

def sprake_finance_to_interface_config(
    fnc: sprakefinance.SprakeFinance,
) -> dict:
    fcfg = fnc.to_dict()
    fcfg['benefit_discount_rate'] *= 100.
    fcfg['cost_discount_rate'] *= 100.
    fcfg['finance_uuid'] = fnc.uuid

    return fcfg

def sprake_model_to_local_model_config(
    mdl: sprakemodel.SprakeModel
) -> dict:
    gen_input = {
        'wind_capacity': mdl.generation.generator.generators[0].nameplate_capacity,
        'pv_capacity': mdl.generation.generator.generators[1].nameplate_capacity
    }

    cs = mdl.consumption_storage

    stor_input = cs.storage_params

    spaceheat_p = cs.spaceheat_params
    dhw_p = cs.dhw_params
    app_p = cs.appliance_params
    ev_p = cs.ev_params

    bc_input = {
        'n_units': cs.n_units,
        'hlp': spaceheat_p.get('hlp'),
        'gfa': spaceheat_p.get('gfa'),
        'ref_daily_consumption': dhw_p.get('ref_daily_consumption'),
        'seasonal_variance': dhw_p.get('seasonal_variance')
    }

    dc_input = {
        'efficiency_reduction': app_p.get('efficiency_reduction'),
        'annual_residential_consumption_per_ev': \
            ev_p.get('annual_residential_consumption_per_ev'),
        'n_evs_per_household': ev_p.get('n_evs') / cs.n_units
    }

    # Model config

    # Note that we are only going to allow horizons in multiples
    # of one year. I may allow the start date to vary later.
    # As such, we are just going to take the horizon to be the
    # difference in year between the start and end of the timespan
    ts = mdl.get_run_period()
    mc_input = {
        'horizon': ts.end.year - ts.start.year
    }

    # Location config
    loc = mdl.location
    loc_input = {
        'lat': loc.lat,
        'lon': loc.lon,
        'name': loc.name
    }

    mcfg = {
        'model_uuid': mdl.uuid,
        'gen_input': gen_input,
        'stor_input': stor_input,
        'bc_input': bc_input,
        'dc_input': dc_input,
        'mc_input': mc_input,
        'loc_input': loc_input,
    }

    return mcfg

def sprake_model_to_interface_configs(
    mdl: sprakemodel.SprakeModel, 
    fnc: sprakefinance.SprakeFinance,
) -> Tuple[dict, dict]:
    gen_input = {
        'wind_capacity': mdl.generation.generator.generators[0].nameplate_capacity,
        'pv_capacity': mdl.generation.generator.generators[1].nameplate_capacity
    }

    cs = mdl.consumption_storage

    stor_input = cs.storage_params

    spaceheat_p = cs.spaceheat_params
    dhw_p = cs.dhw_params
    app_p = cs.appliance_params
    ev_p = cs.ev_params

    bc_input = {
        'n_units': cs.n_units,
        'hlp': spaceheat_p.get('hlp'),
        'gfa': spaceheat_p.get('gfa'),
        'ref_daily_consumption': dhw_p.get('ref_daily_consumption'),
        'seasonal_variance': dhw_p.get('seasonal_variance')
    }

    dc_input = {
        'efficiency_reduction': app_p.get('efficiency_reduction'),
        'annual_residential_consumption_per_ev': \
            ev_p.get('annual_residential_consumption_per_ev'),
        'n_evs_per_household': ev_p.get('n_evs') / cs.n_units
    }

    # Model config

    # Note that we are only going to allow horizons in multiples
    # of one year. I may allow the start date to vary later.
    # As such, we are just going to take the horizon to be the
    # difference in year between the start and end of the timespan
    ts = mdl.get_run_period()
    mc_input = {
        'horizon': ts.end.year - ts.start.year
    }

    # Location config
    loc = mdl.location
    loc_input = {
        'lat': loc.lat,
        'lon': loc.lon,
        'name': loc.name
    }

    mcfg = {
        'model_uuid': mdl.uuid,
        'gen_input': gen_input,
        'stor_input': stor_input,
        'bc_input': bc_input,
        'dc_input': dc_input,
        'mc_input': mc_input,
        'loc_input': loc_input,
    }

    fcfg = sprake_finance_to_interface_config(fnc)

    return mcfg, fcfg

def add_initial_callback(app):
    """
    Functions to synchronise app interface with the served model
    """
    @app.callback(
        Output('firstload-config-watcher', 'data'),
        Input('onload-div', 'children')
    )
    def sync_config_init(_):
        return json.dumps(str(datetime.datetime.now()))

    clientside_callback(
        ClientsideFunction(
            namespace='clientside',
            function_name = 'attach_drawer'
        ),
        Output('post-drawer-attach', 'children'),
        Input('onload-div', 'children')
    )

    @app.callback(
        Output('store-model-completed-run', 'data', allow_duplicate = True),
        Input('model-config-watcher', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True,
        #background = True,
        #manager = background_callback_manager,
    )
    def trigger_mdl_run(_, selected_config):
        """Config change - run the model now"""
        # print (ctx.triggered)

        NUP = no_update
        if selected_config is None:
            return NUP
        selected_config = json.loads(selected_config)
        mdl = models.get(selected_config['model_uuid'], None)
        if mdl is None:
            return NUP

        print('Starting normally triggered run')
        mdl_hash = mdl.run()
        print('Normal run complete')

        return json.dumps(
            {
                'model_uuid': mdl.uuid,
                'model_last_run': str(mdl.last_run),
                'model_hash': mdl_hash
            }
        )

    @app.callback(
        Output('finance-config-watcher', 'data', allow_duplicate=True),
        Input('store-model-completed-run', 'data'),
        State('store-configurations', 'data'),
        prevent_initial_call = True
    )
    def trigger_financial_results_post_run(model_run, configurations):
        NUP = no_update
        if model_run is None or configurations is None:
            return NUP
        model_run = json.loads(model_run)
        configurations = json.loads(configurations)
        model_uuid = model_run['model_uuid']
        olist = []
        for i, conf in enumerate(configurations):
            if conf['model_uuid'] == model_uuid:
                olist.append({
                    'config_index': i,
                    'finance_uuid': conf['finance_uuid'],
                    'model_uuid': model_uuid
                })
        return json.dumps(olist)
    
    @app.callback(
        Output('store-selected-configuration', 'data', allow_duplicate = True),
        Output('store-configurations', 'data', allow_duplicate = True),
        Output('model-config', 'data', allow_duplicate=True),
        Output('finance-config', 'data', allow_duplicate=True),
        Input('firstload-config-watcher', 'data'),
        #Input('live-config-watcher', 'data'),
        Input('store-selected-configuration', 'data'),
        State('store-configurations', 'data'),
        prevent_initial_call=True
    )
    def sync_config(_, selected_config, all_configs):
        # print ('Active configuration has been changed')
        # print (ctx.triggered)
        if selected_config is None:
            if all_configs is None:
                # On first load, we can generate a random configuration
                all_configs = [compose_configuration(
                    'Configuration Name',
                    str(uuid.uuid4()),
                    str(uuid.uuid4())
                )]
            else:
                all_configs = json.loads(all_configs)
            selected_config = all_configs[0].copy()
            selected_config['config_index'] = 0
        else:
            selected_config = json.loads(selected_config)
            all_configs = json.loads(all_configs)
        
        mdl = models.get(selected_config['model_uuid'], None)
        if mdl is None:
            # TODO: Deal with if the model should exist.
            # Need to recreate it from the local store.
            mdl = create_default_model()
            mdl.uuid = selected_config['model_uuid']
            models[mdl.uuid] = mdl
        
        fnc = finances.get(selected_config['finance_uuid'], None)
        if fnc is None:
            # TODO: Deal with if the finance should exist.
            # Need to recreate it from the local store.
            fnc = create_default_finance()
            fnc.uuid = selected_config['finance_uuid']
            fnc.set_model(mdl)
            finances[fnc.uuid] = fnc
        
        mcfg, fcfg = sprake_model_to_interface_configs(mdl, fnc)

        return (
            json.dumps(selected_config),
            json.dumps(all_configs),
            json.dumps(mcfg),
            json.dumps(fcfg)
        )
    
    @app.callback(
        Output('site-location', 'data', allow_duplicate = True),
        Input('model-config', 'data'),
        prevent_initial_call=True
    )
    def sync_loc_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update
        mcfg = json.loads(mcfg)
        loc_input = mcfg.get('loc_input', None)
        return json.dumps(loc_input)

    @app.callback(
        Output('gen-smry-wind-cap', 'children'),
        Output('gen-smry-pv-cap', 'children'),
        Output({'type': 'input-model-config', 'section': 'gen_input', 'key': 'wind_capacity'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'gen_input', 'key': 'pv_capacity'}, 'value'),
        Input('model-config', 'data'),
        prevent_initial_call=True
    )
    def sync_gen_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update, no_update, no_update, no_update
        mcfg = json.loads(mcfg)
        gen_input = mcfg.get('gen_input', {})
        return (
            f"{gen_input.get('wind_capacity', 0.0):,.1f}",
            f"{gen_input.get('pv_capacity', 0.0):,.1f}",
            gen_input.get('wind_capacity', 0.0),
            gen_input.get('pv_capacity', 0.0)
        )

    @app.callback(
        Output('stor-smry-cap', 'children'),
        Output({'type': 'input-model-config', 'section': 'stor_input', 'key': 'storage_capacity'}, 'value'),
        Input('model-config','data'),
        prevent_initial_call=True
    )
    def sync_stor_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update, no_update
        mcfg = json.loads(mcfg)
        stor_input = mcfg.get('stor_input', {})
        return (
            f"{stor_input.get('storage_capacity', 0.0):,.0f}",
            stor_input.get('storage_capacity', 0.0)
        )

    @app.callback(
        Output('bc-smry-n-units', 'children'),
        Output({'type': 'input-model-config', 'section': 'bc_input', 'key': 'n_units'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'bc_input', 'key': 'hlp'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'bc_input', 'key': 'gfa'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'bc_input', 'key': 'ref_daily_consumption'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'bc_input', 'key': 'seasonal_variance'}, 'value'),
        Input('model-config', 'data'),
        prevent_initial_call=True
    )
    def sync_bc_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update, no_update, no_update, no_update, no_update, no_update
        mcfg = json.loads(mcfg)
        bc_input = mcfg.get('bc_input', {})
        return (
            f"{bc_input.get('n_units', 0):,.0f}",
            bc_input.get('n_units', 0),
            bc_input.get('hlp', 0),
            bc_input.get('gfa', 0),
            bc_input.get('ref_daily_consumption', 0),
            bc_input.get('seasonal_variance', 0)
        )

    @app.callback(
        Output({'type': 'input-model-config', 'section': 'dc_input', 'key': 'efficiency_reduction'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'dc_input', 'key': 'annual_residential_consumption_per_ev'}, 'value'),
        Output({'type': 'input-model-config', 'section': 'dc_input', 'key': 'n_evs_per_household'}, 'value'),
        Output('cons-smry-app','children'),
        Output('cons-smry-ev','children'),
        Input('model-config', 'data'),
        prevent_initial_call=True
    )
    def sync_dc_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update, no_update, no_update, no_update, no_update
        mcfg = json.loads(mcfg)
        dc_input = mcfg.get('dc_input', {})
        ann_appliance = (
            (1.0 - float(dc_input.get('efficiency_reduction', 0))) * MODEL_CONSTANTS['sprake_model']['sprake_ref_appliance_consumption_annual']
        )
        ann_ev = (
            dc_input.get('n_evs_per_household', 0) * dc_input.get('annual_residential_consumption_per_ev', 0)
        )
        return (
            dc_input.get('efficiency_reduction', 0),
            dc_input.get('annual_residential_consumption_per_ev', 0),
            dc_input.get('n_evs_per_household', 0),
            '{:,.0f}'.format(ann_appliance),
            '{:,.0f}'.format(ann_ev)
        )

    @app.callback(
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'wind_capex_per_kw'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'wind_om_per_kw_year'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'pv_capex_per_kw'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'pv_om_per_kw_year'}, 'value'),
        Output('cost-gen-smry-capex', 'children'),
        Output('cost-gen-smry-ongoing', 'children'),
        Input('model-config', 'data'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_cost_gen_inputs_to_store(mcfg, fcfg):
        if fcfg is None or mcfg is None:
            return no_update, no_update, no_update, no_update, no_update, no_update
        mcfg = json.loads(mcfg)
        fcfg = json.loads(fcfg)
        gen_input = mcfg.get('gen_input', {})
        uc = fcfg.get('unit_costs', {})
        wind_cap = gen_input.get('wind_capacity', 0.0)
        pv_cap = gen_input.get('pv_capacity', 0.0)
        tot_capex = (
            uc.get('wind_capex_per_kw', 0) * wind_cap
            + uc.get('pv_capex_per_kw', 0) * pv_cap
        )
        tot_ongoing = (
            uc.get('wind_om_per_kw_year', 0) * wind_cap
            + uc.get('pv_om_per_kw_year', 0) * pv_cap
        )
        return (
            uc.get('wind_capex_per_kw', 0),
            uc.get('wind_om_per_kw_year', 0),
            uc.get('pv_capex_per_kw', 0),
            uc.get('pv_om_per_kw_year', 0),
            '{:,.0f}'.format(tot_capex),
            '{:,.0f}'.format(tot_ongoing)
        )

    @app.callback(
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'bess_capex_per_kwh'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'bess_om_per_kwh_year'}, 'value'),
        Output('cost-stor-smry-capex', 'children'),
        Output('cost-stor-smry-ongoing', 'children'),
        Input('model-config', 'data'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_cost_stor_inputs_to_store(mcfg, fcfg):
        if fcfg is None or mcfg is None:
            return no_update, no_update, no_update, no_update
        mcfg = json.loads(mcfg)
        fcfg = json.loads(fcfg)
        stor_input = mcfg.get('stor_input', {})
        uc = fcfg.get('unit_costs', {})
        bess_cap = stor_input.get('storage_capacity', 0.0)
        tot_capex = bess_cap * uc.get('bess_capex_per_kwh', 0)
        tot_ongoing = bess_cap * uc.get('bess_om_per_kwh_year', 0)
        return (
            uc.get('bess_capex_per_kwh', 0),
            uc.get('bess_om_per_kwh_year', 0),
            '{:,.0f}'.format(tot_capex),
            '{:,.0f}'.format(tot_ongoing)
        )

    @app.callback(
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'resident_sc_per_unit_day'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'resident_var_per_unit'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'grid_export_var_per_unit'}, 'value'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_cost_sales_inputs_to_store(fcfg):
        if fcfg is None:
            return no_update, no_update, no_update
        fcfg = json.loads(fcfg)
        uc = fcfg.get('unit_costs', {})
        return (
            uc.get('resident_sc_per_unit_day', 0),
            uc.get('resident_var_per_unit', 0),
            uc.get('grid_export_var_per_unit', 0)
        )

    @app.callback(
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'grid_import_sc_per_day'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': 'grid_import_var_per_unit'}, 'value'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_cost_imports_inputs_to_store(fcfg):
        if fcfg is None:
            return no_update, no_update
        fcfg = json.loads(fcfg)
        uc = fcfg.get('unit_costs', {})
        return (
            uc.get('grid_import_sc_per_day', 0),
            uc.get('grid_import_var_per_unit', 0)
        )

    @app.callback(
        Output('mdl-smry-horizon', 'children'),
        Output({'type': 'input-model-config', 'section': 'mc_input', 'key': 'horizon'}, 'value'),
        Input('model-config', 'data'),
        prevent_initial_call=True
    )
    def sync_mc_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update, no_update
        mcfg = json.loads(mcfg)
        mc_input = mcfg.get('mc_input', {})
        return (
            f"{mc_input.get('horizon', 1):.0f}",
            mc_input.get('horizon', 1)
        )

    @app.callback(
        Output('fnc-smry-benefit-dr', 'children'),
        Output('fnc-smry-cost-dr', 'children'),
        Output({'type': 'input-finance-config', 'section': 'None', 'key': 'benefit_discount_rate'}, 'value'),
        Output({'type': 'input-finance-config', 'section': 'None', 'key': 'cost_discount_rate'}, 'value'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_fnc_inputs_to_store(fcfg):
        if fcfg is None:
            return no_update, no_update, no_update, no_update
        fcfg = json.loads(fcfg)
        return (
            f"{fcfg.get('benefit_discount_rate', 0.0):,.1%}",
            f"{fcfg.get('cost_discount_rate', 0.0):,.1%}",
            100.*fcfg.get('benefit_discount_rate', 0.0),
            100.*fcfg.get('cost_discount_rate', 0.0)
        )

    @app.callback(
        Output('res-gen-wind-tbl', 'children'),
        Output('res-gen-pv-tbl', 'children'),
        Output('res-gen-combined-tbl', 'children'),
        Input('res-gen', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_gen_results_to_store(res, ann_hori_toggle):
        if res is None:
            return no_update, no_update, no_update
        res = json.loads(res)
        return (
            create_wind_results(res, not(ann_hori_toggle)),
            create_pv_results(res, not(ann_hori_toggle)),
            create_combined_generation_results(res, not(ann_hori_toggle))
        )

    @app.callback(
        Output('res-stor-tbl', 'children'),
        Input('res-stor', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_stor_results_to_store(res, ann_hori_toggle):
        if res is None:
            return no_update
        res = json.loads(res)
        return create_stor_results(res, not(ann_hori_toggle))        

    @app.callback(
        Output('res-cons-tbl', 'children'),
        Output('res-cons-seasonal-tbl', 'children'),
        Input('res-cons', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_cons_results_to_store(res, ann_hori_toggle):
        if res is None:
            return no_update, no_update
        res = json.loads(res)
        return create_cons_results(res, not(ann_hori_toggle)), create_seasonal_cons_results(res, not(ann_hori_toggle))

    @app.callback(
        Output('res-net-tbl', 'children'),
        Output('res-net-seasonal-tbl', 'children'),
        Input('res-net', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_net_results_to_store(net, ann_hori_toggle):
        if net is None:
            return no_update, no_update
        net = json.loads(net)
        return (
            create_net_results(net, not(ann_hori_toggle)), 
            create_seasonal_net_results(net, not(ann_hori_toggle))
        )

    @app.callback(
        Output('res-finance-so-benefits-tbl', 'children'),
        Output('cost-sales-smry-residents', 'children'),
        Output('cost-sales-smry-export', 'children'),
        Input('res-finance-so-benefits', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def sync_fnc_so_benefits_to_store(fnc, ann_hori_toggle, selected_config):
        if fnc is None:
            return no_update, no_update, no_update
        fnc = json.loads(fnc)
        selected_config = json.loads(selected_config)
        config_index = selected_config['config_index']
        if fnc is None:
            return no_update, no_update, no_update
        bnfts = create_so_benefits_results(fnc, not(ann_hori_toggle))
        return (
            bnfts,
            '{:,.0f}'.format(fnc[config_index].get('smry_residential_peryear')),
            '{:,.0f}'.format(fnc[config_index].get('smry_exports_peryear')),
        )
    
    @app.callback(
        Output('res-finance-so-costs-tbl', 'children'),
        Output('cost-import-smry-fixed', 'children'),
        Output('cost-import-smry-ongoing', 'children'),
        Input('res-finance-so-costs', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def sync_fnc_so_costs_to_store(fnc, ann_hori_toggle, selected_config):
        if fnc is None:
            return no_update, no_update, no_update
        fnc = json.loads(fnc)
        selected_config = json.loads(selected_config)
        config_index = selected_config['config_index']
        if fnc is None:
            return no_update, no_update, no_update
        return (
            create_so_costs_results(fnc, not(ann_hori_toggle)),
            '{:,.0f}'.format(fnc[config_index].get('smry_import_fixed_cost_peryear')),
            '{:,.0f}'.format(fnc[config_index].get('smry_import_variable_cost_peryear'))
        )

    @app.callback(
        Output('res-finance-so-value-tbl', 'children'),
        Input('res-finance-so-value', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_fnc_so_value_to_store(fnc, ann_hori_toggle):
        if fnc is None:
            return no_update
        fnc = json.loads(fnc)
        if fnc is None:
            return no_update
        return create_so_value_results(fnc, not(ann_hori_toggle))

    return app

RESULT_CACHE_PREFIXES = {
    'generation': 'res_gen_',
    'storage': 'res_stor_',
    'consumption': 'res_cons_',
    'net_energy': 'res_net_'
}

def generic_model_postprocess(
    model_run_json,
    postprocess_function,
    result_id_prefix
):
    """
    Run a postprocess function on a model and store in the results cache.
    """
    NUP = no_update
    if model_run_json is None:
        return NUP
    
    model_run = json.loads(model_run_json)
    model_id = model_run['model_id']
    mdl = get_model(model_id)
    
    # Avoid recalculation if nothing has actually run
    run_hash = hash(mdl)
    result_id = result_id_prefix + str(model_id)
    prev_result = results.get(result_id, None)
    if not prev_result is None and prev_result['run_hash'] == run_hash:
        return NUP
    
    print (f"making {result_id_prefix}")
    gen_results = postprocess_function(mdl)
    gen_results['run_hash'] = run_hash
    results[result_id] = gen_results

    return model_run_json


def add_result_callbacks(app):
    """
    Callbacks to synchronise app interface with results of the model after run
    """

    @app.callback(
        Output('res-gen', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_gen(model_run_json):
        """
        Create the generation results for a completed model run.
        """
        return generic_model_postprocess(
            model_run_json,
            post_sprake_gen_results.gen_results_to_interface_sprake,
            RESULT_CACHE_PREFIXES['generation']
        )
    
    @app.callback(
        Output('res-stor', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_stor(model_run_json):
        """
        Create the storage results for a completed model run.
        """
        return generic_model_postprocess(
            model_run_json,
            post_sprake_storage_results.stor_results_to_interface_sprake,
            RESULT_CACHE_PREFIXES['storage']
        )
    
    @app.callback(
        Output('res-cons', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_cons(model_run_json):
        """
        Create the consumption results for a completed model run.
        """
        return generic_model_postprocess(
            model_run_json,
            post_sprake_consumption_results.consumption_results_to_interface_sprake,
            RESULT_CACHE_PREFIXES['consumption']
        )

    @app.callback(
        Output('res-cons', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_cons(model_run_json):
        """
        Create the net energy results for a completed model run.
        """
        return generic_model_postprocess(
            model_run_json,
            post_sprake_net_results.net_results_to_interface_sprake,
            RESULT_CACHE_PREFIXES['net_energy']
        )

    @app.callback(
        Output('res-finance-so-benefits', 'data'),
        Input('finance-config-watcher', 'data'),
        State('store-configurations', 'data'),
        State('res-finance-so-benefits', 'data'),
        prevent_initial_call=True
    )
    def set_res_finance_benefits_so(finance_to_refresh, configurations, res_ben):
        """
        Create the system owner financial benefits results after a completed model run.
        """
        NUP = no_update
        if finance_to_refresh is None or configurations is None:
            return NUP
        finance_to_refresh = json.loads(finance_to_refresh)
        configurations = json.loads(configurations)

        if res_ben is None:
            res_ben = [None] * len(configurations)
        else:
            res_ben = json.loads(res_ben)
            if len(res_ben) < len(configurations):
                res_ben += [None] * (len(configurations) - len(res_ben))

        for ftr in finance_to_refresh:
            mdl = models.get(ftr['model_uuid'])
            fnc = finances.get(ftr['finance_uuid'])
            if mdl is None or fnc is None:
                next
            print ("making so financial benefits results")
            fnc_benefits_results = (
                post_sprake_finance_benefits_results
                .finance_benefits_results_to_interface_sprake(mdl,fnc)
            )
            res_ben[ftr['config_index']] = fnc_benefits_results
        
        return json.dumps(res_ben)
    
    @app.callback(
        Output('res-finance-so-costs', 'data'),
        Input('finance-config-watcher', 'data'),
        State('store-configurations', 'data'),
        State('res-finance-so-costs', 'data'),
        prevent_initial_call=True
    )
    def set_res_finance_costs_so(finance_to_refresh, configurations, res_cost):
        """
        Create the system owner financial costs results after a completed model run.
        """
        NUP = no_update
        if finance_to_refresh is None or configurations is None:
            return NUP
        finance_to_refresh = json.loads(finance_to_refresh)
        configurations = json.loads(configurations)

        if res_cost is None:
            res_cost = [None] * len(configurations)
        else:
            res_cost = json.loads(res_cost)
            if len(res_cost) < len(configurations):
                res_cost += [None] * (len(configurations) - len(res_cost))
        
        for ftr in finance_to_refresh:
            mdl = models.get(ftr['model_uuid'])
            fnc = finances.get(ftr['finance_uuid'])
            if mdl is None or fnc is None:
                next
            print ("making so financial costs results")
            fnc_costs_results = (
                post_sprake_finance_costs_results
                .finance_costs_results_to_interface_sprake(mdl,fnc)
            )
            res_cost[ftr['config_index']] = fnc_costs_results
        
        return json.dumps(res_cost)

    @app.callback(
        Output('res-finance-so-value', 'data'),
        Input('finance-config-watcher', 'data'),
        State('store-configurations', 'data'),
        State('res-finance-so-value', 'data'),
        prevent_initial_call=True
    )
    def set_res_finance_value_so(finance_to_refresh, configurations, res_value):
        """
        Create the system owner financial value results after a completed model run.
        """
        NUP = no_update
        if finance_to_refresh is None or configurations is None:
            return NUP
        finance_to_refresh = json.loads(finance_to_refresh)
        configurations = json.loads(configurations)

        if res_value is None:
            res_value = [None] * len(configurations)
        else:
            res_value = json.loads(res_value)
            if len(res_value) < len(configurations):
                res_value += [None] * (len(configurations) - len(res_value))

        for ftr in finance_to_refresh:
            mdl = models.get(ftr['model_uuid'])
            fnc = finances.get(ftr['finance_uuid'])
            if mdl is None or fnc is None:
                next
            print ("making so financial value results")
            fnc_value_results = (
                post_sprake_finance_value_results
                .finance_value_results_to_interface_sprake(mdl,fnc)
            )
            res_value[ftr['config_index']] = fnc_value_results
        
        return json.dumps(res_value)

    return app

def add_result_header_callbacks(app):
    
    @app.callback(
        Output('gen-ressmry-container', 'children'),
        Input('res-gen', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_generation_results_header(
        res_trigger, 
        ann_hori_toggle, 
        selected_config
    ):
        NUP = no_update
        
        selected_config = json.loads(selected_config)
        model_id = selected_config['model_uuid']
        res_id = RESULT_CACHE_PREFIXES['generation'] + str(model_id)
        res = results.get(res_id)
        if res is None:
            return NUP

        gm = res.get('generator_meter_summary')
        
        if ann_hori_toggle:
            str_1 = 'Total generation: '
            wind_ann = gm.get('wind_export').get('sum')
            pv_ann = gm.get('solar_export').get('sum')
            total_ann = wind_ann + pv_ann
        else:
            str_1 = 'Annual generation: '
            wind_ann = gm.get('wind_export').get('mean')
            pv_ann = gm.get('solar_export').get('mean')
            total_ann = wind_ann + pv_ann
        
        return [
            str_1,
            get_icon('generation'),
            " = ",
            html.Span(f'{total_ann:,.1f}'),
            " kWh; ",
            get_icon('gen-wind'),
            " = ",
            html.Span(f'{wind_ann:,.1f}'),
            " kWh; ",
            get_icon('gen-pv'),
            " = ",
            html.Span(f'{pv_ann:,.1f}'),
            " kWh"
        ]

    @app.callback(
        Output('stor-ressmry-container', 'children'),
        Input('res-stor', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_storage_results_header(
        res_trigger, 
        ann_hori_toggle,
        selected_config
    ):
        NUP = no_update

        selected_config = json.loads(selected_config)
        model_id = selected_config['model_uuid']
        res_id = RESULT_CACHE_PREFIXES['storage'] + str(model_id)
        res = results.get(res_id)
        if res is None:
            return NUP

        hrs_full = res.get('stor_hours_at_max').get('hrs_at_max_soc')
        hrs_empty = res.get('stor_hours_at_min').get('hrs_at_min_soc')
        cc = res.get('no_charge_cycles').get('charge_cycles')
        
        if ann_hori_toggle:
            stat='sum'
        else:
            stat='mean'
        
        hrs_full = hrs_full.get(stat)
        hrs_empty = hrs_empty.get(stat)
        cc = cc.get(stat)

        return [
            'Hours full = ',
            html.Span(f'{hrs_full:,.0f}'),
            "; Hours empty = ",
            html.Span(f'{hrs_empty:,.0f}'),
            "; Charge cycles = ",
            html.Span(f'{cc:,.0f}')
        ]

    @app.callback(
        Output('cons-ressmry-container', 'children'),
        Input('res-cons', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_consumption_results_header(
        res_trigger, 
        ann_hori_toggle, 
        selected_config
    ):
        NUP = no_update
        
        selected_config = json.loads(selected_config)
        model_id = selected_config['model_uuid']
        res_id = RESULT_CACHE_PREFIXES['consumption'] + str(model_id)
        res = results.get(res_id)
        if res is None:
            return NUP
        
        if ann_hori_toggle:
            str_1 = 'Total consumption: '
            stat='sum'
        else:
            str_1 = 'Annual consumption: '
            stat='mean'
        residential_cons = res.get('consumption_meter_summaries').get('residential').get(stat)
        ev_cons = res.get('consumption_meter_summaries').get('evcharge_import').get(stat)

        return [
            str_1,
            get_icon('consumption-building'),
            ' = ',
            html.Span(f'{residential_cons:,.1f}'),
            ' kWh; ',
            get_icon('consumption-direct-ev'),
            ' = ',
            html.Span(f'{ev_cons:,.1f}'),
            ' kWh'                
        ]

    @app.callback(
        Output('net-ressmry-container', 'children'),
        Input('res-net', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_net_results_header(
        res_trigger,
        ann_hori_toggle,
        selected_config
    ):
        NUP = no_update
        
        selected_config = json.loads(selected_config)
        model_id = selected_config['model_uuid']
        res_id = RESULT_CACHE_PREFIXES['net_energy'] + str(model_id)
        res = results.get(res_id)
        if res is None:
            return NUP

        if ann_hori_toggle:
            str_1 = 'Total export = '
            str_2 = 'Total import = '
            stat = 'sum'
        else:
            str_1 = 'Annual export = '
            str_2 = 'Annual import = '
            stat = 'mean'
        
        ms = (
            pd.DataFrame
            .from_dict(res['meter_summaries'], orient='columns')
            .set_index(['variable', 'statistic'])
        )
        energy_export = ms.loc[('grid_export',stat),'value']
        energy_import = ms.loc[('grid_import',stat),'value']
        storage_loss = ms.loc[('storage_loss',stat),'value']

        return [
            str_1,
            html.Span(f'{energy_export:,.1f}'),
            ' kWh; ',
            str_2,
            html.Span(f'{energy_import:,.1f}'),
            ' kWh; Storage losses = ',
            html.Span(f'{storage_loss:,.1f}'),
            ' kWh'
        ]

    @app.callback(
        Output('finance-ressmry-container', 'children'),
        Input('res-finance-so-benefits', 'data'),
        Input('res-finance-so-costs', 'data'),
        Input('res-finance-so-value', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_finance_results_header(res_benefits, res_costs, res_value, selected_config):
        if (res_benefits is None) or (res_costs is None) or (res_value is None):
            return no_update
        
        res_benefits = json.loads(res_benefits)
        res_costs = json.loads(res_costs)
        res_value = json.loads(res_value)

        selected_config = json.loads(selected_config)
        config_index = selected_config['config_index']

        if isinstance(res_benefits, list):
            res_benefits = res_benefits[config_index]
        if isinstance(res_costs, list):
            res_costs = res_costs[config_index]
        if isinstance(res_value, list):
            res_value = res_value[config_index]

        dr_benefits = res_benefits.get('benefits_discount_rate')
        prval_benefits = res_benefits.get('present_benefits_discounted')
        dr_costs = res_costs.get('costs_discount_rate')
        prval_costs = res_costs.get('present_costs_discounted')
        value = (
            pd.DataFrame
            .from_dict(res_value.get('value_summaries'), orient='columns')
            .set_index(['variable', 'statistic'])
        )
        npv = value.loc[('net_present_value_discounted','sum'),'value']

        return [
            'Total benefits (',
            html.Span(f'{dr_benefits:,.1%}'),
            ') = ',
            html.Span(f'£{prval_benefits:,.2f}'),
            '; Total costs (',
            html.Span(f'{dr_costs:,.1%}'),
            ') = ',
            html.Span(f'£{prval_costs:,.2f}'),
            '; NPV = ',
            html.Span(f'£{npv:,.2f}'),
        ]

    return app

def add_input_callbacks(app):
    """
    Functions to synchronise configurations with inputs.
    """

    @app.callback(
        Input('trigger-post-model-run', 'data'),
        prevent_initial_call = True
    )
    def model_run_postprocess(model_run):
        """
        Postprocess and trigger updates from a completed model run.

        A completed model run should result in the following actions:
        1. For any configuration where the finance is associated with this 
           model, queue up a finance run.
        2. If the model is the model of the selected configuration, update the
           main results.
        3. Update the model results in the View.
        """
        return 

    @app.callback(
        Output('trigger-postprocess-finance-run', 'data'),
        Output('latch-finances-checkedout', 'data', allow_duplicate = True),
        Output('latch-finance-run-global', 'data', allow_duplicate = True),
        Input('trigger-post-finance-run', 'data'),
        State('latch-finances-checkedout', 'data'),
        prevent_initial_call = True
    )
    def receiver_finance_run(
        trigger_post_finance_run,
        latch_finances_checkedout
    ):
        """
        After a (background) finance run completes, resync the local finance.
        """
        finance_run = json.loads(trigger_post_finance_run)
        finance_id = finance_run['finance_id']

        # Sync with background cache
        finances[finance_id] = finance_from_cache(finance_id)
        # Ensure model is correct
        finances[finance_id].model = get_model(finance_run['model_id'])

        # Clear finance for editing
        latch_finances_checkedout = set(json.loads(latch_finances_checkedout))
        latch_finances_checkedout.remove(finance_id)

        print('finance run did complete')
        print(finance_run)

        return (
            trigger_post_finance_run,
            json.dumps(list(latch_finances_checkedout)),
            True,
        )

    @app.callback(
        Output('trigger-post-finance-run', 'data'),
        Input('trigger-finance-run', 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager
    )
    def run_finance(finance_run_request):
        finance_run = json.loads(finance_run_request)
        model_id = finance_run['model_id']
        finance_id = finance_run['finance_id']
        mdl = model_from_cache(model_id)

        fnc = finance_from_cache(finance_id)
        # Suspect that if we don't do this, things will rapidly break
        # unless the pickle serialises the model for the finance
        # in which case, we may need to re-write the reduce function
        fnc.model = mdl

        # CREATE THE FINANCE RESULTS

        # SYNCRONISE THE FINANCE
        finances[finance_id] = fnc
        finance_to_cache(finance_id)
        
        return finance_run_request

    @app.callback(
        Output('latch-finances-checkedout', 'data', allow_duplicate = True),
        Output('latch-finance-run-global', 'data', allow_duplicate = True),
        Output('trigger-finance-run', 'data'),
        Input('dispatchitem-finance-run', 'data'),
        State('latch-finances-checkedout', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_finance_run(
        dispatchitem_finance_run,
        latch_finances_checkedout
    ):
        """
        Handle a finance run request.

        When a finance run request gets this far, it has been cleared for
        running (i.e. it has passed any latches). It can therefore be
        synchronised to the cache, soft-locked for configuration updates
        by adding it to the checked-out list, and the trigger of the background
        finance run can be fired.
        """
        if dispatchitem_finance_run is None:
            return no_update, no_update, no_update
        
        finance_run = json.loads(dispatchitem_finance_run)

        if isinstance(finance_run, list):
            raise TypeError('Cannot handle a list of finance run requests')
        
        if latch_finances_checkedout is None:
            latch_finances_checkedout = set()
        else:
            latch_finances_checkedout = set(json.loads(latch_finances_checkedout))
        
        # Model is synced to cache, but no need to lock
        model_to_cache(finance_run['model_id'])

        finance_to_cache(finance_run['finance_id'])
        latch_finances_checkedout.add(finance_run['finance_id'])

        return(
            json.dumps(list(latch_finances_checkedout)),
            False,
            dispatchitem_finance_run
        )

    @app.callback(
        Output('queue-finance-run', 'data'),
        Output('dispatchitem-finance-run', 'data'),
        Output('interval-finance-run', 'disabled'),
        Input('prequeue-finance-run', 'data'),
        Input('interval-finance-run', 'n_intervals'),
        State('latch-models-checkedout', 'data'),
        State('queue-finance-run', 'data'),
        prevent_initial_call = True,
    )
    def queueman_finance_run(
        prequeue_finance_run,
        interval_finance_run,
        latch_models_checkedout,
        queue_finance_run
    ):
        """
        Receives and dispatches finance runs.

        On receiving (a) finance run request(s) through the prequeue, adds
        it/them to the end of the finance run queue, after popping out any
        existing requests for that finance to run.
        The queue is then iterated through. If the finance is permitted to
        be run (no latches apply) then it shall be removed from the queue
        and dispatched.
        The interval-finance-fun is enabled if the queue is not empty, forcing
        a re-fire of this callback every second until the queue is cleared.
        """
        if not queue_finance_run:
            queue_finance_run = []
        else:
            queue_finance_run = json.loads(queue_finance_run)
        
        if ctx.triggered_id == 'prequeue-finance-run':
            requests = json.loads(prequeue_finance_run)
            if isinstance(requests, list):
                for finance_id in [x['finance_id'] for x in requests]:
                    remove_indexes = (
                        [i if x['finance_id']  == finance_id else None for i, x in enumerate(queue_finance_run)]
                        .sort(reverse = True)
                    )
                    if remove_indexes:
                        for i in remove_indexes:
                            queue_finance_run.pop(i)
                queue_finance_run += requests
            else:
                finance_id = requests['finance_id']
                remove_indexes = (
                    [i if x['finance_id']  == finance_id else None for i, x in enumerate(queue_finance_run)]
                    .sort(reverse = True)
                )
                if remove_indexes:
                    for i in remove_indexes:
                        queue_finance_run.pop(i)
                queue_finance_run.append(requests)

            if latch_models_checkedout is None:
                latch_models_checkedout = set()
            else:
                latch_models_checkedout = set(json.loads(latch_models_checkedout))
            
            for i, request in enumerate(queue_finance_run):
                # Cannot run if model is checked out
                if not request['model_id'] in latch_models_checkedout:
                    dispatch_request = queue_finance_run.pop(i)

                    return (
                        json.dumps(queue_finance_run),
                        json.dumps(dispatch_request),
                        len(queue_finance_run) == 0,
                    )
            
            return (
                json.dumps(queue_finance_run),
                no_update,
                len(queue_finance_run) == 0
            )

    @app.callback(
        Output('trigger-postprocess-model-run', 'data'),
        Output('latch-models-checkedout', 'data', allow_duplicate = True),
        Output('latch-model-run-global', 'data', allow_duplicate = True),
        Input('trigger-post-model-run', 'data'),
        State('latch-models-checkedout', 'data'),
        prevent_initial_call = True
    )
    def receiver_model_run(
        trigger_post_model_run,
        latch_models_checkedout
    ):
        """
        After a (background) model run completes, resync the local model.
        """
        model_run = json.loads(trigger_post_model_run)
        model_id = model_run['model_id']
        
        # Sync with background cache
        models[model_id] = model_from_cache(model_id)
        
        # Clear model for editing
        latch_models_checkedout = set(json.loads(latch_models_checkedout))
        latch_models_checkedout.remove(model_id)

        print('model run did complete')
        print(model_run)

        return (
            trigger_post_model_run,
            json.dumps(list(latch_models_checkedout)),
            True,
        )

    @app.callback(
        Output('trigger-post-model-run', 'data'),
        Input('trigger-model-run', 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager
    )
    def run_model(model_run_request):
        model_run = json.loads(model_run_request)
        model_id = model_run['model_id']
        mdl = model_from_cache(model_id)
        run_hash = mdl.run()
        # Simply because of how to_cache is written, need to place model in
        # local dict
        models[model_id] = mdl
        model_to_cache(model_id)
        return model_run_request

    @app.callback(
        Output('latch-models-checkedout', 'data', allow_duplicate = True),
        Output('latch-model-run-global', 'data', allow_duplicate = True),
        Output('trigger-model-run', 'data'),
        Input('dispatchitem-model-run', 'data'),
        State('latch-models-checkedout', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_model_run(
        dispatchitem_model_run,
        latch_models_checkedout,
    ):
        """
        Handle a model run request.

        When a model run request gets this far, it has been cleared for running
        (i.e. it has passed any latches). It can therefore be synchronised to 
        the cache, soft-locked for configuration updates by adding it to the
        checked-out list, and the trigger for the background model run can be 
        fired.
        """
        if dispatchitem_model_run is None:
            return no_update, no_update, no_update
        
        model_run = json.loads(dispatchitem_model_run)

        # No plan to handle a list of requests here
        if isinstance(model_run, list):
            raise TypeError('Cannot handle a list of model run requests.')
        
        if latch_models_checkedout is None:
            latch_models_checkedout = set() # Empty set, not dict
        else:
            latch_models_checkedout = set(json.loads(latch_models_checkedout))

        model_to_cache(model_run['model_id'])
        latch_models_checkedout.add(model_run['model_id'])

        print ('model dispatched to run')
        print (model_run)

        return (
            json.dumps(list(latch_models_checkedout)),
            False,
            dispatchitem_model_run,
        )

    @app.callback(
        Output('queue-model-run', 'data'),
        Output('dispatchitem-model-run', 'data'),
        Output('interval-model-run', 'disabled'),
        Input('prequeue-model-run', 'data'),
        Input('interval-model-run', 'n_intervals'),
        State('latch-model-run-global', 'data'),
        State('queue-model-run', 'data'),
        prevent_initial_call = True
    )
    def queueman_model_run(
        prequeue_model_run,
        interval_model_run,
        latch_model_run_global,
        queue_model_run
    ):
        """
        Receives and dispatches model runs.

        On receiving (a) model run request(s) through the prequeue, will add 
        it/them to the end of the model run queue, after popping out any 
        existing requests for those models to run.
        The queue is then iterated through. If the model is permitted to be
        run (no latches apply) then it shall be removed from the queue and
        dispatched.
        The interval-model-run is enabled if the queue is not empty, forcing a
        re-fire of this callback every second until the queue is cleared.
        """
        if not queue_model_run:
            queue_model_run = []
        else:
            queue_model_run = json.loads(queue_model_run)
        
        if ctx.triggered_id == 'prequeue-model-run':
            requests = json.loads(prequeue_model_run)
            if isinstance(requests, list):
                for model_id in [x['model_id'] for x in requests]:
                    remove_indexes = (
                        [i if x['model_id'] == model_id else None for i, x in enumerate(queue_model_run)]
                        .sort(reverse=True)
                    )
                    if remove_indexes:
                        for i in remove_indexes:
                            queue_model_run.pop(i)
                queue_model_run += requests
            else:
                model_id = requests['model_id']
                remove_indexes = (
                    [i if x['model_id'] == model_id else None for i, x in enumerate(queue_model_run)]
                    .sort(reverse=True)
                )
                if remove_indexes:
                    for i in remove_indexes:
                        queue_model_run.pop(i)
                queue_model_run.append(requests)
        
        print ('checking run latches')

        # Hope that this can be interpreted as a bool
        if latch_model_run_global is None:
            latch_model_run_global = True

        print(latch_model_run_global)

        if latch_model_run_global:
            for i, request in enumerate(queue_model_run):
                # There are no conditions, so we automatically run the first model
                dispatch_request = queue_model_run.pop(i)
                print('model run')
                print(dispatch_request)
                return (
                    json.dumps(queue_model_run),
                    json.dumps(dispatch_request),
                    len(queue_model_run) == 0
                )
        
        return (
            json.dumps(queue_model_run),
            no_update,
            len(queue_model_run) == 0
        )
    
    @app.callback(
        Output('store-model-interface-configurations', 'data'),
        Output('store-finance-interface-configurations', 'data'),
        Output('prequeue-model-run', 'data'),
        Output('prequeue-finance-run', 'data'),
        Input('dispatchitem-action-user', 'data'),
        State('store-model-interface-configurations', 'data'),
        State('store-finance-interface-configurations', 'data'),
        prevent_initial_call = True
    )
    def dispatcher_action_user(
        dispatchitem_action_user,
        store_model_interface_configurations,
        store_finance_interface_configurations,
    ):
        """
        Handle a user action.

        When a user action gets this far, it has been cleared for actioning
        (i.e. it has passed any latches). This means that if it is a local 
        model configuration change, that may now be applied into the local
        configuration dictionary and the local copy of the model updated.
        If we have a change to a model, then it will be necessary to queue
        the model for running.
        To allow processing of the queue efficiently, the dispatchitem-action-user
        may be a list of actions for a single model, finance, or configuration.
        All updates should be applied prior to the model run request being
        sent.
        """
        if dispatchitem_action_user is None:
            return no_update, no_update
        
        dispatchitem_action_user = json.loads(dispatchitem_action_user)
        if not isinstance(dispatchitem_action_user, list):
            dispatchitem_action_user = [dispatchitem_action_user]

        if store_model_interface_configurations is None:
            store_model_interface_configurations = {}
        else:
            store_model_interface_configurations = json.loads(
                store_model_interface_configurations
            )

        if store_finance_interface_configurations is None:
            store_finance_interface_configurations = {}
        else:
            store_finance_interface_configurations = json.loads(
                store_finance_interface_configurations
            )

        mdl_change_list = []
        fnc_change_list = []
        
        lastmodel = None
        lastfinance = None
        for action in dispatchitem_action_user:
            match action['type']:
                case 'model_config_interface_update':
                    model_id = action['model_id']
                    
                    # Avoid doing the get if mdl_conf is already correctly assigned
                    if not lastmodel or lastmodel != model_id:
                        if model_id not in mdl_change_list:
                            mdl_change_list.append(model_id)
                        lastmodel = model_id
                        mdl_conf = store_model_interface_configurations.get(model_id, {})
                        if not mdl_conf:
                            # Empty dictionary returned - ensure key-val pair set
                            store_model_interface_configurations[model_id] = mdl_conf

                    # First update the interface conf
                    update_val = {action['key']: action['val']}
                    print('updating model')
                    print(update_val)
                    if action['key_section'] is None:
                        mdl_conf.update(update_val)
                    else:
                        if mdl_conf.get(action['key_section']) is None or action['key_section'] == 'None':
                            mdl_conf[action['key_section']] = {}
                        mdl_conf[action['key_section']].update(update_val)
                    
                    # We'll synchronise models once we've done all the updates
                case 'finance_config_interface_update':
                    finance_id = action['finance_id']

                    # Avoid doing the get if fnc_conf is already correctly assigned
                    if not lastfinance or lastfinance != finance_id:
                        if finance_id not in fnc_change_list:
                            fnc_change_list.append(finance_id)
                        lastfinance = finance_id
                        fnc_conf = store_finance_interface_configurations.get(finance_id, {})
                        if not fnc_conf:
                            # Empty dictionary returned - ensure key-val pair set
                            store_finance_interface_configurations[finance_id] = fnc_conf
                    
                    update_val = {action['key']: action['val']}

                    if action['key_section'] is None or action['key_section'] == 'None':
                        fnc_conf.update(update_val)
                    else:
                        if fnc_conf.get(action['key_section']) is None:
                            fnc_conf[action['key_section']] = {}
                        fnc_conf[action['key_section']].update(update_val)
                    # We'll synchronise finances once we've done all the updates
        
        mdl_run_list = []
        for model_id in mdl_change_list:
            mdl_conf = store_model_interface_configurations.get(model_id)
            mdl = get_model(model_id)
            dirty = sync_local_model_config_to_model(mdl_conf, mdl)
            if dirty:
                mdl_run_list.append(model_id)
        
        if len(mdl_change_list) == 0:
            r_local_model_config = no_update
        else:
            r_local_model_config = json.dumps(store_model_interface_configurations)

        fnc_run_list = []
        for finance_id in fnc_change_list:
            fnc_conf = store_finance_interface_configurations.get(finance_id)
            fnc = get_finance(finance_id)
            dirty = sync_local_finance_config_to_finance(fnc_conf, fnc)
            if dirty:
                # Need to store both the finance id and its associated model id,
                # in case the model is locked
                fnc_run_list.append((finance_id, fnc.model.uuid))

        if len(fnc_change_list) == 0:
            r_local_finance_config = no_update
        else:
            r_local_finance_config = json.dumps(store_finance_interface_configurations)
        
        if len(mdl_run_list) == 0:
            r_model_run_requests = no_update
        else:
            r_model_run_requests = json.dumps(
                [browser.model_run_request(model_id) for model_id in mdl_run_list]
            )

        if len(fnc_run_list) == 0:
            r_finance_run_requests = no_update
        else:
            r_finance_run_requests = json.dumps(
                [browser.finance_run_request(finance_id, model_id) for finance_id, model_id in fnc_run_list]
            )

        print('models with local config change')
        print(r_local_model_config)
        print('models to request run')
        print(r_model_run_requests)

        return (
            r_local_model_config,
            r_local_finance_config,
            r_model_run_requests,
            r_finance_run_requests
        )

    @app.callback(
        Output('prequeue-action-user', 'data'),
        Output('queue-action-user', 'data'),
        Output('dispatchitem-action-user', 'data'),
        Output('interval-action-user', 'disabled'),
        Input('prequeue-action-user', 'data'),
        Input('interval-action-user', 'n_intervals'),
        State('latch-models-checkedout', 'data'),
        State('queue-action-user', 'data'),
        prevent_initial_call = True
    )
    def queueman_action_user(
        prequeue_action_user, 
        interval_action_user,
        latch_models_checkedout,
        queue_action_user,
    ):
        """
        Receives and dispatches user actions.

        On receiving an action through the prequeue, will add it to the end
        of the action queue.
        If the action overrides any queued action, the queued action will
        be removed.
        The queue is then iterated through. If the action is permitted to
        be dispatched, it shall be removed from the queue and dispatched.
        A change to the latch conditions or a trigger through the postdispatch-trigger
        will result in the queue being run through again.
        """
        if not queue_action_user:
            queue_action_user = []
        else:
            queue_action_user = json.loads(queue_action_user)

        print('action queue manager triggered by:')
        print(ctx.triggered_id)
        
        if ctx.triggered_id == 'prequeue-action-user':
            print('handling user action')
            action = json.loads(prequeue_action_user)
            print(action)
            if isinstance(action, list):
                queue_action_user += action
            else:
                queue_action_user.append(action)
            
            # TODO: Rationalise queue
        
        if latch_models_checkedout is None:
            latch_models_checkedout = []
        else:
            latch_models_checkedout = set(json.loads(latch_models_checkedout))

        # Loop through action queue
        for i, action in enumerate(queue_action_user):
            match action['type']:
                case 'model_config_interface_update':
                    if action['model_id'] not in latch_models_checkedout:
                        # Have a positive dispatch
                        # Find other appropriate actions
                        action_indexes = [i]
                        j = i + 1
                        if j < len(queue_action_user):
                            for j in range(i + 1, len(queue_action_user)):
                                act_j = queue_action_user[j]
                                if (
                                    act_j['type'] == 'model_config_interface_update'
                                    and act_j['model_id'] == action['model_id']
                                ):
                                    action_indexes.append(j)
                        action_indexes.reverse()
                        dispatch_actions = [queue_action_user.pop(x) for x in action_indexes]
                        dispatch_actions.reverse()
                        
                        print('dispatching')
                        print(dispatch_actions)
                        
                        return (
                            None, # The prequeue is consumed
                            json.dumps(queue_action_user),
                            json.dumps(dispatch_actions),
                            len(queue_action_user) == 0 # Disable Interval
                        )
                case 'finance_config_interface_update':
                    # Currently, have no latches in place for finance.
                    # Will go here when defined.

                    # Collate actions relating to this finance
                    action_indexes = [i]
                    j = i + 1
                    if j < len(queue_action_user):
                        for j in range(i + 1, len(queue_action_user)):
                            act_j = queue_action_user[j]
                            if (
                                act_j['type'] == 'finance_config_interface_update'
                                and act_j['finance_id'] == action['finance_id']
                            ):
                                action_indexes.append(j)
                    action_indexes.reverse()
                    dispatch_actions = [queue_action_user.pop(x) for x in action_indexes]
                    dispatch_actions.reverse()

                    print('dispatching')
                    print(dispatch_actions)

                    return (
                        None, # The prequeue is consumed
                        json.dumps(queue_action_user),
                        json.dumps(dispatch_actions),
                        len(queue_action_user) == 0 # Disable Interval
                    )
                case _:
                    raise ValueError('action type not recognised: %s'.format(action['type']))
        
        # Fall-through - do not update dispatchitem-action-user
        return (
            None, # The prequeue is consumed
            json.dumps(queue_action_user),
            no_update,
            len(queue_action_user) == 0 # Disable Interval
        )

    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        Input({'type': 'input-model-config', 'section': ALL, 'key': ALL}, 'value'),
        State('prequeue-action-user', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_model_config(inputs, prequeue, selected_config):
        """
        Add model configuration update events to the user action prequeue.

        May be fired before the queuemanager absorbs the prequeue, so needs
        to ensure that the prequeue is appended, not overwritten.
        In future, we may see if we can do this with a Patch - not sure how the
        data are held, and it may be that we can just append a list rather than
        full json deserialise/serialise.
        """
        NUP = no_update

        selected_model = json.loads(selected_config).get('model_uuid', None)
        if selected_model is None:
            return NUP

        if prequeue is None:
            prequeue = []
        else:
            prequeue = json.loads(prequeue)
        
        print('model configuration input field changed')
        print(ctx.triggered)

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']
            prequeue.append(
                browser.model_interface_action(
                    model_id = selected_model,
                    input_key = pid['key'],
                    input_value = val,
                    key_section = pid['section']
                )
            )
        
        if len(prequeue) == 0:
            return NUP
        
        return json.dumps(prequeue)
    
    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        Input({'type': 'input-finance-config', 'section': ALL, 'key': ALL}, 'value'),
        State('prequeue-action-user', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def update_finance_config(inputs, prequeue, selected_config):
        """
        Add finance configuration update events to the user action prequeue.

        May be fired before the queuemanager absorbs the prequeue, so needs
        to ensure that the prequeue is appended, not overwritten.
        In future, we may see if we can do this with a Patch - not sure how the
        data are held, and it may be that we can just append a list rather than
        full json deserialise/serialise.
        """
        NUP = no_update

        selected_finance = json.loads(selected_config).get('finance_uuid', None)
        if selected_finance is None:
            return NUP
        
        if prequeue is None:
            prequeue = []
        else:
            prequeue = json.loads(prequeue)

        print('finance configuration input field changed')
        print(ctx.triggered)

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']
            prequeue.append(
                browser.finance_interface_action(
                    finance_id = selected_finance,
                    input_key = pid['key'],
                    input_value = val,
                    key_section = pid['section']
                )
            )
        
        if len(prequeue) == 0:
            return NUP
        
        return json.dumps(prequeue)
    
    def sync_fcfg_to_model(fcfg: dict, fnc: sprakefinance.SprakeFinance) -> bool:
        """
        Pass the finance conf dictionary into the Sprake model
        """
        w_fcfg = sprake_finance_to_interface_config(fnc)

        dirty = False
        if not w_fcfg == fcfg:
            sprake_finance_set_finance_config(fcfg, fnc)
            dirty = True
        
        return dirty
    
    def sync_local_model_config_to_model(
        local_model_config: dict,
        mdl: sprakemodel.SprakeModel,
    ) -> bool:
        """
        Pass a local model configuration dictionary into a Sprake model.

        Returns a bool indicating whether a configuration has changed.
        """
        # Get the existing model configuration so we only update if we have
        # changes
        mcfg = local_model_config
        w_mcfg = sprake_model_to_local_model_config(mdl)

        if (
            mcfg.get('gen_input') is not None
            and w_mcfg.get('gen_input') != mcfg.get('gen_input')
        ):
            sprake_model_set_gen_input(mcfg.get('gen_input', {}), mdl)
        
        if (
            mcfg.get('stor_input') is not None
            and w_mcfg.get('stor_input') != mcfg.get('stor_input')
        ):
            sprake_model_set_stor_input(mcfg.get('stor_input', {}), mdl)

        if (
            mcfg.get('bc_input') is not None
            and w_mcfg.get('bc_input') != mcfg.get('bc_input')
        ):
            sprake_model_set_bc_input(mcfg.get('bc_input', {}), mdl)
        
        if (
            mcfg.get('dc_input') is not None
            and w_mcfg.get('dc_input') != mcfg.get('dc_input')
        ):
            sprake_model_set_dc_input(mcfg.get('dc_input', {}), mdl)
        
        if (
            mcfg.get('mc_input') is not None
            and w_mcfg.get('mc_input') != mcfg.get('mc_input')
        ):
            sprake_model_set_mc_input(mcfg.get('mc_input', {}), mdl)
        
        if (
            mcfg.get('loc_input') is not None
            and w_mcfg.get('loc_input') != mcfg.get('loc_input')
        ):
            sprake_model_set_loc_input(mcfg.get('loc_input', {}), mdl)
        
        return mdl.dirty
    
    def sync_local_finance_config_to_finance(
        local_finance_config: dict,
        fnc: sprakefinance.SprakeFinance,
    ) -> bool:
        fcfg = local_finance_config
        w_fcfg = sprake_finance_to_interface_config(fnc)

        if (
            fcfg is not None
            and w_fcfg != fcfg
        ):
            sprake_finance_set_finance_config(fcfg, fnc)
        return fnc.dirty

    def sync_configs_to_model(
        mcfg: dict,
        fcfg: dict,
        mdl: sprakemodel.SprakeModel,
        fnc: sprakefinance.SprakeFinance
    ) -> Tuple[bool, bool]:
        """
        Pass the configuration dictionaries into the Sprake model
        """

        mdl_dirty = sync_local_model_config_to_model(mcfg, mdl)
        fnc_dirty = sync_local_finance_config_to_finance(fcfg, fnc)
        
        return mdl_dirty, fnc_dirty

    @app.callback(
        Output('finance-config-watcher', 'data', allow_duplicate=True),
        Input('finance-config', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def update_finance_config(fcfg, selected_conf):
        """
        Set the currently selected finance with the data held in the fcfg dict
        """
        NUP = no_update
        if fcfg is None or selected_conf is None:
            return NUP
        
        fcfg = json.loads(fcfg)
        selected_conf = json.loads(selected_conf)
        fnc = finances.get(selected_conf['finance_uuid'], None)
        if fnc is None:
            # TODO: Deal with this
            return NUP

        finance_dirty = sync_fcfg_to_model(fcfg, fnc)

        if finance_dirty:
            return json.dumps(
                [{
                    'config_index': selected_conf.get('config_index', 0),
                    'finance_uuid': selected_conf.get('finance_uuid'),
                    'model_uuid': selected_conf.get('model_uuid')
                }]
            )
        return NUP

    @app.callback(
        Output('model-config-watcher', 'data'),
        Output('finance-config-watcher', 'data', allow_duplicate=True),
        Input('model-config', 'data'),
        State('finance-config', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def update_model_configs(mcfg, fcfg, selected_conf):
        NUP = no_update, no_update
        # print('Configuration is being updated')
        # print(ctx.triggered)
        if mcfg is None or fcfg is None or selected_conf is None:
            return no_update, no_update
        mcfg = json.loads(mcfg)
        fcfg = json.loads(fcfg)
        selected_conf = json.loads(selected_conf)

        mdl = models.get(selected_conf['model_uuid'], None)
        fnc = finances.get(selected_conf['finance_uuid'], None)
        if mdl is None or fnc is None:
            # TODO: Deal with this
            return NUP

        # I don't trust these dirty flags on first load; 
        mdl_dirty, finance_dirty = sync_configs_to_model(mcfg, fcfg, mdl, fnc)

        if mdl_dirty:
            return json.dumps(str(datetime.datetime.now())), no_update
        if finance_dirty:
            return (
                no_update, 
                json.dumps(
                    [{
                        'config_index': selected_conf.get('config_index', 0),
                        'finance_uuid': selected_conf.get('finance_uuid'),
                        'model_uuid': selected_conf.get('model_uuid')
                    }]
                )
            )
        
        return NUP

    return app

def add_model_callbacks(app):
    """
    Add callbacks to Dash App to allow for interfacing with a Sprake model
    """
    app = add_initial_callback(app)
    app = add_result_callbacks(app)
    app = add_result_header_callbacks(app)
    app = add_input_callbacks(app)
    app = results_table.add_configuration_selection_callbacks(app)

    return app

def serve_layout():
    """
    Layout server function for Sprake Energy Model Interface Dash App
    """
    session_id = str(str(uuid.uuid4()))

    return html.Div([
        create_layout(),
        dcc.Store(data=session_id, id='session-id')
    ])

BOOTSTRAP_STYLESHEETS = [dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]

def add_model_from_hash_method(app):
    def model_from_hash(h):
        for mdl in app.models:
            if hash(mdl) == h:
                return mdl
        return None
    app.model_from_hash = model_from_hash
    return app

def create_app(external_stylesheets=None):
    """
    Create the Sprake Energy Model Interface Dash App
    """
    if external_stylesheets is None:
        external_stylesheets = BOOTSTRAP_STYLESHEETS
    else:
        # Always add on bootstrap
        external_stylesheets += BOOTSTRAP_STYLESHEETS

    assets_path = '/assets'
    app = Dash(
        __name__,
        title = "Sprake Energy Model",
        external_stylesheets=external_stylesheets,
        assets_url_path = assets_path
    )
    app.layout = serve_layout

    def add_new_model(ref: newsegsmodel.NewsegsModel | None = None):
        if ref is None:
            mdl = create_default_model()
        else:
            mdl = sprakemodel.SprakeModel(ref)
        models[mdl.uuid] = mdl
        return mdl
    
    def duplicate_model(model_uuid: str):
        ref = models.get(model_uuid, None)
        if ref is None:
            return None
        return add_new_model(ref)
    
    def get_model(model_uuid: str):
        return models.get(model_uuid, None)
    
    def remove_model(model_uuid: str):
        return models.pop(model_uuid, None)

    app.add_new_model = add_new_model
    app.duplicate_model = duplicate_model
    app.get_model = get_model

    def add_new_finance(ref: newsegsfinance.NewsegsFinance | None = None):
        if ref is None:
            fnc = create_default_finance()
        else:
            fnc = sprakefinance.SprakeFinance(ref)
        finances[fnc.uuid] = fnc
        return fnc
    
    def duplicate_finance(finance_uuid: str):
        ref = finances.get(finance_uuid, None)
        if ref is None:
            return None
        model_uuid = ref.model.uuid
        fnc = add_new_finance(ref)
        fnc.model = models.get(model_uuid, None)
        return fnc
    
    def get_finance(finance_uuid: str):
        return finances.get(finance_uuid, None)
    
    def remove_finance(finance_uuid: str):
        return finances.pop(finance_uuid, None)

    app.add_new_finance = add_new_finance
    app.duplicate_finance = duplicate_finance
    app.get_finance = get_finance

    app = add_site_selector_callbacks(app)
    app = add_model_callbacks(app)

    #app = add_model_from_hash_method(app)
    return app

# Commented out to prevent PyLint complaining about use of the name "app" in argument lists
#if __name__=="__main__":
#    app = create_app()
#
#    app.run(debug=True)
