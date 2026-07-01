"""
Summarise meter data by season.
"""
from typing import Tuple

import pandas as pd

from newsegsstats.core import assign_season_index, assign_year_index, grouped_default_stats, index_by, normalise_common_index

def get_meters_by_year_season(df: pd.DataFrame):
    """
    Dataframe of meter data summed within years, grouped by season
    """
    return (
        df
        .groupby(['season_index', 'year_index'])
        .sum()
    )

def year_season_to_seasonal_stats(df: pd.DataFrame,
                                  agg_operations = ['sum','mean','min','max']):
    """
    Summary statistics for yearly data grouped by season
    """
    if 'year_index' in df.columns:
        df = df.drop(columns='year_index')

    return grouped_default_stats(df, 'season_index', agg_operations)

def index_by_season_year(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure that the index of a data frame is set to year and season indices
    """
    return index_by(df, ['season_index', 'year_index'])

def normalised_year_season(meter_sums, denom_sums):
    """
    Normalise meter annual sums (by season) by a denominator series
    """
    return normalise_common_index(
        meter_sums,
        denom_sums,
        ['season_index', 'year_index']
    )

def add_year_as_season(df: pd.DataFrame):
    """
    Concatenate a meter sum with rows containing the sum over the year with season index 0
    """
    return pd.concat([
        (
            df
            .groupby('year_index')
            .sum()
            .assign(season_index = 0)
            .reset_index()
            .set_index(['season_index', 'year_index'])
        ),
        df
    ])

def _prepare_meters_with_indices(meters: pd.DataFrame|pd.Series) -> pd.DataFrame:
    """
    Ensure that dataframe is ready for year and season summaries.
    """
    if isinstance(meters, pd.Series):
        meters = meters.to_frame()

    if 'year_index' not in meters.columns:
        if 'year_index' in meters.index:
            meters = meters.reset_index()
        else:
            meters = meters.pipe(assign_year_index)
    
    if 'season_index' not in meters.columns:
        if 'season_index' in meters.index:
            meters = meters.reset_index()
        else:
            meters = meters.pipe(assign_season_index)
    
    return meters.loc[meters['year_index']>=0, :]

def summarise_meters_by_season(meters: pd.DataFrame) -> pd.DataFrame:
    """
    Summary stats for a meter df by season (including Year), stats over years.
    """
    meters = _prepare_meters_with_indices(meters)

    meters_sum = get_meters_by_year_season(meters).pipe(add_year_as_season)

    return year_season_to_seasonal_stats(meters_sum)

def summarise_normalise_meters_by_season(
    meters: pd.DataFrame,
    denominator_frame: pd.DataFrame
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Summary stats for a meter df by season (including Year), plus normalised stats.
    """
    meters = _prepare_meters_with_indices(meters)
    denominator_frame = _prepare_meters_with_indices(denominator_frame)

    meters_sum = get_meters_by_year_season(meters).pipe(add_year_as_season)
    denominator_sum = get_meters_by_year_season(denominator_frame).pipe(add_year_as_season)

    # Separate handling for sum and other statistics
    meters_norm = normalised_year_season(meters_sum, denominator_sum)
    non_sum_stats = year_season_to_seasonal_stats(meters_norm, agg_operations=['mean','min','max'])

    # For the sum statistics, we need to normalise after summing
    meters_sum_tot = year_season_to_seasonal_stats(meters_sum, agg_operations=['sum'])
    denominator_sum_tot = year_season_to_seasonal_stats(denominator_sum, agg_operations=['sum'])

    sum_stats = normalise_common_index(meters_sum_tot, denominator_sum_tot.loc[:,['season_index','value']], 'season_index', norm_cols='value')

    return (
        (
            year_season_to_seasonal_stats(meters_sum)
            .sort_values(['variable','season_index'])
            .reset_index(drop=True)
        ),
        (
            pd.concat([
                sum_stats,
                non_sum_stats
            ])
            .sort_values(['variable','season_index'])
            .reset_index(drop=True)
        )
    )
