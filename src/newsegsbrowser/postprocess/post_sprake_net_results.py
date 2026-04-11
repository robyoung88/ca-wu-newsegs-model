import numpy as np
import pandas as pd

from src.core.timespan import SEASON_NAMES
from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegsgeneration import newsegsgeneration
from src.newsegscs import newsegscs
from src.stats.core import assign_year_index, assign_peaktime_index, assign_season_index
from src.stats import basic_summary_stats

SEASON_NAMES_MAP = (
    pd.DataFrame(
        {
            'season_index': np.arange(4),
            'season': SEASON_NAMES
        }
    )
    .set_index('season_index')
)

def augment_indices_and_trim(df):
    return (
        df
        .pipe(assign_year_index)
        .pipe(assign_season_index)
        .query('year_index >= 0')
        .assign(season = lambda df: SEASON_NAMES_MAP.loc[df['season_index'],'season'].values)
        .drop(columns='season_index')
    )

def get_meters_by_year(df):
    return(
        df
        .drop(columns='season')
        .groupby('year_index')
        .sum()
    )

def get_meters_by_year_season(df):
    return (
        df
        .groupby(['year_index','season'])
        .sum()
    )

def combined_summary_year_season(df):
    yr = (
        get_meters_by_year(df)
        .assign(season='Year')
        .reset_index()
    )
    yrsn = (
        get_meters_by_year_season(df)
        .reset_index()
    )
    return (
        pd.concat([yr, yrsn])
        #.assign(season = lambda df: )
        .sort_values(['season','year_index'])
        .reset_index(drop=True)
    )

def get_seasonal_statistics(df):
    return(
        df
        .drop(columns='year_index')
        .groupby('season')
        .agg(['sum','mean','min','max'])
    )

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
        .pipe(basic_summary_stats.meter_annual_summary)
        .pipe(basic_summary_stats.meter_annual_summary_to_interface)
    )


    energy_ann = (
        energy_ann
        .pipe(assign_season_index)
        .assign(season = lambda df: SEASON_NAMES_MAP.loc[df['season_index'],'season'].values)
        .drop(columns='season_index')
    )

    #### Production for denominators

    energy_generated_ann = (
        newsegsgeneration.get_generation_meters(genr)
        .loc[:, 'generation_export']
        .pipe(augment_indices_and_trim)
    )

    production_summary = combined_summary_year_season(energy_generated_ann)

    #### Consumption for denominators

    energy_consumed_ann = (
        newsegscs.get_consumption_meters(conr)
        .loc[:, 'consumption']
        .pipe(augment_indices_and_trim)
    )

    consumption_summary = combined_summary_year_season(energy_consumed_ann)

    ####  

    energy_summary = combined_summary_year_season(energy_ann)

    energy_statistics = energy_summary.pipe(get_seasonal_statistics)

    def normalise_sums(meter_sums, denom_sums):
        df1 = meter_sums.set_index(['season', 'year_index'])
        denom = (
            denom_sums
            .set_index(['season', 'year_index'])
            .loc[df1.index,:]
            .iloc[:,0]
            .values
        )
        return df1.apply(lambda col: col/denom, axis = 0).reset_index()

    exports_normalised = normalise_sums(
        energy_summary.loc[:, ['grid_export', 'peak_grid_export', 'season', 'year_index']],
        production_summary
    )

    imports_normalised = normalise_sums(
        energy_summary.loc[:, ['grid_import', 'peak_grid_import', 'season', 'year_index']],
        consumption_summary
    )

    exports_norm_statistics = exports_normalised.pipe(get_seasonal_statistics)

    imports_norm_statistics = imports_normalised.pipe(get_seasonal_statistics)

    # For the sum statistics, need to overwrite with the appropriate sums
    production_seasonal_sum = production_summary.groupby('season')['generation_export'].sum()
    consumption_seasonal_sum = consumption_summary.groupby('season')['consumption'].sum()

    export_sums = energy_summary.loc[:, ['grid_export', 'peak_grid_export', 'season']].groupby('season').sum()
    import_sums = energy_summary.loc[:, ['grid_import', 'peak_grid_import', 'season']].groupby('season').sum()

    export_sums_normalised = (
        export_sums.apply(lambda col: col / production_seasonal_sum.values, axis=0)
    )
    export_sums_normalised.columns = pd.MultiIndex.from_product([export_sums_normalised.columns, ['sum']])

    import_sums_normalised = (
        import_sums.apply(lambda col: col / consumption_seasonal_sum.values, axis=0)
    )
    import_sums_normalised.columns = pd.MultiIndex.from_product([import_sums_normalised.columns, ['sum']])

    # Replace the offending columns
    exports_norm_statistics = (
        exports_norm_statistics
        .drop('sum', axis=1, level=1)
        .join(export_sums_normalised)
    )

    imports_norm_statistics = (
        imports_norm_statistics
        .drop('sum', axis=1, level=1)
        .join(import_sums_normalised)
    )

    results_to_interface['seasonal_statistics'] = energy_statistics

    results_to_interface['seasonal_statistics_normalised_export'] = exports_norm_statistics

    results_to_interface['seasonal_statistics_normalised_import'] = imports_norm_statistics

    return results_to_interface
