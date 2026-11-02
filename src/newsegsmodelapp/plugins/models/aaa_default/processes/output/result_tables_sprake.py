"""
Formatted AG Grid tables for the results section.

Functions:
- create_wind_results
- create_pv_results
- create_combined_generation_results
- create_stor_results
- create_cons_results
- create_seasonal_cons_results
- create_net_results
- create_seasonal_net_results
- create_so_benefits_results
- create_so_costs_results
- create_so_value_results
"""
from typing import Mapping
from functools import partial

import dash_ag_grid as dag
import pandas as pd

from newsegsmodelapp.components.layouts import results_table
from newsegsmodelapp.components import stats as newsegsbrowser_stats

def _as_data_list(data) -> list:
    """Results for a single configuration, or a list of them, as a list"""
    if data is None:
        data = {}
    if isinstance(data, Mapping):
        return [data]
    return data

def _create_grid(records: list[dict], n_configs: int, table_name: str, annual: bool) -> dag.AgGrid:
    grid_id = {'type': 'result-grid', 'table': table_name + ('_ann' if annual else '_hori')}
    return results_table.create_result_grid(records, n_configs, grid_id)

def create_wind_results(wind_data=None, annual=True) -> dag.AgGrid:
    """
    Create and format the wind generation results table
    """
    wind_data = _as_data_list(wind_data)

    if (annual):
        ann_gen = newsegsbrowser_stats.stat_description_records(
            wind_data,
            ['generator_meter_summary','wind_export'],
            'Wind production (kWh/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        ann_gen = newsegsbrowser_stats.stat_description_records(
            wind_data,
            ['generator_meter_summary', 'wind_export'],
            'Wind production (kWh)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

    hours_in_range = newsegsbrowser_stats.stat_description_compound_records(
        wind_data,
        'wind_production_categorised',
        'Hours in range',
        newsegsbrowser_stats.hours_in_range_formatter
    )

    longest_hours_below_5 = newsegsbrowser_stats.event_and_daterange_records(
        wind_data,
        'wind_continuous_hours_below_5pc',
        r"Longest continuous hours <5%",
        "hours",
        '{:,.1f}'.format
    )

    longest_hours_above_95 = newsegsbrowser_stats.event_and_daterange_records(
        wind_data,
        'wind_continuous_hours_above_95pc',
        r"Longest continuous hours ≥95%",
        "hours",
        '{:,.1f}'.format
    )

    if (annual):
        direct_sc = newsegsbrowser_stats.self_consumption_records(
            wind_data,
            ['self-consumption','yearly'],
            r'Wind-only self-consumption potential (kWh/yr (% production))',
            stat_list = newsegsbrowser_stats.ANNUAL_SC_STATS,
            index_filter='wind_export'
        )
    else:
        direct_sc = newsegsbrowser_stats.self_consumption_records(
            wind_data,
            ['self-consumption','horizon'],
            r'Wind-only self-consumption potential (kWh (% production))',
            stat_list = newsegsbrowser_stats.HORIZON_SC_STATS,
            index_filter='wind_export'
        )

    records = ann_gen + hours_in_range + longest_hours_below_5 \
        + longest_hours_above_95 + direct_sc

    return _create_grid(records, len(wind_data), 'table_generation_wind', annual)

def create_pv_results(pv_data=None, annual=True) -> dag.AgGrid:
    """Create pv results.

    TODO: Add a description.

    Args:
        pv_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    pv_data = _as_data_list(pv_data)

    if (annual):
        ann_gen = newsegsbrowser_stats.stat_description_records(
            pv_data,
            ['generator_meter_summary','solar_export'],
            'PV production (kWh/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        ann_gen = newsegsbrowser_stats.stat_description_records(
            pv_data,
            ['generator_meter_summary','solar_export'],
            'PV production (kWh)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

    max_day = newsegsbrowser_stats.event_and_date_records(
        pv_data,
        'max_solar_day',
        r'Maximum daily production (kWh)',
        'value',
        '{:,.1f}'.format
    )

    min_day = newsegsbrowser_stats.event_and_date_records(
        pv_data,
        'min_solar_day',
        r'Minimum daily production (kWh)',
        'value',
        '{:,.1f}'.format
    )

    days_in_range = newsegsbrowser_stats.stat_description_compound_records(
        pv_data,
        'pv_production_categorised',
        r'Daily production distribution as % of max [kWh range] days (%days)',
        stat_formatter = newsegsbrowser_stats.days_in_range_formatter,
        stat_list = newsegsbrowser_stats.DEFAULT_DAYS_IN_RANGE_STATS
    )

    if (annual):
        direct_sc = newsegsbrowser_stats.self_consumption_records(
            pv_data,
            ['self-consumption','yearly'],
            r'PV-only self-consumption potential (kWh/yr (% production))',
            stat_list = newsegsbrowser_stats.ANNUAL_SC_STATS,
            index_filter = 'solar_export'
        )
    else:
        direct_sc = newsegsbrowser_stats.self_consumption_records(
            pv_data,
            ['self-consumption','horizon'],
            r'PV-only self-consumption potential (kWh (% production))',
            stat_list = newsegsbrowser_stats.HORIZON_SC_STATS,
            index_filter='solar_export'
        )

    records = ann_gen + max_day + min_day + days_in_range + direct_sc

    return _create_grid(records, len(pv_data), 'table_generation_pv', annual)

def create_combined_generation_results(gen_data=None, annual=True) -> dag.AgGrid:
    """Create combined generation results.

    TODO: Add a description.

    Args:
        gen_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    gen_data = _as_data_list(gen_data)

    if (annual):
        ann_gen = newsegsbrowser_stats.stat_description_records(
            gen_data,
            ['generator_meter_summary','generation_export'],
            'Production (kWh/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        ann_gen = newsegsbrowser_stats.stat_description_records(
            gen_data,
            ['generator_meter_summary','generation_export'],
            'Production (kWh/yr)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

    max_day = newsegsbrowser_stats.event_and_date_records(
        gen_data,
        'max_generation_day',
        r'Maximum daily production (kWh)',
        'value',
        lambda x: '{:,.1f}'.format(x)
    )

    min_day = newsegsbrowser_stats.event_and_date_records(
        gen_data,
        'min_generation_day',
        r'Minimum daily production (kWh)',
        'value',
        lambda x: '{:,.1f}'.format(x)
    )

    days_in_range = newsegsbrowser_stats.stat_description_compound_records(
        gen_data,
        'generation_production_categorised',
        r'Daily production distribution (% of max) [kWh range] days (%days)',
        stat_formatter = newsegsbrowser_stats.days_in_range_formatter,
        stat_list = newsegsbrowser_stats.DEFAULT_DAYS_IN_RANGE_STATS)

    if (annual):
        direct_sc = newsegsbrowser_stats.self_consumption_records(
            gen_data,
            ['self-consumption','yearly'],
            r'Without storage self-consumption potential (kWh/yr (% production))',
            stat_list = newsegsbrowser_stats.ANNUAL_SC_STATS,
            index_filter='generation_export'
        )
    else:
        direct_sc = newsegsbrowser_stats.self_consumption_records(
            gen_data,
            ['self-consumption','horizon'],
            r'Without storage self-consumption potential (kWh/yr (% production))',
            stat_list = newsegsbrowser_stats.HORIZON_SC_STATS,
            index_filter='generation_export'
        )

    records = ann_gen + max_day + min_day + days_in_range + direct_sc

    return _create_grid(records, len(gen_data), 'table_generation_combined', annual)

def create_stor_results(stor_data=None, annual=True) -> dag.AgGrid:
    """Create stor results.

    TODO: Add a description.

    Args:
        stor_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    stor_data = _as_data_list(stor_data)

    if (annual):
        to_stor = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['to_stor_meter_summary', 'storage_import'],
            'Units to storage (kWh/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        from_stor = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['from_stor_meter_summary', 'storage_export'],
            'Units from storage (kWh/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        loss_stor = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['loss_stor_meter_summary', 'storage_loss'],
            'Units lost (kWh/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

        charge_cycles = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['no_charge_cycles', 'charge_cycles'],
            'Effective charge cycles (N/yr)',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}')

        hrs_min_soc = newsegsbrowser_stats.stat_description_parallel_records(
            stor_data,
            'stor_hours_at_min',
            r'Hours at min SoC (hrs/yr, (%))',
            'hrs_at_min_soc',
            'prop_hrs_at_min_soc',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS
        )

        hrs_max_soc = newsegsbrowser_stats.stat_description_parallel_records(
            stor_data,
            'stor_hours_at_max',
            r'Hours at max SoC (hrs/yr, (%))',
            'hrs_at_max_soc',
            'prop_hrs_at_max_soc',
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS
        )
    else:
        to_stor = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['to_stor_meter_summary', 'storage_import'],
            'Units to storage (kWh)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        from_stor = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['from_stor_meter_summary', 'storage_export'],
            'Units from storage (kWh)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
        loss_stor = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['loss_stor_meter_summary', 'storage_loss'],
            'Units lost (kWh)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )

        charge_cycles = newsegsbrowser_stats.stat_description_records(
            stor_data,
            ['no_charge_cycles','charge_cycles'],
            'Effective charge cycles (N)',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
            fmt='{:,.0f}')

        hrs_min_soc = newsegsbrowser_stats.stat_description_parallel_records(
            stor_data,
            'stor_hours_at_min',
            r'Hours at min SoC (hrs, (%))',
            'hrs_at_min_soc',
            'prop_hrs_at_min_soc',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS
        )

        hrs_max_soc = newsegsbrowser_stats.stat_description_parallel_records(
            stor_data,
            'stor_hours_at_max',
            r'Hours at max SoC (hrs, (%))',
            'hrs_at_max_soc',
            'prop_hrs_at_max_soc',
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS
        )

    longest_hrs_min_soc = newsegsbrowser_stats.event_and_daterange_records(
        stor_data,
        'max_continuous_hours_min_soc',
        r'Longest continuous hours at min SoC',
        'hours',
        '{:,.1f}'.format)

    longest_hrs_max_soc = newsegsbrowser_stats.event_and_daterange_records(
        stor_data,
        'max_continuous_hours_max_soc',
        r'Longest continuous hours at max SoC',
        'hours',
        '{:,.1f}'.format
    )

    max_charge_rate = newsegsbrowser_stats.event_and_date_records(
        stor_data,
        'max_charge_rate_time',
        r'Maximum charge rate (kW)',
        'value',
        '{:,.1f}'.format,
        trimdate=9
    )

    max_discharge_rate = newsegsbrowser_stats.event_and_date_records(
        stor_data,
        'max_discharge_rate_time',
        r'Maximum discharge rate (kW)',
        'value',
        '{:,.1f}'.format,
        trimdate=9
    )

    records = to_stor + from_stor + loss_stor + charge_cycles + hrs_min_soc + longest_hrs_min_soc \
        + hrs_max_soc + longest_hrs_max_soc + max_charge_rate + max_discharge_rate

    return _create_grid(records, len(stor_data), 'table_storage', annual)

def create_cons_results(cons_data=None, annual=True) -> dag.AgGrid:
    """Create cons results.

    TODO: Add a description.

    Args:
        cons_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    cons_data = _as_data_list(cons_data)

    if annual:
        psd = partial(
            newsegsbrowser_stats.stat_description_records,
            data_list = cons_data,
            stat_list = newsegsbrowser_stats.ANNUAL_DEFAULT_STATS,
            fmt='{:,.0f}'
        )
    else:
        psd = partial(
            newsegsbrowser_stats.stat_description_records,
            data_list = cons_data,
            stat_list = newsegsbrowser_stats.TOTAL_DEFAULT_STATS,
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

    max_day = newsegsbrowser_stats.event_and_date_records(
        cons_data,
        'max_consumption_day',
        r'Maximum daily consumption (kWh)',
        'value',
        '{:,.1f}'.format
    )

    min_day = newsegsbrowser_stats.event_and_date_records(
        cons_data,
        'min_consumption_day',
        r'Minimum daily consumption (kWh)',
        'value',
        '{:,.1f}'.format
    )

    admd = newsegsbrowser_stats.single_stat_records(
        cons_data,
        'admd_calculated',
        'ADMD - calculated (kW)',
        'value',
        fmt='{:,.0f}'
    )
    max_demand = newsegsbrowser_stats.event_and_date_records(
        cons_data,
        'admd_observed',
        'Maximum demand (kW)',
        'value',
        '{:,.0f}'.format
    )

    records = app_cons + dhw_cons + spaceheat_cons + residential_cons + perunit_residential_cons \
        + ev_cons + site_cons + admd + max_demand + min_day + max_day

    return _create_grid(records, len(cons_data), 'table_consumption', annual)

def create_seasonal_cons_results(cons_data=None, annual=True) -> dag.AgGrid:
    """Create seasonal cons results.

    TODO: Add a description.

    Args:
        cons_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    cons_data = _as_data_list(cons_data)

    if (annual):
        weekday_sitecons = newsegsbrowser_stats.seasonal_consumption_records(
            cons_data,
            ['seasonal_consumption','wd'],
            r'Weekday site demand (kWh/yr | kWh/day)',
            stat_list = newsegsbrowser_stats.ANNUAL_CONS_STATS
        )

        sat_sitecons = newsegsbrowser_stats.seasonal_consumption_records(
            cons_data,
            ['seasonal_consumption','sat'],
            r'Saturday site demand (kWh/yr | kWh/day)',
            stat_list = newsegsbrowser_stats.ANNUAL_CONS_STATS
        )

        sun_sitecons = newsegsbrowser_stats.seasonal_consumption_records(
            cons_data,
            ['seasonal_consumption','sun'],
            r'Sunday/holiday site demand (kWh/yr | kWh/day)',
            stat_list = newsegsbrowser_stats.ANNUAL_CONS_STATS
        )

    else:
        weekday_sitecons = newsegsbrowser_stats.seasonal_consumption_records(
            cons_data,
            ['seasonal_consumption','wd'],
            r'Weekday site demand (kWh | kWh/day)',
            stat_list = newsegsbrowser_stats.HORIZON_CONS_STATS
        )

        sat_sitecons = newsegsbrowser_stats.seasonal_consumption_records(
            cons_data,
            ['seasonal_consumption','sat'],
            r'Saturday site demand (kWh | kWh/day)',
            stat_list = newsegsbrowser_stats.HORIZON_CONS_STATS
        )

        sun_sitecons = newsegsbrowser_stats.seasonal_consumption_records(
            cons_data,
            ['seasonal_consumption','sun'],
            r'Sunday/holiday site demand (kWh | kWh/day)',
            stat_list = newsegsbrowser_stats.HORIZON_CONS_STATS
        )

    records = weekday_sitecons + sat_sitecons + sun_sitecons

    return _create_grid(records, len(cons_data), 'table_consumption_seasonal', annual)

def create_net_results(net_data=None, annual=True) -> dag.AgGrid:
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    """Create net results.

    TODO: Add a description.

    Args:
        net_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    net_data = _as_data_list(net_data)

    if (annual):
        meter_stats = newsegsbrowser_stats.present_single_stat_per_row(
            net_data,
            'meter_summaries',
            ['grid_export', 'grid_import', 'storage_loss', 'peak_grid_export', 'peak_grid_import'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_ANNUAL,
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
        meter_stats = newsegsbrowser_stats.present_single_stat_per_row(
            net_data,
            'meter_summaries',
            ['grid_export', 'grid_import', 'storage_loss', 'peak_grid_export', 'peak_grid_import'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
            fmt='{:,.0f}',
            variable_mapper = {
                'grid_export' : 'Export to grid (kWh)',
                'grid_import' : 'Import from grid (kWh)',
                'storage_loss' : 'Storage losses (kWh)',
                'peak_grid_export': 'Exports 5pm-8pm (kWh)',
                'peak_grid_import': 'Imports 5pm-8pm (kWh)',
            }
        )

    records = newsegsbrowser_stats.dataframe_records(meter_stats)

    return _create_grid(records, len(net_data), 'table_net', annual)

def create_seasonal_net_results(net_data=None, annual=True) -> dag.AgGrid:
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    """Create seasonal net results.

    TODO: Add a description.

    Args:
        net_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    net_data = _as_data_list(net_data)

    if (annual):
        export_stats = newsegsbrowser_stats.present_paired_seasonal_stats(
            net_data,
            'export_seasonal_statistics',
            'export_seasonal_statistics_normalised',
            ['grid_export', 'peak_grid_export'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_ANNUAL,
            variable_mapper = {
                'grid_export': r'Export to grid (kWh/yr (% production))',
                'peak_grid_export': r'Exports 5pm-8pm (kWh/yr (% production))'
            }
        )

        import_stats = newsegsbrowser_stats.present_paired_seasonal_stats(
            net_data,
            'import_seasonal_statistics',
            'import_seasonal_statistics_normalised',
            ['grid_import', 'peak_grid_import'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_ANNUAL,
            variable_mapper = {
                'grid_import': r'Import from grid (kWh/yr (% consumption))',
                'peak_grid_import': r'Imports 5pm-8pm (kWh/yr (% consumption))'
            }
        )
    else:
        export_stats = newsegsbrowser_stats.present_paired_seasonal_stats(
            net_data,
            'export_seasonal_statistics',
            'export_seasonal_statistics_normalised',
            ['grid_export', 'peak_grid_export'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
            variable_mapper = {
                'grid_export': r'Export to grid (kWh (% production))',
                'peak_grid_export': r'Exports 5pm-8pm (kWh (% production))'
            }
        )

        import_stats = newsegsbrowser_stats.present_paired_seasonal_stats(
            net_data,
            'import_seasonal_statistics',
            'import_seasonal_statistics_normalised',
            ['grid_import', 'peak_grid_import'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
            variable_mapper = {
                'grid_import': r'Import from grid (kWh (% consumption))',
                'peak_grid_import': r'Imports 5pm-8pm (kWh (% consumption))'
            }
        )

    records = newsegsbrowser_stats.dataframe_records(pd.concat([
        export_stats,
        import_stats
    ]))

    return _create_grid(records, len(net_data), 'table_net_seasonal', annual)

def create_so_benefits_results(econ_data=None, annual=True) -> dag.AgGrid:
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    """Create so benefits results.

    TODO: Add a description.

    Args:
        econ_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    econ_data = _as_data_list(econ_data)

    if (annual):
        receipt_stats = newsegsbrowser_stats.present_single_stat_per_row(
            econ_data,
            'undiscounted_receipts_summaries',
            ['receipts_resident', 'receipts_resident_perunit', 'receipts_ev', 'receipts_exports'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_ANNUAL,
            fmt='{:,.0f}',
            variable_mapper = {
                'receipts_resident': 'Resident receipts (£/yr)',
                'receipts_resident_perunit': 'Resident receipts (£/yr/household)',
                'receipts_ev': 'EV receipts (£/yr)',
                'receipts_exports': 'Export receipts (£/yr)',
            }
        )
    else:
        receipt_stats = newsegsbrowser_stats.present_single_stat_per_row(
            econ_data,
            'undiscounted_receipts_summaries',
            ['receipts_resident', 'receipts_resident_perunit', 'receipts_ev', 'receipts_exports'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
            fmt='{:,.0f}',
            variable_mapper = {
                'receipts_resident': 'Undiscounted resident receipts (£)',
                'receipts_resident_perunit': 'Undiscounted resident receipts (£/household)',
                'receipts_ev': 'Undiscounted EV receipts (£)',
                'receipts_exports': 'Undiscounted export receipts (£)',
            }
        )

    total_benefits = newsegsbrowser_stats.present_single_scalar(
        econ_data,
        'present_benefits_undiscounted',
        'Present benefits (undiscounted) (£)',
        'Total'
    )

    total_benefits_discounted = newsegsbrowser_stats.present_paired_scalars(
        econ_data,
        'present_benefits_discounted',
        'benefits_discount_rate',
        'Present benefits (discounted) (£)',
        'Total',
        fmt='{:,.2f} (@{:,.1%})'
    )

    records = newsegsbrowser_stats.dataframe_records(pd.concat([
        receipt_stats,
        total_benefits,
        total_benefits_discounted
    ]))

    return _create_grid(records, len(econ_data), 'table_finance_so_benefits', annual)

def create_so_costs_results(econ_data=None, annual=True) -> dag.AgGrid:
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    """Create so costs results.

    TODO: Add a description.

    Args:
        econ_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    econ_data = _as_data_list(econ_data)

    if (annual):
        recurring_stats = newsegsbrowser_stats.present_single_stat_per_row(
            econ_data,
            'undiscounted_variable_costs_summaries',
            ['import_costs', 'om_costs_gen', 'om_costs_stor', 'variable_costs'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_ANNUAL,
            fmt='{:,.0f}',
            variable_mapper = {
                'import_costs': 'Import costs (£/yr)',
                'om_costs_gen': 'O&M costs - generation (£/yr)',
                'om_costs_stor': 'O&M costs - storage (£/yr)',
                'variable_costs': 'Recurrent costs - total (£/yr)',
            }
        )

    else:
        recurring_stats = newsegsbrowser_stats.present_single_stat_per_row(
            econ_data,
            'undiscounted_variable_costs_summaries',
            ['import_costs', 'om_costs_gen', 'om_costs_stor', 'variable_costs'],
            statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
            fmt='{:,.0f}',
            variable_mapper = {
                'import_costs': 'Undiscounted import costs (£)',
                'om_costs_gen': 'Undiscounted O&M costs - generation (£)',
                'om_costs_stor': 'Undiscounted O&M costs - storage (£)',
                'variable_costs': 'Undiscounted recurrent costs - total (£)',
            }
        )

    capex_stats = newsegsbrowser_stats.present_single_stat_per_row(
        econ_data,
        'undiscounted_capex_summaries',
        ['capex_costs_gen', 'capex_costs_stor', 'capex_costs_dist', 'capex_costs_metering', 'capex_costs_total'],
        statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
        fmt='{:,.0f}',
        variable_mapper = {
            'capex_costs_gen': 'Capital costs - generation (£)',
            'capex_costs_stor': 'Capital costs - storage (£)',
            'capex_costs_dist': 'Capital costs - distribution and switching (£)',
            'capex_costs_metering': 'Capital costs - metering (£)',
            'capex_costs_total': 'Capital costs - total (£)'
        }
    )

    total_costs = newsegsbrowser_stats.present_single_scalar(
        econ_data,
        'present_costs_undiscounted',
        'Present costs (undiscounted) (£)',
        'Total'
    )

    total_costs_discounted = newsegsbrowser_stats.present_paired_scalars(
        econ_data,
        'present_costs_discounted',
        'costs_discount_rate',
        'Present costs (discounted) (£)',
        'Total',
        fmt='{:,.2f} (@{:,.1%})'
    )

    records = newsegsbrowser_stats.dataframe_records(pd.concat([
        recurring_stats,
        capex_stats,
        total_costs,
        total_costs_discounted,
    ]))

    return _create_grid(records, len(econ_data), 'table_finance_so_costs', annual)

def create_so_value_results(econ_data=None, annual=True) -> dag.AgGrid:
    # TODO: Load tables as appropriate at this stage to prevent multiple from_dict interprets
    """Create so value results.

    TODO: Add a description.

    Args:
        econ_data: TODO.
        annual: TODO.

    Returns:
        TODO.
    """
    econ_data = _as_data_list(econ_data)

    simple_stats = newsegsbrowser_stats.present_single_stat_per_row(
        econ_data,
        'value_summaries',
        ['benefit_cost_ratio_undiscounted', 'net_present_value_undiscounted', 'simple_payback_time_yrs'],
        statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
        fmt='{:,.2f}',
        variable_mapper = {
            'benefit_cost_ratio_undiscounted': 'Benefits/Costs (undiscounted)',
            'net_present_value_undiscounted': 'Net Present Value (£) (undiscounted)',
            'simple_payback_time_yrs': 'Simple payback time (years)'
        }
    )

    compound_stats = newsegsbrowser_stats.present_single_stat_per_row_plus_paired_scalars(
        econ_data,
        'value_summaries',
        ['benefit_cost_ratio_discounted', 'net_present_value_discounted'],
        'benefits_discount_rate',
        'costs_discount_rate',
        statistic_names = newsegsbrowser_stats.DEFAULT_STATISTICS_HORIZON,
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
    )
    if len(out_table) >= 5:
        out_table = out_table.iloc[[0,3,1,4,2],:]

    records = newsegsbrowser_stats.dataframe_records(out_table)

    return _create_grid(records, len(econ_data), 'table_finance_so_value', annual)
