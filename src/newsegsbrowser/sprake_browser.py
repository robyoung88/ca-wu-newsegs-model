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

from dash import Dash, html, Input, Output, dcc, State, ALL, no_update
import dash_bootstrap_components as dbc
import dash_daq as daq
from dash_extensions import Purify

from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegsfinance import SprakeFinance

from src.newsegsbrowser.common import get_icon, create_numeric_card_input, unescape_html_icons
from src.newsegsbrowser.map import create_site_selector_map, add_site_selector_callbacks
from src.newsegsbrowser.results_table import create_tbl_head, create_configuration_selector
from src.newsegsbrowser.stats import *
from src.newsegsbrowser.postprocess import post_sprake_gen_results, post_sprake_storage_results
from src.newsegsbrowser.postprocess import post_sprake_consumption_results, post_sprake_net_results
from src.newsegsbrowser.postprocess import post_sprake_finance_benefits_results, post_sprake_finance_costs_results
from src.newsegsbrowser.postprocess import post_sprake_finance_value_results

from src.newsegsbrowser import ROOTDIR
#from config import settings

_CONST_FILE = os.path.join(ROOTDIR, 'constants', 'model_constants.json')

with open(_CONST_FILE, 'r') as f:
    MODEL_CONSTANTS = json.load(f)

