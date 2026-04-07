# Avoid problem of TimeSpan __init__ annotation referencing TimeSpan before it is in namespace
from __future__ import annotations

from copy import copy
from functools import singledispatchmethod
import operator
from typing import TypeAlias,overload
import numpy as np
import pandas as pd
from datetime import timedelta, tzinfo
import zoneinfo
import pytz
import dateutil
from pandas.core.tools.datetimes import DatetimeScalar, Timedelta
import numpy.typing as npt

SECONDS_TO_HOURS = 1.0 / 3600.0

# -----------------------------------------------------------------------------
# Ways of defining and comparing blocks of time

TimedeltaScalar: TypeAlias = Timedelta|timedelta|np.timedelta64|str|int|float
TimeZoneScalar: TypeAlias = str|tzinfo

class TimeSpan:
    _tz = 'utc'

    @singledispatchmethod
    def __init__(
        self, 
        start: TimeSpan | DatetimeScalar,
        end: DatetimeScalar | None = None,
        tz: TimeZoneScalar|None = None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('`start` must be an identifiable date, is %s', start)
        
    # Copy constructor is registered at the bottom
    # for late-binding
    
    @__init__.register(DatetimeScalar)
    def _from_dates(self, start: DatetimeScalar, end: DatetimeScalar, tz: TimeZoneScalar|None = None):
        self.start = start
        self.end = end
        if tz is not None:
            self.tz = tz
    
    # If we are using single dispatch, then we are unable
    # to use a "None" first argument for a default constructor
    # To get around this, we will use a class method
    @classmethod
    def from_none(cls):
        return cls("2002-01-01T00:00:00", "2015-01-01T00:00:00")

    def _post_calc(self):
        """
        Calculations that should occur once a change in a key property has occurred
        """
        if hasattr(self, "_start_dt"):
            if hasattr(self, "_tz"):
                if not self._start_dt.tz == self._tz:
                    self._tz = self._start_dt.tz
                if hasattr(self, "_end_dt"):
                    if not self._end_dt.tz == self._tz:
                        self._end_dt = TimeSpan.rationalise_datetime(self._end_dt, self._tz)
            if hasattr(self, "_end_dt"):
                self._delta = self._end_dt - self._start_dt

    @staticmethod
    def rationalise_datetime(this_datetime:DatetimeScalar, tz:TimeZoneScalar|None=None):
        if not (isinstance(this_datetime, pd.Timestamp)):
            this_datetime = pd.Timestamp(this_datetime, tz=tz)
        elif not(tz is None) and not (this_datetime.tz == pd.Timestamp("2012-01-01T00:00:00", tz=tz).tz):
            try:
                this_datetime = this_datetime.tz_convert(tz)
            except TypeError:
                this_datetime = this_datetime.tz_localize(tz)
        return this_datetime
    
    @property
    def start(self):
        return self._start_dt

    @start.setter
    def start(self, start_datetime:DatetimeScalar):
        if hasattr(start_datetime, 'tz'):
            self.set_start(start_datetime)
        elif hasattr(self, '_tz'):
            self.set_start(start_datetime, self._tz)
        else:
            self.set_start(start_datetime)

    def set_start(self, start_datetime:DatetimeScalar, tz:TimeZoneScalar|None=None):
        self._start_dt = TimeSpan.rationalise_datetime(start_datetime, tz)
        self._tz = self._start_dt.tz
        self._post_calc()

    @property
    def end(self):
        return self._end_dt
        
    @end.setter
    def end(self, end_datetime:DatetimeScalar):
        if hasattr(end_datetime, 'tz'):
            self.set_end(end_datetime)
        elif hasattr(self, '_tz'):
            self.set_end(end_datetime, self._tz)
        else:
            self.set_end(end_datetime)

    def set_end(self, end_datetime:DatetimeScalar, tz:TimeZoneScalar|None=None):
        self._end_dt = TimeSpan.rationalise_datetime(end_datetime, tz)
        self._post_calc()

    @property
    def tz(self):
        if hasattr(self, "_tz"):
            return self._tz
        else:
            return None

    @tz.setter
    def tz(self, tz:TimeZoneScalar|None):
        if hasattr(self, '_start_dt'):
            self._start_dt = TimeSpan.rationalise_datetime(self._start_dt, tz)
        if hasattr(self, '_end_dt'):
            self._end_dt = TimeSpan.rationalise_datetime(self._end_dt, tz)
        #self._tz = self._start_dt.tz
        self._post_calc()

    @property
    def delta(self) -> pd.Timedelta|None:
        if hasattr(self, '_delta'):
            return self._delta
        else:
            return None

    def set_delta(self, time_delta:TimedeltaScalar):
        if isinstance(time_delta, pd.Timedelta):
            self.end = self.start + pd.Timedelta(time_delta)
        else:
            self.end = self.start + pd.Timedelta(time_delta, unit='h')

    @classmethod
    def from_dates(cls, start_datetime: DatetimeScalar, end_datetime: DatetimeScalar, tz:TimeZoneScalar|None='utc'):
        o = cls()
        o.start = start_datetime
        o.end = end_datetime
        if not (tz is None):
            o.tz = tz
        return o
    
    @classmethod
    def from_date_delta(cls, start_datetime:DatetimeScalar, time_delta:TimedeltaScalar, tz:TimeZoneScalar|None='utc'):
        o = cls()
        o.start = start_datetime
        if type(time_delta in ('str','int','float')):
            o.end = o.start + pd.Timedelta(time_range, unit='h')
        else:
            o.end = o.start + pd.Timedelta(time_range)
        if not (tz is None):
            o.tz = tz
        
        return o

    @classmethod
    def from_timespan(cls, timespan:TimeSpan):
        return cls(timespan)

    def __str__(self):
        return str(self.start) + " - " + str(self.end)

    def __lt__(self, other:TimeSpan) -> bool:
        """
        Does this time span start before other?
        """
        return (self.start < other.start)
    
    def __le__(self, other:TimeSpan) -> bool:
        """
        Does this time span start at or before other?
        """
        return (self.start <= other.start)

    def __eq__(self, other:TimeSpan) -> bool:
        """
        Do both start and end of time spans match?
        """
        return (self.start == other.start) and (self.end == other.end)

    def __ne__(self, other:TimeSpan) -> bool:
        """
        Do not both start and end of time spans match?
        """
        return (self.start != other.start) or (self.end != other.end)

    def __ge__(self, other:TimeSpan) -> bool:
        """
        Does this time span end at or after other?
        """
        return (self.end >= other.end)

    def __gt__(self, other:TimeSpan) -> bool:
        """
        Does this time span end after other?
        """
        return (self.end > other.end)
    
    def __add__(self, time_delta:TimedeltaScalar):
        o = copy(self)
        o.end = o.end + pd.Timedelta(time_delta)
        return o
    
    def __sub__(self, time_delta:TimedeltaScalar):
        o = copy(self)
        o.end = o.end - pd.Timedelta(time_delta)
        return o

    def __mul__(self, times:int|float):
        o = copy(self)
        o.end = o.start + o.delta * times
        return o
    
    def __truediv__(self, denom:int|float):
        o = copy(self)
        o.end = o.start + o.delta / denom
        return o

# TimeSpan copy constructor
@TimeSpan.__init__.register(TimeSpan)
def TimeSpan_from_other(self, start: TimeSpan, end: None = None):
    """
    Initialise a TimeSpan using another TimeSpan
    """
    self._start_dt = start.start
    self._end_dt = start.end
    self._tz = start.tz
    self._post_calc()

setattr(TimeSpan, '_from_other', TimeSpan_from_other)

class RegTimeSpan(TimeSpan):
    """
    A TimeSpan which strides between its start and end in equally-spaced TimeDeltas
    """

    def __init__(self, other:TimeSpan|None=None) -> None:
        super().__init__(other)
        if not (other is None):
            if isinstance(other, RegTimeSpan):
                self._timestep = other.timestep
    
    def _post_calc(self):
        """
        Calculations that should occur once a change in a key property has occurred
        """
        super()._post_calc()
        if hasattr(self, "_timestep"):
            if hasattr(self, "_delta"):
                self._n = self.delta // self.timestep

    @property
    def timestep(self) -> pd.Timedelta:
        return self._timestep
    
    @timestep.setter
    def timestep(self, timestep:TimedeltaScalar) -> None:
        self.set_timestep(timestep)
    
    def set_timestep(self, timestep:TimedeltaScalar, unit=None) -> None:
        if isinstance(timestep, pd.Timedelta):
            self._timestep = pd.Timedelta(timestep)
        elif not unit is None:
            self._timestep = pd.Timedelta(timestep, unit = unit)
        else:
            if isinstance(timestep, str):
                self._timestep = pd.Timedelta(timestep)
            else:
                self._timestep = pd.Timedelta(timestep, unit = "h")
        self._post_calc()

    @classmethod
    def from_dates(cls, start_datetime: DatetimeScalar, end_datetime: DatetimeScalar, timestep:TimedeltaScalar, tz:TimeZoneScalar|None='utc', unit=None):
        o = super(RegTimeSpan, cls).from_dates(start_datetime,end_datetime,tz)
        o.set_timestep(timestep, unit)
        return o

    @property
    def n_interval(self):
        return self._n

    @property
    def n_node(self):
        return self._n + 1

    @property
    def end_timeseries(self):
        """
        The actual final time of the time series - may differ from end depending on timestep
        """
        return self.start + self.n_interval * self.timestep

    def to_pandas(self):
        return pd.date_range(self.start,self.end,freq=self.timestep)
    
    def __str__(self):
        return str(self.start) + " - " + str(self.end) + ", timestep: " + str(self.timestep)

    def __eq__(self, other:RegTimeSpan) -> bool:
        """
        Do start, end and timestep of time spans match?
        """
        return (self.start == other.start) and (self.end == other.end) and (self.timestep == other.timestep)

    def __ne__(self, other:RegTimeSpan) -> bool:
        """
        Do not start, end and timestep of time spans match?
        """
        return not(self == other)

class OffsetRegTimeSpan(RegTimeSpan):
    """
    A regular timespan which is offset from another timespan by a fixed number of timesteps

    The purpose of this class is to allow a small timeseries to be repeated (with offset) to represent a longer timeseries which may start at a different time.
    """
    def __init__(self, other:TimeSpan|None=None) -> None:
        self._offset_initialised = False
        super().__init__(other)
        if not (other is None):
            if isinstance(other, OffsetRegTimeSpan):
                self._offset_initialised = other.offset_initialised
                self._local_start = other.local_start
                self._remote_start = other.remote_start

    @property 
    def offset_initialised(self):
        return self._offset_initialised    

    @property
    def local_start(self) -> pd.Timestamp:
        return self._local_start
    
    @property
    def remote_start(self) -> pd.Timestamp:
        return self._remote_start

    def set_offset(self, 
                   local_start:DatetimeScalar, 
                   remote_start:DatetimeScalar):
        if not(isinstance(local_start, pd.Timestamp)):
            local_start = pd.Timestamp(local_start, tz=self.tz)
        if not(isinstance(remote_start, pd.Timestamp)):
            remote_start = pd.Timestamp(remote_start, tz=self.tz)
        self._local_start = local_start
        self._remote_start = remote_start
        self._offset_initialised = True

    @property
    def offset_local(self) -> int:
        """
        How many strides to get to the start at the local side of the anchor.

        Ideally, this would be within the local TimeSpan, but that is not enforced
        """
        return self.normalise_index(int((self.local_start - self.start)//self.timestep))

    @overload
    def normalise_index(self, index:int) -> int:
        ...

    @overload
    def normalise_index(self, index:npt.ArrayLike[np.int64]) -> npt.ArrayLike[np.int64]:
        ...

    def normalise_index(self, index):
        """
        Get the retrievable index from the (wrapped) local timespan.

        NB - the timespan is assumed wrapped with overlapping end and start, so the end index is never realised.
        e.g. if the timespan covers 1 year from 2020-01-01T00:00:00 to 2021-01-01T00:00:00, then the index for the latter date will never be returned
        """
        return index % self.n_interval

    def get_local_index(self, remote_timespan:TimeSpan) -> npt.NDArray[np.int64]:
        """
        A vector of indices for the local timeseries corresponding to the remote timespan
        """
        delta = remote_timespan.delta
        n_interval = delta // self.timestep

        # How far to move from our reference offset to reach the requested timespan start
        start_off = int((remote_timespan.start - self.remote_start) // self.timestep)
        i0 = self.offset_local + start_off
        i1 = i0 + n_interval + 1
        return self.normalise_index(np.arange(i0, i1))

    def _post_calc(self):
        super()._post_calc()
        if not self._offset_initialised:
            if hasattr(self, "_start_dt"):
                self._local_start = self._start_dt
                self._remote_start = self._start_dt

def delta_days(datetimes:pd.Series) -> pd.Series:
    """
    Return indicator for day changes in timeseries

    Useful for calculating standing charges, this looks for changes in year day
    between adjacent series entries and indicates "1" if at least one midnight
    has passed. The last entry is always set to 0 to prevent standing charges
    on zero-length intervals
    """
    yearday = datetimes.dt.day_of_year
    delta_day = 1 * np.logical_not(yearday - yearday.shift(1, fill_value=yearday.iloc[0]-1)==0)
    delta_day.iloc[-1] = 0
    return delta_day

def year_index(datetimes:pd.Series) -> npt.NDArray[np.int32]:
    """
    Return array integers indicating which year datetime belongs to in series

    A year is determined to have passed if the numeric year has increased and the day of year 
    is >= the first day of the series. This implies that the calendar date of increment may vary 
    depending on whether the present year is a leap year
    """
    yearday = datetimes.dt.day_of_year
    year = datetimes.dt.year
    startday = yearday.iloc[0]
    startyear = year.iloc[0]
    return ((year - startyear - 1) + 1 *((yearday - startday) >=0)).to_numpy(dtype=np.int32)

def season_index(datetimes:pd.Series) -> npt.NDArray[np.int32]:
    """
    Return array integers indicating which season (0-3) datetime belongs to in series

    Seasons are:
    0 = Winter = Dec, Jan, Feb
    1 = Spring = Mar, Apr, May
    2 = Summer = Jun, Jul, Aug
    3 = Autumn = Sep, Oct, Nov
    """
    monthn = datetimes.dt.month
    return np.where(
        monthn >= 12,
        0,
        np.where(
            monthn >= 9,
            3,
            np.where(
                monthn >= 6,
                2,
                np.where(
                    monthn >= 3,
                    1,
                    0
                )
            )
        )
    )
