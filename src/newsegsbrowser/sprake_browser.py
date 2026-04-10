# A Dash Leaflet map browser for manipulating the Sprake Model
import json
import uuid
import datetime
from collections.abc import Mapping
#from typing import Literal

from dash import Dash, html, Input, Output, dcc, State, ALL, no_update
import dash_bootstrap_components as dbc
import dash_daq as daq

from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegsfinance import SprakeFinance

from src.newsegsbrowser.common import get_icon, create_numeric_card_input
from src.newsegsbrowser.map import create_site_selector_map, add_site_selector_callbacks
from src.newsegsbrowser.results_table import create_tbl_head, create_configuration_selector
from src.newsegsbrowser.stats import *
from src.newsegsbrowser.postprocess import post_sprake_gen_results, post_sprake_storage_results

#from config import settings

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
    
    if (annual):
        app_cons = present_stat_description(cons_data, 'annual_app_cons', 'Appliance consumption (kWh/yr)', fmt='{:,.0f}')
        dhw_cons = present_stat_description(cons_data, 'annual_dhw_cons', 'DHW consumption (kWh/yr)', fmt='{:,.0f}')
        spaceheat_cons = present_stat_description(cons_data, 'annual_sh_cons', 'Space heat consumption (kWh/yr)', fmt='{:,.0f}')

        residential_cons = present_stat_description(cons_data, 'annual_resid_cons', 'Total residential consumption (kWh/yr)', fmt='{:,.0f}')
        perunit_residential_cons = present_stat_description(cons_data, 'annual_resid_cons_perunit', 'Per-unit residential consumption (kWh/yr)', fmt='{:,.0f}')

        ev_cons = present_stat_description(cons_data, 'annual_ev_cons', 'EV consumption (kWh/yr)', fmt='{:,.0f}')
        site_cons = present_stat_description(cons_data, 'annual_site_cons', 'Site consumption (kWh/yr)', fmt='{:,.0f}')

    else:
        app_cons = present_stat_description(cons_data, 'total_app_cons', 'Appliance consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')
        dhw_cons = present_stat_description(cons_data, 'total_dhw_cons', 'DHW consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')
        spaceheat_cons = present_stat_description(cons_data, 'total_sh_cons', 'Space heat consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')

        residential_cons = present_stat_description(cons_data, 'total_resid_cons', 'Total residential consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')
        perunit_residential_cons = present_stat_description(cons_data, 'total_resid_cons_perunit', 'Per-unit residential consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')

        ev_cons = present_stat_description(cons_data, 'total_ev_cons', 'EV consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')
        site_cons = present_stat_description(cons_data, 'total_site_cons', 'Site consumption (kWh)', stat_list=TOTAL_DEFAULT_STATS, fmt='{:,.0f}')

    admd = present_single_stat(cons_data, 'admd_computed', 'ADMD - calculated (kW)', 'value', fmt='{:,.0f}')
    max_demand = present_event_and_date(cons_data, 'max_demand', 'Maximum demand (kW)', 'value', lambda x: '{:,.0f}'.format(x))

    tab_body = [html.Tbody(app_cons + dhw_cons + spaceheat_cons + residential_cons + perunit_residential_cons + ev_cons + site_cons + admd + max_demand)]

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
        weekday_sitecons = present_stat_description_compound(cons_data,
                                                             'annual_site_daily_cons_wd',
                                                             r'Weekday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=ANNUAL_SEASONAL_STATS)

        sat_sitecons = present_stat_description_compound(cons_data,
                                                             'annual_site_daily_cons_sat',
                                                             r'Saturday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=ANNUAL_SEASONAL_STATS)
        
        sun_sitecons = present_stat_description_compound(cons_data,
                                                             'annual_site_daily_cons_sun',
                                                             r'Sunday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=ANNUAL_SEASONAL_STATS)
    else:
        weekday_sitecons = present_stat_description_compound(cons_data,
                                                             'total_site_daily_cons_wd',
                                                             r'Weekday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=TOTAL_SEASONAL_STATS)

        sat_sitecons = present_stat_description_compound(cons_data,
                                                             'total_site_daily_cons_sat',
                                                             r'Saturday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=TOTAL_SEASONAL_STATS)
        
        sat_sitecons = present_stat_description_compound(cons_data,
                                                             'total_site_daily_cons_sun',
                                                             r'Sunday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=TOTAL_SEASONAL_STATS)

    tab_body = [html.Tbody(weekday_sitecons + sat_sitecons + sun_sitecons)]

    return dbc.Table(tbl_head + tab_body)

def create_net_results(net_data=None, annual=True):
    if net_data is None:
        net_data = {}
    
    if isinstance(net_data, Mapping):
        n_configs = 1
        net_data = [net_data]
    else:
        n_configs = len(net_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        export_stats = present_stat_description(net_data, 'annual_export', 'Export to grid (kWh/yr)', fmt='{:,.0f}')
        import_stats = present_stat_description(net_data, 'annual_import', 'Import from grid (kWh/yr)', fmt='{:,.0f}')
        loss_stats = present_stat_description(net_data, 'annual_stor_loss', 'Storage losses (kWh/yr)', fmt='{:,.0f}')

        # NB - ensure this stat compensates for daylight savings
        peak_export = present_stat_description(net_data, 'peak_export', 'Exports 5pm-8pm (kWh/yr)', fmt='{:,.0f}')
        peak_import = present_stat_description(net_data, 'peak_import', 'Imports 5pm-8pm (kWh/yr)', fmt='{:,.0f}')
    else:
        export_stats = present_stat_description(net_data, 'annual_export', 'Export to grid (kWh)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
        import_stats = present_stat_description(net_data, 'annual_import', 'Import from grid (kWh)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
        loss_stats = present_stat_description(net_data, 'annual_stor_loss', 'Storage losses (kWh)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)

        # NB - ensure this stat compensates for daylight savings
        peak_export = present_stat_description(net_data, 'peak_export', 'Exports 5pm-8pm (kWh)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
        peak_import = present_stat_description(net_data, 'peak_import', 'Imports 5pm-8pm (kWh)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
    
    tab_body = [html.Tbody(export_stats + import_stats + loss_stats + peak_export + peak_import)]

    return dbc.Table(tbl_head + tab_body)

def create_seasonal_net_results(net_data=None, annual=True):
    if net_data is None:
        net_data = {}
    
    if isinstance(net_data, Mapping):
        n_configs = 1
        net_data = [net_data]
    else:
        n_configs = len(net_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        export_stats = present_stat_description_compound(net_data,
                                                         'annual_export',
                                                         r'Export to grid (kWh/yr (% production))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=ANNUAL_SEASONAL_STATS)

        import_stats = present_stat_description_compound(net_data,
                                                         'annual_import',
                                                         r'Import from grid (kWh/yr (% consumption))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=ANNUAL_SEASONAL_STATS)

        peak_export = present_stat_description_compound(net_data,
                                                         'peak_export',
                                                         r'Exports 5pm-8pm (kWh/yr (% production))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=ANNUAL_SEASONAL_STATS)
        
        peak_import = present_stat_description_compound(net_data,
                                                        'peak_import',
                                                        r'Imports 5pm-8pm (kWh/yr (% consumption))',
                                                        stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                        stat_list=ANNUAL_SEASONAL_STATS)
    else:
        export_stats = present_stat_description_compound(net_data,
                                                         'annual_export',
                                                         r'Export to grid (kWh (% production))',
                                                         stat_formatter = val_percent_formatter_factory('total', 'frac'),
                                                         stat_list=TOTAL_SEASONAL_STATS)

        import_stats = present_stat_description_compound(net_data,
                                                         'annual_import',
                                                         r'Import from grid (kWh (% consumption))',
                                                         stat_formatter = val_percent_formatter_factory('total', 'frac'),
                                                         stat_list=TOTAL_SEASONAL_STATS)

        peak_export = present_stat_description_compound(net_data,
                                                         'peak_export',
                                                         r'Exports 5pm-8pm (kWh (% production))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=TOTAL_SEASONAL_STATS)
        
        peak_import = present_stat_description_compound(net_data,
                                                        'peak_import',
                                                        r'Imports 5pm-8pm (kWh (% consumption))',
                                                        stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                        stat_list=TOTAL_SEASONAL_STATS)

    tab_body = [html.Tbody(export_stats + import_stats + peak_export + peak_import)]

    return dbc.Table(tbl_head + tab_body)

def create_so_benefits_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        resid_receipts = present_stat_description(econ_data, 'annual_resident_receipts', 'Resident receipts (£/yr)', fmt='{:,.0f}')
        resid_perunit_receipts = present_stat_description(econ_data, 'annual_resident_perunit_receipts', 'Resident receipts (£/yr/household)', fmt='{:,.0f}')

        ev_receipts = present_stat_description(econ_data, 'annual_ev_receipts', 'EV receipts (£/yr)', fmt='{:,.0f}')

        export_receipts = present_stat_description(econ_data, 'annual_export_receipts', 'Export receipts (£/yr)', fmt='{:,.0f}')
    else:
        resid_receipts = present_stat_description(econ_data, 'annual_resident_receipts', 'Resident receipts (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
        resid_perunit_receipts = []

        ev_receipts = present_stat_description(econ_data, 'annual_ev_receipts', 'EV receipts (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)

        export_receipts = present_stat_description(econ_data, 'annual_export_receipts', 'Export receipts (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)

    total_benefits = present_stat_description(econ_data, 'total_benefits_undiscounted', 'Total present benefits (undiscounted) (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
    total_benefits_discounted = present_stat_description(econ_data, 'total_benefits_discounted', 'Total present benefits (discounted) (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)

    tab_body = [html.Tbody(resid_receipts + resid_perunit_receipts + ev_receipts + export_receipts + total_benefits + total_benefits_discounted)]

    return dbc.Table(tbl_head + tab_body)

def create_so_costs_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    tbl_head = create_tbl_head(n_configs)

    if (annual):
        import_costs = present_stat_description(econ_data, 'annual_import_costs', 'Import costs (£/yr)', fmt='{:,.2f}')
        generator_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - generation (£/yr)', fmt='{:,.2f}')
        storage_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - storage (£/yr)', fmt='{:,.2f}')

        ann_costs = present_stat_description(econ_data, 'annual_recurrent_costs', 'Recurrent costs - total (£/yr)', fmt='{:,.2f}')
    else:
        import_costs = present_stat_description(econ_data, 'annual_import_costs', 'Import costs (£r)', fmt='{:,.2f}', stat_list=TOTAL_DEFAULT_STATS)
        generator_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - generation (£/yr)', fmt='{:,.2f}', stat_list=TOTAL_DEFAULT_STATS)
        storage_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - storage (£/yr)', fmt='{:,.2f}', stat_list=TOTAL_DEFAULT_STATS)

        ann_costs = present_stat_description(econ_data, 'annual_recurrent_costs', 'Recurrent costs - total (£/yr)', fmt='{:,.2f}', stat_list=TOTAL_DEFAULT_STATS)

    capex_generation = present_single_stat(econ_data, 'total_gen_capex', 'Capital costs - generation (£)', 'value', fmt='{:,.2f}')
    capex_storage = present_single_stat(econ_data, 'total_stor_capex', 'Capital costs - storage (£)', 'value', fmt='{:,.2f}')
    capex_dist = present_single_stat(econ_data, 'total_dist_capex', 'Capital costs - distribution and switching (£)', 'value', fmt='{:,.2f}')
    capex_meter = present_single_stat(econ_data, 'total_meter_capex', 'Capital costs - metering (£)', 'value', fmt='{:,.2f}')

    capex_total = present_single_stat(econ_data, 'total_capex', 'Capital costs - total (£)', 'value', fmt='{:,.2f}')

    total_costs = present_stat_description(econ_data, 'total_costs_undiscounted', 'Total present costs (undiscounted) (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)
    total_costs_discounted = present_stat_description(econ_data, 'total_costs_discounted', 'Total present costs (discounted) (£)', fmt='{:,.0f}', stat_list=TOTAL_DEFAULT_STATS)

    tab_body = [html.Tbody(import_costs + generator_om_costs + storage_om_costs + ann_costs + capex_generation + capex_storage + capex_dist + capex_meter + capex_total + total_costs + total_costs_discounted)]

    return dbc.Table(tbl_head + tab_body)

def create_so_value_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}

    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)

    tbl_head = create_tbl_head(n_configs)

    b_to_c_undiscounted = present_single_stat(econ_data, 'benefits_to_costs_undiscounted', 'Benefits/Costs (undiscounted)', 'value', fmt='{:,.2f}')
    b_to_c_discounted = present_single_stat(econ_data, 'benefits_to_costs_discounted', 'Benefits/Costs (discounted)', 'value', fmt='{:,.2f}')

    simple_payback_time = present_single_stat(econ_data, 'simple_payback_time', 'Simple payback time (years)', 'value', fmt='{:,.2f}')

    npv_undiscounted = present_single_stat(econ_data, 'npv_undiscounted', 'Net Present Value (undiscounted) (£)', 'value', fmt='{:,.0f}')
    npv_discounted = present_single_stat(econ_data, 'npv_discounted', 'Net Present Value (discounted) (£)', 'value', fmt='{:,.0f}')

    tab_body = [html.Tbody(b_to_c_undiscounted + b_to_c_discounted + simple_payback_time + npv_undiscounted + npv_discounted)]

    return dbc.Table(tbl_head + tab_body)

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
                " kWh/yr; ",
                get_icon('consumption-direct-ev'),
                " = ",
                html.Span("0.0", id="cons-smry-ev"),
                " kWh/yr"
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
                "/kWh"
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
                html.Span("0.0", id='gen-ressmry-wind-prod'),
                " kWh; ",
                get_icon('gen-pv'),
                " = ",
                html.Span("0.0", id='gen-ressmry-solar-prod'),
                " kWh"
            ],
            id='gen-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary("Wind Generation"),
                html.Div([
                    create_wind_results()
                    ],
                    id="gen-res-wind-tbl")
            ]),
            html.Details([
                html.Summary("Solar PV Generation"),
                html.Div([
                    create_pv_results()
                    ],
                    id="gen-res-pv-tbl")
            ]),

            html.Details([
                html.Summary("Total Generation"),
                html.Div([
                    create_combined_generation_results()
                    ],
                    id="gen-res-combined-tbl")
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
                html.Span("0", id='stor-ressmry-hours-full'),
                "; Hours empty = ",
                html.Span("0", id='stor-ressmry-hours-empty'),
                "; Charge cycles = ",
                html.Span("0", id='stor-ressmry-charge-cycles')
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Storage'),
                html.Div([
                    create_stor_results()
                ],
                id='stor-res-tbl')
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
                html.Span('0.0', id='cons-ressmry-resident'),
                ' kWh; ',
                get_icon('consumption-direct-ev'),
                ' = ',
                html.Span('0.0', id='cons-ressmry-ev'),
                ' kWh'                
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Consumption'),
                html.Div([
                    create_cons_results()
                ],
                id='cons-res-tbl')
            ]),

            html.Details([
                html.Summary('Seasonal Consumption'),
                html.Div([
                    create_seasonal_cons_results()
                ],
                id='cons-res-seasonal-tbl')
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
                html.Span('0.0', id = 'net-ressmry-export'),
                ' kWh; Annual import = ',
                html.Span('0.0', id = 'net-ressmry-import'),
                ' kWh; Storage losses = ',
                html.Span('0.0', id = 'net-ressmry-storloss'),
                ' kWh'
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Overall net energy'),
                html.Div([
                    create_net_results()
                ],
                id='net-res-tbl')
            ]),

            html.Details([
                html.Summary('Seasonal net energy'),
                html.Div([
                    create_seasonal_net_results()
                ],
                id='net-res-seasonal-tbl')
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
                html.Span('0%', id='econ-ressmry-dr-benefits'),
                ') = ',
                html.Span('£0.00', id='econ-ressmry-npbenefits'),
                '; Total costs (',
                html.Span('0%', id='econ-ressmry-dr-costs'),
                ') = ',
                html.Span('£0.00', id='econ-ressmry-npcosts'),
                '; NPV = ',
                html.Span('£0.00', id='econ-ressmry-npv'),
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Benefits'),
                html.Div([
                    create_so_benefits_results()
                ],
                id='econ-res-benefits-tbl')
            ]),

            html.Details([
                html.Summary('Costs'),
                html.Div([
                    create_so_costs_results()
                ],
                id='econ-res-cost-tbl')
            ]),

            html.Details([
                html.Summary('Value'),
                html.Div([
                    create_so_value_results()
                ],
                id='econ-res-value-tbl')
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
        dcc.Store(id='res-finance-so')
    ])
    ]

    return dbc.Container(mapview, fluid=False)

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

        odict = {'gen_input': gen_input,
                 'stor_input': stor_input,
                 'bc_input': bc_input,
                 'dc_input': dc_input,
                 'mc_input': mc_input}

        fnc = app.finance

        return json.dumps(odict), json.dumps(fnc.to_dict())

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
        Input('model-config', 'data'),
        prevent_initial_call=True
    )
    def sync_dc_inputs_to_store(mcfg):
        if mcfg is None:
            return no_update, no_update, no_update
        mcfg = json.loads(mcfg)
        dc_input = mcfg.get('dc_input', {})
        return (
            dc_input.get('efficiency_reduction', 0),
            dc_input.get('annual_residential_consumption_per_ev', 0),
            dc_input.get('n_evs_per_household', 0)
        )

    @app.callback(
        Output('cost-gen-wind-capex-input', 'value'),
        Output('cost-gen-wind-recurrent-input', 'value'),
        Output('cost-gen-pv-capex-input', 'value'),
        Output('cost-gen-pv-recurrent-input', 'value'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_cost_gen_inputs_to_store(fcfg):
        if fcfg is None:
            return no_update, no_update, no_update, no_update
        fcfg = json.loads(fcfg)
        uc = fcfg.get('unit_costs', {})
        return (
            uc.get('wind_capex_per_kw', 0),
            uc.get('wind_om_per_kw_year', 0),
            uc.get('pv_capex_per_kw', 0),
            uc.get('pv_om_per_kw_year', 0)
        )

    @app.callback(
        Output('cost-stor-bess-capex-input', 'value'),
        Output('cost-stor-bess-recurrent-input', 'value'),
        Input('finance-config', 'data'),
        prevent_initial_call=True
    )
    def sync_cost_stor_inputs_to_store(fcfg):
        if fcfg is None:
            return no_update, no_update
        fcfg = json.loads(fcfg)
        uc = fcfg.get('unit_costs', {})
        return (
            uc.get('bess_capex_per_kwh', 0),
            uc.get('bess_om_per_kwh_year', 0)
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
        Output('gen-res-wind-tbl', 'children'),
        Output('gen-res-pv-tbl', 'children'),
        Output('gen-res-combined-tbl', 'children'),
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
        Output('stor-res-tbl', 'children'),
        Input('res-stor', 'data'),
        Input('annual-horizon-toggle', 'value'),
        prevent_initial_call=True
    )
    def sync_stor_results_to_store(res, ann_hori_toggle):
        if res is None:
            return no_update
        res = json.loads(res)
        return create_stor_results(res, not(ann_hori_toggle))        

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
    def set_res_gen(_):
        """
        Create the storage results data after a completed model run
        """
        mdl = app.mdl

        print ("making stor results")
        stor_results = post_sprake_storage_results.stor_results_to_interface_sprake(mdl)
        return json.dumps(stor_results)

    return app

def add_model_callbacks(app):
    """
    Add callbacks to Dash App to allow for interfacing with a Sprake model
    """
    app = add_initial_callback(app)
    app = add_result_callbacks(app)

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
