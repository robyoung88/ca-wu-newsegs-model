"""Blocks of time and the constants and index functions used with them.

The classes (`TimeSpan`, `RegTimeSpan`, `OffsetRegTimeSpan`) are defined in the `timespan`
module.
"""
from .timespan import *

__all__ = [
    'SECONDS_IN_DAY',
    'SECONDS_TO_HOURS',
    'SECONDS_TO_DAYS',
    'NANOSECONDS_TO_DAYS',
    'SEASON_NAMES',
    'PEAK_PERIODS',
    'TimedeltaScalar',
    'TimeZoneScalar',
    'delta_days',
    'year_index',
    'season_index',
    'month_index',
    'day_index',
    'peaktime_index',
    'TimeSpan',
    'RegTimeSpan',
    'OffsetRegTimeSpan'
]
