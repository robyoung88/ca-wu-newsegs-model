import numpy as np
import pandas as pd

from src.core.timespan import SEASON_NAMES
from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegsgeneration import newsegsgeneration
from src.newsegscs import newsegscs
from src.stats.core import assign_year_index, assign_peaktime_index, assign_season_index
from src.stats import basic_summary_stats
from src.stats import seasonal_statistics

def net_results_to_interface_sprake(
    mdl: SprakeModel
) -> dict:
    """
    Extracts the net energy flow results required for the Dash interface.
    """
    # This holds our final returned data structure
    results_to_interface = {}

    genr = mdl.get_generation_result()
    conr = mdl.get_consumption_storage_result()

    energy_export = newsegscs.get_site_export_meters(conr)
    energy_import = newsegscs.get_site_import_meters(conr)
    energy_losses = newsegscs.get_storage_loss_meters(conr)

    energy_combined = (
        energy_export
        .join(energy_import)
        .join(energy_losses)
        .pipe(assign_peaktime_index)
        .assign(
            peak_grid_export = lambda df: df['grid_export'] * df['peaktime_index'],
            peak_grid_import = lambda df: df['grid_import'] * df['peaktime_index']
        )
        .drop(columns=['peaktime_index'])
    )

    energy_ann = (
        energy_combined
        .pipe(assign_year_index)
        .query('year_index >= 0')
    )

    results_to_interface['meter_summaries'] = (
        energy_ann
        .pipe(basic_summary_stats.meter_annual_summary2)
        .pipe(basic_summary_stats.meter_annual_summary2_to_interface)
    )

    export_seas_stats, export_seas_stats_norm = seasonal_statistics.summarise_normalise_meters_by_season(
        energy_combined.loc[:, ['grid_export', 'peak_grid_export']],
        newsegsgeneration.get_generation_meters(genr).loc[:, 'generation_export']
    )

    import_seas_stats, import_seas_stats_norm = seasonal_statistics.summarise_normalise_meters_by_season(
        energy_combined.loc[:, ['grid_import', 'peak_grid_import']],
        newsegscs.get_consumption_meters(conr).loc[:, 'consumption']
    )

    results_to_interface['export_seasonal_statistics'] = export_seas_stats.to_dict(orient='list')

    results_to_interface['export_seasonal_statistics_normalised'] = export_seas_stats_norm.to_dict(orient='list')

    results_to_interface['import_seasonal_statistics'] = import_seas_stats.to_dict(orient='list')

    results_to_interface['import_seasonal_statistics_normalised'] = import_seas_stats_norm.to_dict(orient='list')

    return results_to_interface