print(MODEL_CONSTANTS)

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
                        create_numeric_card_input('gen-wind', 'Wind Capacity (kW rated)', 'wind-capacity-input')    
                    ),
                    dbc.Row(
                        create_numeric_card_input('gen-pv', 'Solar PV Capacity (kWp)', 'pv-capacity-input')
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
                        create_numeric_card_input('storage', 'Storage Capacity (kWh)', 'stor-capacity-input')
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
                        create_numeric_card_input('consumption-building-nunits', 'No. of households', 'bc-n-unit-input')
                    ]),
                    dbc.Row([
                        create_numeric_card_input('consumption-building-hlp', 'HLP (W/m²/K)', 'bc-hlp-input')
                    ]),
                    dbc.Row([
                        create_numeric_card_input('consumption-building-gfa', 'Mean GFA (m²/household)', 'bc-gfa-input')
                    ]),
                    # TODO: Output Fabric Energy Efficiency here
                    dbc.Row([
                        create_numeric_card_input('consumption-building-dhw-ref', 'Reference hot water demand (kWh/day)', 'bc-dhw-ref-daily-cons-input')
                    ]),
                    dbc.Row([
                        create_numeric_card_input('consumption-building-dhw-var', 'Seasonal variation (%)', 'bc-dhw-seasonal-variance-input')
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
                        create_numeric_card_input('consumption-direct-appliance-reduction', 'High-efficiency appliances consumption reduction (fraction)', 'dc-app-efficiency-reduction-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('consumption-direct-ev-anncharge', 'Residential charging per EV (kWh/yr)', 'ev-ann-charge-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('consumption-direct-ev-nperunit', 'EVs per household (n)', 'ev-per-unit-input')
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
                        create_numeric_card_input('gen-wind',
                                                  'Wind Capex (£/kW)',
                                                  'cost-gen-wind-capex-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input(['gen-wind','cost-recurrent'],
                                                  'Wind Ongoing (£/kW/yr)',
                                                  'cost-gen-wind-recurrent-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('gen-pv',
                                                  'Solar PV Capex (£/kWp)',
                                                  'cost-gen-pv-capex-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input(['gen-pv','cost-recurrent'],
                                                  'Solar PV Ongoing (£/kWp/yr)',
                                                  'cost-gen-pv-recurrent-input')
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
                        create_numeric_card_input('storage',
                                                  'BESS Capex (£/kWh)',
                                                  'cost-stor-bess-capex-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input(['storage', 'cost-recurrent'],
                                                   'BESS Ongoing (£/kWh/yr)',
                                                   'cost-stor-bess-recurrent-input')
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
                        create_numeric_card_input('cost-residents-standing',
                                                  'Standing charge (£/household/day)',
                                                  'cost-resident-sc-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('cost-residents-perunit',
                                                  'Per unit charge (£/kWh)',
                                                  'cost-resident-var-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('cost-export',
                                                  'Grid export - mean per unit charge (£/kWh)',
                                                  'cost-export-var-input')
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
                        create_numeric_card_input('cost-import-fixed',
                                                  'Fixed costs for backup (£/site/day)',
                                                  'cost-import-sc-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('cost-import-perunit',
                                                  'Per-unit costs for backup (£/kWh)', 
                                                  'cost-import-var-input')
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
                        create_numeric_card_input('model-settings-time-horizon',
                                                  'Time horizon (years)',
                                                  'mdl-timehorizon-input')
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
    return dbc.Row([
        html.H1([get_icon('results'), 'Results'],
        style={
            'display': 'inline-block',
            'width':'50%',
            'float': 'left'
        }),

        html.Span([
            html.H5("Per year",style={'display': 'inline-block', 'vertical-align': 'middle'}),
            daq.ToggleSwitch(style={'display': 'inline-block',
                                    'vertical-align': 'middle',
                                    'padding': "10px"},
                             id='annual-horizon-toggle'),
            html.H5('To horizon',style={'display': 'inline-block', 'vertical-align': 'middle'})
        ],
        style={
            'display': 'inline-block',
            'width':'50%',
            'float': 'right',
            "justifyContent": "flex-end",
            "alignItems": "center",
            'text-align': 'right'
        })
    ],
    style={'display': 'flex'}
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
    mapview = [create_site_selector_map()] \
        + [
            html.Div([

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

        html.Hr(),

        # Results

        create_results_header(),

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

        html.Div(id='onload-div'), # To trigger first callback

        # To trigger resync of input fields from model, e.g. after a load
        dcc.Store(id='live-config-watcher'),

        # To trigger resync of output fields after a model run
        dcc.Store(id='model-run-watcher'),

        dcc.Store(id='model-config'),
        dcc.Store(id='finance-config'),
        dcc.Store(id='res-gen'),
        dcc.Store(id='res-stor'),
        dcc.Store(id='res-cons'),
        dcc.Store(id='res-net'),
        dcc.Store(id='res-finance-so-benefits'),
        dcc.Store(id='res-finance-so-costs'),
        dcc.Store(id='res-finance-so-value'),
    ])
    ]

    return dbc.Container(mapview, fluid=False)

def sprake_model_set_gen_input(gen_input:dict, mdl:SprakeModel):
    mdl.generation.generator.generators[0].nameplate_capacity = gen_input.get('wind_capacity', 0.0)
    mdl.generation.generator.generators[1].nameplate_capacity = gen_input.get('pv_capacity', 0.0)
    mdl.generation.dirty = True

def sprake_model_set_stor_input(stor_input:dict, mdl:SprakeModel):
    mdl.consumption_storage.set_storage_params(stor_input.copy())
    # consumption storage will be dirtied by this method

def sprake_model_set_bc_input(bc_input:dict, mdl:SprakeModel):
    cs = mdl.consumption_storage
    spaceheat_p = cs.spaceheat_params
    dhw_p = cs.dhw_params

    cs.n_units = bc_input.get('n_units', 1.0)
    spaceheat_p['hlp'] = bc_input.get('hlp', 1.1)
    spaceheat_p['gfa'] = bc_input.get('gfa', 1.0)
    dhw_p['ref_daily_consumption'] = bc_input.get('ref_daily_consumption', 0.0)
    dhw_p['seasonal_variance'] = bc_input.get('seasonal_variance', 0.01)
    cs.dirty = True

def sprake_model_set_dc_input(dc_input:dict, mdl:SprakeModel):
    cs = mdl.consumption_storage
    app_p = cs.appliance_params
    ev_p = cs.ev_params

    app_p['efficiency_reduction'] = dc_input.get('efficiency_reduction', 0.0)
    ev_p['annual_residential_consumption_per_ev'] = dc_input.get('annual_residential_consumption_per_ev', 0.0)
    ev_p['n_evs'] = dc_input.get('n_evs_per_household', 0.0) * cs.n_units
    cs.dirty = True

def sprake_model_set_mc_input(mc_input:dict, mdl:SprakeModel):
    ts = mdl.get_run_period()
    ts.end = ts.start + pd.Timedelta(mc_input.get('horizon',1)*365, unit='d') 
    while ts.end.day != ts.start.day:
        ts.end = ts.end + pd.Timedelta(1, unit='d')
    mdl.set_run_period(ts)

def sprake_model_to_interface_configs(mdl) -> Tuple(dict, dict):
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

    mcfg = {
        'gen_input': gen_input,
        'stor_input': stor_input,
        'bc_input': bc_input,
        'dc_input': dc_input,
        'mc_input': mc_input
    }

    fcfg = app.finance.to_dict()

    return mcfg, fcfg

def add_initial_callback(app):
    """
    Functions to synchronise app interface with the served model
    """
    @app.callback(
        Output('live-config-watcher', 'data'),
        Input('onload-div', 'children')
    )
    def sync_config_init(_):
        return json.dumps(str(datetime.datetime.now()))

    @app.callback(
        Output('model-run-watcher', 'data'),
        Input('onload-div', 'children')
    )
    def sync_mdl_run_init(_):
        app.mdl.run()
        print('run complete')
        return json.dumps(str(datetime.datetime.now()))

    @app.callback(
        Output('model-config', 'data', allow_duplicate=True),
        Output('finance-config', 'data', allow_duplicate=True),
        Input('live-config-watcher', 'data'),
        prevent_initial_call=True
    )
    def sync_config(_):
        mdl = app.mdl

        mcfg, fcfg = sprake_model_to_interface_configs(mdl)

        return json.dumps(mcfg), json.dumps(fcfg)

    @app.callback(
        Output('gen-smry-wind-cap', 'children'),
        Output('gen-smry-pv-cap', 'children'),
        Output('wind-capacity-input', 'value'),
        Output('pv-capacity-input', 'value'),
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
        Output('stor-capacity-input', 'value'),
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
        Output('bc-n-unit-input', 'value'),
        Output('bc-hlp-input', 'value'),
        Output('bc-gfa-input', 'value'),
        Output('bc-dhw-ref-daily-cons-input', 'value'),
        Output('bc-dhw-seasonal-variance-input', 'value'),
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
        Output('dc-app-efficiency-reduction-input', 'value'),
        Output('ev-ann-charge-input', 'value'),
        Output('ev-per-unit-input', 'value'),
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
        Output('cost-gen-wind-capex-input', 'value'),
        Output('cost-gen-wind-recurrent-input', 'value'),
        Output('cost-gen-pv-capex-input', 'value'),
        Output('cost-gen-pv-recurrent-input', 'value'),
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
        Output('cost-stor-bess-capex-input', 'value'),
        Output('cost-stor-bess-recurrent-input', 'value'),
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
        Output('cost-resident-sc-input', 'value'),
        Output('cost-resident-var-input', 'value'),
        Output('cost-export-var-input', 'value'),
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
        Output('cost-import-sc-input', 'value'),
        Output('cost-import-var-input', 'value'),
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
        Output('mdl-timehorizon-input', 'value'),
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
        prevent_initial_call=True
    )
    def sync_fnc_so_benefits_to_store(fnc, ann_hori_toggle):
        if fnc is None:
            return no_update, no_update, no_update
        fnc = json.loads(fnc)
        bnfts = create_so_benefits_results(fnc, not(ann_hori_toggle))
        return (
            bnfts,
            '{:,.0f}'.format(fnc.get('smry_residential_peryear')),
            '{:,.0f}'.format(fnc.get('smry_exports_peryear')),
        )
    
    @app.callback(
        Output('res-finance-so-costs-tbl', 'children'),
        Output('cost-import-smry-fixed', 'children'),
        Output('cost-import-smry-ongoing', 'children'),
        Input('res-finance-so-costs', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_fnc_so_costs_to_store(fnc, ann_hori_toggle):
        if fnc is None:
            return no_update, no_update, no_update
        fnc = json.loads(fnc)
        return (
            create_so_costs_results(fnc, not(ann_hori_toggle)),
            '{:,.0f}'.format(fnc.get('smry_import_fixed_cost_peryear')),
            '{:,.0f}'.format(fnc.get('smry_import_variable_cost_peryear'))
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
        return create_so_value_results(fnc, not(ann_hori_toggle))

    return app

def add_result_callbacks(app):
    """
    Callbacks to synchronise app interface with results of the model after run
    """
    @app.callback(
        Output('res-gen', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_gen(_):
        """
        Create the generation results data after a completed model run
        """
        mdl = app.mdl

        print ("making gen results")
        gen_results = post_sprake_gen_results.gen_results_to_interface_sprake(mdl)
        return json.dumps(gen_results)

    @app.callback(
        Output('res-stor', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_stor(_):
        """
        Create the storage results data after a completed model run
        """
        mdl = app.mdl

        print ("making stor results")
        stor_results = post_sprake_storage_results.stor_results_to_interface_sprake(mdl)
        return json.dumps(stor_results)

    @app.callback(
        Output('res-cons', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_cons(_):
        """
        Create the consumption results data after a completed model run.
        """
        mdl = app.mdl

        print ("making consumption results")
        cons_results = post_sprake_consumption_results.consumption_results_to_interface_sprake(mdl)
        return json.dumps(cons_results)

    @app.callback(
        Output('res-net', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_net(_):
        """
        Create the net energy results data after a completed model run.
        """
        mdl = app.mdl

        print ("making net energy results")
        net_results = post_sprake_net_results.net_results_to_interface_sprake(mdl)
        return json.dumps(net_results)
    
    @app.callback(
        Output('res-finance-so-benefits', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_finance_benefits_so(_):
        """
        Create the system owner financial benefits results after a completed model run.
        """
        mdl = app.mdl
        fnc = app.finance

        print ("making so financial benefits results")
        fnc_benefits_results = (
            post_sprake_finance_benefits_results
            .finance_benefits_results_to_interface_sprake(mdl,fnc)
        )
        return json.dumps(fnc_benefits_results)
    
    @app.callback(
        Output('res-finance-so-costs', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_finance_costs_so(_):
        """
        Create the system owner financial costs results after a completed model run.
        """
        mdl = app.mdl
        fnc = app.finance

        print ("making so financial costs results")
        fnc_costs_results = (
            post_sprake_finance_costs_results
            .finance_costs_results_to_interface_sprake(mdl,fnc)
        )
        return json.dumps(fnc_costs_results)

    @app.callback(
        Output('res-finance-so-value', 'data'),
        Input('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def set_res_finance_value_so(_):
        """
        Create the system owner financial value results after a completed model run.
        """
        mdl = app.mdl
        fnc = app.finance

        print ("making so financial value results")
        fnc_value_results = (
            post_sprake_finance_value_results
            .finance_value_results_to_interface_sprake(mdl,fnc)
        )
        return json.dumps(fnc_value_results)

    return app

def add_result_header_callbacks(app):
    
    @app.callback(
        Output('gen-ressmry-container', 'children'),
        Input('res-gen', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def update_generation_results_header(res, ann_hori_toggle):
        if res is None:
            return no_update
        res = json.loads(res)
        gm = res.get('generator_meter_summary')
        if ann_hori_toggle:
            str_1 = 'Total generation: '
            wind_ann = gm.get('wind_export').get('sum')
            pv_ann = gm.get('solar_export').get('sum')
        else:
            str_1 = 'Annual generation: '
            wind_ann = gm.get('wind_export').get('mean')
            pv_ann = gm.get('solar_export').get('mean')
        return [
            str_1,
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
        prevent_initial_call=True
    )
    def update_storage_results_header(res, ann_hori_toggle):
        if res is None:
            return no_update
        res = json.loads(res)
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
        prevent_initial_call=True
    )
    def update_consumption_results_header(res, ann_hori_toggle):
        if res is None:
            return no_update
        res = json.loads(res)
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
        prevent_initial_call=True
    )
    def update_net_results_header(res, ann_hori_toggle):
        if res is None:
            return no_update
        res = json.loads(res)
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
        prevent_initial_call=True
    )
    def update_finance_results_header(res_benefits, res_costs, res_value):
        if (res_benefits is None) or (res_costs is None) or (res_value is None):
            return no_update
        res_benefits = json.loads(res_benefits)
        res_costs = json.loads(res_costs)
        res_value = json.loads(res_value)

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
        Output('model-config', 'data', allow_duplicate=True),
        Input('wind-capacity-input', 'value'),
        Input('pv-capacity-input', 'value'),
        State('model-config', 'data'),
        prevent_initial_call=True
    )
    def update_gen_config(wind_cap, pv_cap, mcfg):
        if mcfg is None:
            mcfg = {
                'gen_input': {}
            }
        else:
            mcfg = json.loads(mcfg)

        gen_input = copy.copy(mcfg.get('gen_input', {}))

        if not wind_cap is None:
            gen_input['wind_capacity'] = float(wind_cap)
        if not pv_cap is None:
            gen_input['pv_capacity'] = float(pv_cap)

        if (gen_input == mcfg['gen_input']):
            return no_update
        
        mcfg['gen_input'] = gen_input

        return json.dumps(mcfg)
    
    @app.callback(
        Output('model-config', 'data', allow_duplicate=True),
        Input('stor-capacity-input', 'value'),
        State('model-config', 'data'),
        prevent_initial_call=True
    )
    def update_stor_config(stor_cap, mcfg):
        if mcfg is None:
            mcfg = {
                'stor_input': {}
            }
        else:
            mcfg = json.loads(mcfg)

        stor_input = copy.copy(mcfg.get('stor_input', {}))

        if not stor_cap is None:
            stor_input['storage_capacity'] = float(stor_cap)
        
        if stor_input == mcfg.get('stor_input', {}):
            return no_update
        
        mcfg['stor_input'] = stor_input
        return json.dumps(mcfg)

    @app.callback(
        Output('model-config', 'data', allow_duplicate=True),
        Input('bc-n-unit-input', 'value'),
        Input('bc-hlp-input', 'value'),
        Input('bc-gfa-input', 'value'),
        Input('bc-dhw-ref-daily-cons-input', 'value'),
        Input('bc-dhw-seasonal-variance-input', 'value'),
        State('model-config', 'data'),
        prevent_initial_call=True
    )
    def update_bc_config(
        bc_n_unit,
        bc_hlp,
        bc_gfa,
        bc_dhw_ref_daily_cons,
        bc_dhw_seasonal_variance,
        mcfg
    ):
        if mcfg is None:
            mcfg = {
                'bc_input': {}
            }
        else:
            mcfg = json.loads(mcfg)
        
        bc_input = copy.copy(mcfg.get('bc_input', {}))

        if not bc_n_unit is None:
            bc_input['n_units'] = float(bc_n_unit)
        if not bc_hlp is None:
            bc_input['hlp'] = float(bc_hlp)
        if not bc_gfa is None:
            bc_input['gfa'] = float(bc_gfa)
        if not bc_dhw_ref_daily_cons is None:
            bc_input['ref_daily_consumption'] = bc_dhw_ref_daily_cons
        if not bc_dhw_seasonal_variance is None:
            bc_input['seasonal_variance'] = bc_dhw_seasonal_variance
        
        if bc_input == mcfg.get('bc_input', {}):
            return no_update
        
        mcfg['bc_input'] = bc_input
        return json.dumps(mcfg)

    @app.callback(
        Output('model-config', 'data', allow_duplicate=True),
        Input('dc-app-efficiency-reduction-input', 'value'),
        Input('ev-ann-charge-input', 'value'),
        Input('ev-per-unit-input', 'value'),
        State('model-config', 'data'),
        prevent_initial_call=True
    )
    def update_dc_config(
        dc_app_efficiency_reduction,
        ev_ann_charge,
        ev_per_unit,
        mcfg
    ):
        if mcfg is None:
            mcfg = {
                'bc_input': {}
            }
        else:
            mcfg = json.loads(mcfg)
        
        dc_input = copy.copy(mcfg.get('dc_input', {}))

        if not dc_app_efficiency_reduction is None:
            dc_input['efficiency_reduction'] = float(dc_app_efficiency_reduction)
        if not ev_ann_charge is None:
            dc_input['annual_residential_consumption_per_ev'] = float(ev_ann_charge)
        if not ev_per_unit is None:
            dc_input['n_evs_per_household'] = float(ev_per_unit)
        
        if dc_input == mcfg.get('dc_input', {}):
            return no_update
        
        mcfg['dc_input'] = dc_input
        return json.dumps(mcfg)

    @app.callback(
        Output('finance-config', 'data', allow_duplicate=True),
        Input('cost-gen-wind-capex-input', 'value'),
        Input('cost-gen-wind-recurrent-input', 'value'),
        Input('cost-gen-pv-capex-input', 'value'),
        Input('cost-gen-pv-recurrent-input', 'value'),
        State('finance-config', 'data'),
        prevent_initial_call=True
    )
    def update_gen_costs(
        gen_wind_capex,
        gen_wind_recurrent,
        gen_pv_capex,
        gen_pv_recurrent,
        fcfg
    ):
        if fcfg is None:
            fcfg = {
                'unit_costs': {}
            }
        else:
            fcfg = json.loads(fcfg)
        
        unit_costs = copy.copy(fcfg.get('unit_costs', {}))

        if not gen_wind_capex is None:
            unit_costs['wind_capex_per_kw'] = float(gen_wind_capex)
        if not gen_wind_recurrent is None:
            unit_costs['wind_om_per_kw_year'] = float(gen_wind_recurrent)
        if not gen_pv_capex is None:
            unit_costs['pv_capex_per_kw'] = float(gen_pv_capex)
        if not gen_pv_recurrent is None:
            unit_costs['pv_om_per_kw_year'] = float(gen_pv_recurrent)
        
        if unit_costs == fcfg.get('unit_costs', {}):
            return no_update
        
        fcfg['unit_costs'] = unit_costs
        return json.dumps(fcfg)

    @app.callback(
        Output('finance-config', 'data', allow_duplicate=True),
        Input('cost-stor-bess-capex-input', 'value'),
        Input('cost-stor-bess-recurrent-input', 'value'),
        State('finance-config', 'data'),
        prevent_initial_call=True
    )
    def update_stor_costs(
        stor_capex,
        stor_recurrent,
        fcfg
    ):
        if fcfg is None:
            fcfg = {
                'unit_costs': {}
            }
        else:
            fcfg = json.loads(fcfg)

        unit_costs = copy.copy(fcfg.get('unit_costs', {}))

        if not stor_capex is None:
            unit_costs['bess_capex_per_kwh'] = float(stor_capex)
        if not stor_recurrent is None:
            unit_costs['bess_om_per_kwh_year'] = float(stor_recurrent)
        
        if unit_costs == fcfg.get('unit_costs', {}):
            return no_update
        
        fcfg['unit_costs'] = unit_costs
        return json.dumps(fcfg)

    @app.callback(
        Output('finance-config', 'data', allow_duplicate=True),
        Input('cost-resident-sc-input', 'value'),
        Input('cost-resident-var-input', 'value'),
        Input('cost-export-var-input', 'value'),
        State('finance-config', 'data'),
        prevent_initial_call=True
    )
    def update_sales_costs(
        resident_sc,
        resident_var,
        export_var,
        fcfg
    ):
        if fcfg is None:
            fcfg = {
                'unit_costs': {}
            }
        else:
            fcfg = json.loads(fcfg)

        unit_costs = copy.copy(fcfg.get('unit_costs', {}))

        if not resident_sc is None:
            unit_costs['resident_sc_per_unit_day'] = float(resident_sc)
        if not resident_var is None:
            unit_costs['resident_var_per_unit'] = float(resident_var)
        if not export_var is None:
            unit_costs['grid_export_var_per_unit'] = float(export_var)
        
        if unit_costs == fcfg.get('unit_costs', {}):
            return no_update
        
        fcfg['unit_costs'] = unit_costs
        return json.dumps(fcfg)

    @app.callback(
        Output('finance-config', 'data', allow_duplicate=True),
        Input('cost-import-sc-input', 'value'),
        Input('cost-import-var-input', 'value'),
        State('finance-config', 'data'),
        prevent_initial_call=True
    )
    def update_import_costs(
        import_sc,
        import_var,
        fcfg
    ):
        if fcfg is None:
            fcfg = {
                'unit_costs': {}
            }
        else:
            fcfg = json.loads(fcfg)

        unit_costs = copy.copy(fcfg.get('unit_costs', {}))

        if not import_sc is None:
            unit_costs['grid_import_sc_per_day'] = float(import_sc)
        if not import_var is None:
            unit_costs['grid_import_var_per_unit'] = float(import_var)
        
        if unit_costs == fcfg.get('unit_costs', {}):
            return no_update
        
        fcfg['unit_costs'] = unit_costs
        return json.dumps(fcfg)

    @app.callback(
        Output('model-config', 'data', allow_duplicate=True),
        Input('mdl-timehorizon-input', 'value'),
        State('model-config', 'data'),
        prevent_initial_call=True
    )
    def update_model_settings(
        timehorizon,
        mcfg
    ):
        if mcfg is None:
            mcfg = {
                'mc_input': {}
            }
        else:
            mcfg = json.loads(mcfg)
        
        mc_input = copy.copy(mcfg.get('mc_input', {}))

        if not timehorizon is None:
            mc_input['horizon'] = int(timehorizon)
        
        if mc_input == mcfg.get('mc_input', {}):
            return no_update
        
        mcfg['mc_input'] = mc_input
        return json.dumps(mcfg)

    def sync_configs_to_model(mcfg, fcfg) -> Tuple[bool, bool]:
        """
        Pass the configuration dictionaries into the Sprake model
        """
        mdl = app.mdl
        fnc = app.finance

        # Get the existing configs to check against
        w_mcfg, w_fcfg = sprake_model_to_interface_configs(mdl)

        if not w_mcfg.get('gen_input') == mcfg.get('gen_input'):
            sprake_model_set_gen_input(mcfg.get('gen_input', {}), mdl)
        
        if not w_mcfg.get('stor_input') == mcfg.get('stor_input'):
            sprake_model_set_stor_input(mcfg.get('stor_input', {}), mdl)

        if not w_mcfg.get('bc_input') == mcfg.get('bc_input'):
            sprake_model_set_bc_input(mcfg.get('bc_input', {}), mdl)
        
        if not w_mcfg.get('dc_input') == mcfg.get('dc_input'):
            sprake_model_set_dc_input(mcfg.get('dc_input', {}), mdl)
        
        if not w_mcfg.get('mc_input') == mcfg.get('mc_input'):
            sprake_model_set_mc_input(mcfg.get('mc_input', {}), mdl)

    return app

def add_model_callbacks(app):
    """
    Add callbacks to Dash App to allow for interfacing with a Sprake model
    """
    app = add_initial_callback(app)
    app = add_result_callbacks(app)
    app = add_result_header_callbacks(app)
    app = add_input_callbacks(app)

    return app

def serve_layout():
    """
    Layout server function for Sprake Energy Model Interface Dash App
    """
    session_id = str(uuid.uuid4())

    return html.Div([
        create_layout(),
        dcc.Store(data=session_id, id='session-id')
    ])

BOOTSTRAP_STYLESHEETS = [dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]

def create_app(external_stylesheets=None, run_model=False):
    """
    Create the Sprake Energy Model Interface Dash App
    """
    if external_stylesheets is None:
        external_stylesheets = BOOTSTRAP_STYLESHEETS
    else:
        # Always add on bootstrap
        external_stylesheets += BOOTSTRAP_STYLESHEETS

    app = Dash(external_stylesheets=external_stylesheets)
    app.layout = serve_layout

    # Load model
    app.mdl = SprakeModel()
    # Temp - override default PV array size
    app.mdl.generation.generator.generators[1].n_arrays=100
    if run_model:
        app.mdl.run()
    app.finance = SprakeFinance()
    app.finance.set_model(app.mdl)

    app = add_site_selector_callbacks(app)
    app = add_model_callbacks(app)

    app.title = "Sprake Energy Model"

    return app

# Commented out to prevent PyLint complaining about use of the name "app" in argument lists
#if __name__=="__main__":
#    app = create_app()
#
#    app.run(debug=True)
