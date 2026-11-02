"""Blocks of time and the constants and index functions used with them.

The classes (`TimeSpan`, `RegTimeSpan`, `OffsetRegTimeSpan`) and the functions that index
datetimes by year, season, month, day and peak period are defined in the `timespan` module.
"""
from .timespan import (
    SECONDS_TO_HOURS,
    SEASON_NAMES,
    PEAK_PERIODS,
    delta_days,
    year_index,
    season_index,
    month_index,
    day_index,
    peaktime_index,
    TimeSpan,
    RegTimeSpan,
    OffsetRegTimeSpan,
    timespan_from_dict,
)

__all__ = [
    'SECONDS_TO_HOURS',
    'SEASON_NAMES',
    'PEAK_PERIODS',
    'delta_days',
    'year_index',
    'season_index',
    'month_index',
    'day_index',
    'peaktime_index',
    'TimeSpan',
    'RegTimeSpan',
    'OffsetRegTimeSpan',
    'timespan_from_dict'
]
