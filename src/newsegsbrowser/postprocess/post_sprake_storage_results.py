import numpy as np
import pandas as pd

from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegscs import newsegscs
from src.stats.core import assign_year_index
from src.stats.core import assign_delta_hours
from src.stats import basic_summary_stats
from src.stats import time_in_range
from src.stats import locate_timeseries_extrema

# Will count minimum soc as < 1%
MIN_SOC_THRESHOLD_PROP = 0.01
MAX_SOC_THRESHOLD_PROP = 0.99

def stor_results_to_interface_sprake(
    mdl: SprakeModel
) -> dict:
    """
    Extracts the storage results required fro the Dash interface to Sprake model.
    """
    # This holds our final returned data structure
    results_to_interface = {}

    conr = mdl.get_consumption_storage_result()

    storage_capacity = mdl.consumption_storage.storage_params.get('storage_capacity')

    to_stor = newsegscs.get_storage_import_meters(conr)
    from_stor = newsegscs.get_storage_export_meters(conr)
    loss_stor = newsegscs.get_storage_loss_meters(conr)
    soc_stor = conr.dsm_to_pandas().loc[:,'storage_soc']

    to_stor_ann = to_stor.pipe(assign_year_index).query('year_index >= 0')
    from_stor_ann = from_stor.pipe(assign_year_index).query('year_index >= 0')
    loss_stor_ann = loss_stor.pipe(assign_year_index).query('year_index >= 0')

    results_to_interface['to_stor_meter_summary'] = (
        to_stor_ann
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    results_to_interface['from_stor_meter_summary'] = (
        from_stor_ann
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    results_to_interface['loss_stor_meter_summary'] = (
        loss_stor_ann
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    # TODO - Half-cycle correction
    min_soc_threshold = MIN_SOC_THRESHOLD_PROP * storage_capacity
    max_soc_threshold = MAX_SOC_THRESHOLD_PROP * storage_capacity

    results_to_interface['stor_hours_at_min'] = (
        (1.0 * (soc_stor <= min_soc_threshold))
        .pipe(assign_delta_hours)
        .assign(
            hrs_at_min_soc = lambda df: df['storage_soc'] * df['delta_hours']
        )
        .loc[:, 'hrs_at_min_soc']
        .pipe(assign_year_index)
        .query('year_index >= 0')
        .pipe(basic_summary_stats.meter_annual_summary)
        .assign(
            prop_hrs_at_min_soc = lambda df: df['hrs_at_min_soc'] / 8760.0 # NB - may result in > 1.0 for leap years
        )
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    results_to_interface['max_continuous_hours_min_soc'] = (
        time_in_range.max_continuous_time_in_range(
            soc_stor,
            -1000.0,
            min_soc_threshold,
            include_upper=True
        )
    )

    results_to_interface['stor_hours_at_max'] = (
        (1.0 * (soc_stor >= max_soc_threshold))
        .pipe(assign_delta_hours)
        .assign(
            hrs_at_max_soc = lambda df: df['storage_soc'] * df['delta_hours']
        )
        .loc[:, 'hrs_at_max_soc']
        .pipe(assign_year_index)
        .query('year_index >= 0')
        .pipe(basic_summary_stats.meter_annual_summary)
        .assign(
            prop_hrs_at_max_soc = lambda df: df['hrs_at_max_soc'] / 8760.0 # NB - may result in > 1.0 for leap years
        )
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    results_to_interface['max_continuous_hours_max_soc'] = (
        time_in_range.max_continuous_time_in_range(
            soc_stor,
            max_soc_threshold,
            storage_capacity * 10.0,
            include_lower=True
        )
    )

    results_to_interface['no_charge_cycles'] = (
        from_stor_ann
        .assign(charge_cycles = lambda df: df['storage_export'] / storage_capacity)
        .loc[:,['charge_cycles','year_index']]
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )

    maximum_charge_rate = (
        to_stor
        .pipe(assign_delta_hours)
        .query('delta_hours > 0')
        .assign(
            charge_power = lambda df: df['storage_import'] / df['delta_hours']
        )
        .loc[:, 'charge_power']
    )

    results_to_interface['max_charge_rate_time'] = (
        locate_timeseries_extrema.report_ts_max(
            maximum_charge_rate
        )
    )

    maximum_discharge_rate = (
        from_stor
        .pipe(assign_delta_hours)
        .query('delta_hours > 0')
        .assign(
            discharge_power = lambda df: df['storage_export'] / df['delta_hours']
        )
        .loc[:, 'discharge_power']
    )
    results_to_interface['max_dicharge_rate_time'] = (
        locate_timeseries_extrema.report_ts_max(
            maximum_discharge_rate
        )
    )

    return results_to_interface
