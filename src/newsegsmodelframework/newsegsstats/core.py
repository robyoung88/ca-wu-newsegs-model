"""
Core functions used by multiple statistical procedures.
"""
from collections.abc import Collection
import warnings

import numpy as np
import numpy.typing as npt
import pandas as pd

from newsegsmodelframework.core import SECONDS_TO_HOURS
from newsegsmodelframework.core.timespan import year_index, season_index, day_index, peaktime_index, PEAK_PERIODS
from newsegsmodelframework.core.timespan import month_index

def assign_delta_hours(
    data: pd.DataFrame|pd.Series
) -> pd.DataFrame:
    """
    Augment a datetime-indexed dataframe with the time difference.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    if 'datetime' in data.columns:
        datetime = data.loc[:, 'datetime']
    else:
        datetime = pd.Series(data.index)

    return (
        data
        .assign(
            delta_hours = (
                (
                    datetime  - datetime.shift(1, fill_value = datetime.iloc[0])
                ).dt.seconds * SECONDS_TO_HOURS
            ).values
    ))

def assign_year_index(
        data: pd.DataFrame|pd.Series,
        shift: int = 1,
) -> pd.DataFrame:
    """
    Augment a datetime-indexed meter dataframe with the year index.

    The year index will be shifted by default so that the zeroth time node
    is set to year -1, assuming that meters are retrospective (i.e. sum
    over previous timestep)
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    if "year_index" in data.columns:
        raise UserWarning('year_index is already present in data')
    ann_data = data.assign(year_index = lambda df: year_index(pd.Series(df.index)))

    if shift > 0:
        ann_data = ann_data.assign(year_index = lambda df: df['year_index'].shift(shift, fill_value=-1))
    elif shift <0:
        ann_data = ann_data.assign(year_index = lambda df: df['year_index'].shift(shift, fill_value=df['year_index'].iloc[-1]))
    
    return ann_data

def assign_season_index(
        data: pd.DataFrame|pd.Series,
        shift: int = 1,
) -> pd.DataFrame:
    """
    Augment a datetime-indexed meter dataframe with the season index.

    The seson index will be shifted by default , assuming that meters 
    are retrospective (i.e. sum over previous timestep). Fill values
    for shifts are LOCF/LOCB
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    if "season_index" in data.columns:
        raise UserWarning('season_index is already present in data')
    ann_data = data.assign(season_index = lambda df: season_index(pd.Series(df.index)))

    if shift > 0:
        ann_data = ann_data.assign(season_index = lambda df: df['season_index'].shift(shift, fill_value=df['season_index'].iloc[0]))
    elif shift <0:
        ann_data = ann_data.assign(season_index = lambda df: df['season_index'].shift(shift, fill_value=df['season_index'].iloc[-1]))
    
    return ann_data

def assign_month_index(
    data: pd.DataFrame|pd.Series,
    shift: int = -1,
) -> pd.DataFrame:
    """
    Augment a datetime-indexed meter dataframe with the month index.

    The month index will be shifted by default, assuming that meters
    are retrospective (i.e. sum over previous timestep).
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()
    
    if "month_index" in data.columns:
        warnings.warn('month_index is already present in data and will be overwritten')
    mon_data = data.assign(month_index = lambda df: month_index(pd.Series(df.index)))

    if shift > 0:
        mon_data = mon_data.assign(
            month_index = lambda df: df['month_index'].shift(shift, fill_value=df['month_index'].iloc[0])
        )
    elif shift <0:
        mon_data = mon_data.assign(
            month_index = lambda df: df['month_index'].shift(shift, fill_value=df['month_index'].iloc[-1]))
    
    return mon_data

def assign_peaktime_index(
    data: pd.DataFrame|pd.Series,
    shift: int = 0,
    peak_periods = PEAK_PERIODS
) -> pd.DataFrame:
    """
    Augment a datetime-indexed meter dataframe with an indicator for peak times.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    if "peaktime_index" in data.columns:
        raise UserWarning('peaktime_index is already present in data')
    
    ann_data = data.assign(peaktime_index = lambda df: peaktime_index(df.index, peak_periods=peak_periods))

    if shift > 0:
        ann_data = ann_data.assign(season_index = lambda df: df['peaktime_index'].shift(shift, fill_value=df['peaktime_index'].iloc[0]))
    elif shift < 0:
        ann_data = ann_data.assign(season_index = lambda df: df['peaktime_index'].shift(shift, fill_value=df['peaktime_index'].iloc[-1]))
    
    return ann_data

def assign_day_index(
    data: pd.DataFrame|pd.Series,
    shift: int = 1,
    ref_datetime: pd.Timestamp|None = None
) -> pd.DataFrame:
    """
    Augment a datetime-indexed meter dataframe with the day index.

    The day index will be shifted by default so that the zeroth time node
    is set to day -1, i.e. assuming that meter data is retrospective (i.e.
    sum over previous timestep)

    Days run relative to the first time node or reference_datetime, not 
    midnight to midnight.
    """
    if isinstance(data, pd.Series):
        data = data.to_frame()

    if "day_index" in data.columns:
        raise UserWarning('day_index is already present in data')
    
    dt_series = pd.Series(data.index)
    
    if ref_datetime is None:
        ref_datetime = dt_series.iloc[0]
    day_data = data.assign(day_index = day_index(dt_series, ref_datetime))

    if shift > 0:
        day_data = day_data.assign(
            day_index = lambda df: \
                df['day_index'].shift(
                    shift, 
                    fill_value=-1
                )
        )
    elif shift <0:
        day_data = day_data.assign(
            day_index = lambda df: \
                df['day_index'].shift(
                    shift, 
                    fill_value=df['day_index'].iloc[-1]
                    )
            )
    
    return day_data

def grouped_default_stats(
    df: pd.DataFrame,
    grouping_vars = 'season_index',
    agg_operations = ['sum','mean','min','max']
) -> pd.DataFrame:
    """
    Default format for statistics grouped by at least one variable.
    """
    return (
        df
        .groupby(grouping_vars)
        .agg(agg_operations)
        .melt(ignore_index=False)
        .rename(columns = {
            'variable_0': 'variable',
            'variable_1': 'statistic'
        })
        .reset_index()
    )

def index_by(df: pd.DataFrame|pd.Series, index_vars: Collection) -> pd.DataFrame:
    """
    Ensure that dataframe is indexed by some list of variables
    """
    if isinstance(df, pd.Series):
        df = df.to_frame()

    if isinstance(index_vars, str):
        if len(df.index.names) == 1:
            if df.index.names[0] is None:
                return df.set_index(index_vars)
            if df.index.names[0] == index_vars:
                return df
            return df.reset_index().set_index(index_vars)
        else:
            return df.reset_index().set_index(index_vars)

    if set(df.index.names) == set(index_vars):
        return df
    
    if df.index.names is None:
        return df.set_index(index_vars)
    
    return df.reset_index().set_index(index_vars)

def normalise_common_index(
    df: pd.DataFrame,
    denom: pd.DataFrame,
    index_vars: Collection,
    norm_cols: Collection|None = None
) -> pd.DataFrame:
    """
    Matching the denom by index, divide through df by denom.

    The first non-index column of the denom dataframe will be the denominator.
    """
    df = index_by(df, index_vars)
    denominator = (
        denom
        .pipe(index_by, index_vars = index_vars)
        .loc[df.index, :]
        .iloc[:, 0]
        .values
    )

    if norm_cols is None:
        norm_cols = list(df.columns)

    return df.apply(lambda col: col/denominator if col.name in norm_cols else col, axis = 0).reset_index()
