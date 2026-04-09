"""
Sum meters to daily totals
"""
import pandas as pd

from src.stats.core import assign_day_index

def agg_meters_daily(
    data: pd.DataFrame|pd.Series
) -> pd.DataFrame:
    """
    Sum values in a datetime-indexed dataframe per day.

    The returned dataframe includes the first datetime per day for
    convenience.
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
