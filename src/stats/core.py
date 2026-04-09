"""
Core functions used by multiple statistical procedures.
"""
import numpy as np
import numpy.typing as npt
import pandas as pd

from src.core import SECONDS_TO_HOURS
from src.core.timespan import year_index, season_index, day_index

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
