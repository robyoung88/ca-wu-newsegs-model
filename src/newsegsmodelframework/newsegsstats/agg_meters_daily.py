"""Sum meters to daily totals.

This module provides a function to aggregate datetime-indexed meter
readings to daily totals while preserving the first datetime for each
day for convenience.
"""
import pandas as pd

from newsegsmodelframework.newsegsstats.core import assign_day_index

def agg_meters_daily(
    data: pd.DataFrame|pd.Series
) -> pd.DataFrame:
    """Sum values in a datetime-indexed DataFrame per day.

    Args:
        data (pd.DataFrame | pd.Series): Datetime-indexed data to aggregate.

    Returns:
        pd.DataFrame: DataFrame indexed by ``day_index`` containing summed
            values for each day and a ``datetime`` column with the first
            timestamp of that day.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()
    
    data = (
        data
        .pipe(assign_day_index)
    )
    return (
        data
        .groupby('day_index')
        .sum()
        .join(
            data
            .reset_index(names='datetime')
            .set_index('day_index')
            .loc[:,['datetime']]
            .groupby(level='day_index')
            .agg(lambda x: x.iloc[0])
        )
    )
