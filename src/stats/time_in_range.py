"""
Statistics for time spent by meter readings within ranges.
"""
from functools import partial

import numpy as np
import numpy.typing as npt
import pandas as pd

from src.stats.core import assign_delta_hours

def in_range(
    timeseries: npt.NDArray|pd.Series,
    minimum: float,
    maximum: float,
    include_lower: bool = True,
    include_upper: bool = False
) -> npt.NDArray[bool]:
    """
    Indicates whether values in array are in range.
    """
    match include_lower:
        case False:
            match include_upper:
                case False:
                    return np.logical_and(timeseries > minimum, timeseries < maximum)
                case _:
                    return np.logical_and(timeseries > minimum, timeseries <= maximum)
        case _:
            match include_upper:
                case False:
                    return np.logical_and(timeseries >= minimum, timeseries < maximum)
                case _:
                    return np.logical_and(timeseries >= minimum, timeseries <= maximum)

def in_range_intervals_unclosed(
    timeseries: pd.Series,
    minimum: float,
    maximum: float,
    include_lower: bool = True,
    include_upper: bool = False
) -> pd.DataFrame:
    """
    A worker to provide opening and closing times for value-in-range intervals.
    """
    kwargs = locals()
    kwargs.pop('timeseries')
    in_rng = partial(in_range, **kwargs)

    ts_name = timeseries.name

    working_df = (
        timeseries
        .pipe(assign_delta_hours)
        .query('delta_hours > 0')
        .assign(in_range = lambda df: in_rng(df[ts_name]))
        .assign(
            lead_in_range = lambda df: df['in_range'].shift(1, fill_value = False),
            lag_in_range = lambda df: df['in_range'].shift(-1, fill_value = False),
            starting_sequence = lambda df: np.logical_and(
                df['in_range'],
                np.logical_not(df['lead_in_range'])
            ),
            ending_sequence = lambda df: np.logical_and(
                df['in_range'],
                np.logical_not(df['lag_in_range'])
            )
        )
    )

    intervals = (
        working_df
        .query('starting_sequence | ending_sequence')
        .reset_index()
        .rename(columns={'index': 'datetime'})
    )

    return intervals

def continuous_time_in_range(
    timeseries: pd.Series,
    minimum: float,
    maximum: float,
    include_lower: bool = True,
    include_upper: bool = False
) -> pd.DataFrame:

    kwargs = locals()
    intervals = in_range_intervals_unclosed(**kwargs)

    # Deal separately with single-timestep intervals and multiple-timestep intervals
    is_single = np.logical_and(
        intervals['starting_sequence'],
        intervals['ending_sequence']
    )

    if np.any(is_single):
        singles = (
            intervals.loc[is_single, :]
            .rename(columns = {'datetime': 'datetime_end',
                               'delta_hours': 'hours'})
            .assign(
                datetime_start = lambda df: \
                    df['datetime_end'] - pd.Timedelta(df['hours'].values[0], 'h')
            )
            .loc[:, ['datetime_start','datetime_end','hours']]
        )
    else:
        singles = None

    is_plural = np.logical_not(is_single)
    if np.any(is_plural):
        plurals = (
            intervals.loc[is_plural, :]
            .assign(
                datetime_start = lambda df: \
                    (df['datetime'] - pd.Timedelta(df['delta_hours'].values[0], 'h')).shift(1))
            .query('ending_sequence')
            .rename(columns = {'datetime': 'datetime_end'})
            .assign(interval_length = lambda df: df['datetime_end'] - df['datetime_start'],
                    hours = lambda df: \
                        df['interval_length'].dt.days * 24.0 + df['interval_length'].dt.seconds / 3600.0)
            .loc[:, ['datetime_start','datetime_end','hours']]
        )
    else:
        plurals = None
    
    return pd.concat([singles, plurals]).sort_values('datetime_end')

def max_continuous_time_in_range(
    timeseries: pd.Series,
    minimum: float,
    maximum: float,
    include_lower: bool = True,
    include_upper: bool = False
) -> dict:

    kwargs = locals()
    intervals = in_range_intervals_unclosed(**kwargs)
    
    # Deal with case that all intervals are one timestep long
    if np.all(np.logical_and(
        intervals['starting_sequence'],
        intervals['ending_sequence'])
    ): 
        # Arbitrarily act as though it's the first interval that counts
        x = intervals.iloc[0, :]
        tdelta = x['delta_hours']
        return {
            'datetime_start': str(x['datetime'] - pd.Timedelta(tdelta, 'h')),
            'datetime_end': str(x['datetime']),
            'hours': tdelta
        }
    
    intervals = (
        intervals
        .query('starting_sequence != ending_sequence')
        .assign(seq_start = lambda df: (df['datetime'] - pd.Timedelta(df['delta_hours'].values[0], 'h')).shift(1))
        .query('ending_sequence')
        .assign(interval_length = lambda df: df['datetime'] - df['seq_start'])
        .sort_values('interval_length', ascending=False)
    )

    # Although there may be multiple maxima, just choose the first
    x = intervals.iloc[0, :]
    return {
        'datetime_start': str(x['seq_start']),
        'datetime_end': str(x['datetime']),
        'hours': x['interval_length'].days * 24.0 + x['interval_length'].seconds / 3600.0
    }

