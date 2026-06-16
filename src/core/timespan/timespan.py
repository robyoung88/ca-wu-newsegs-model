"""
Ways of defining and comparing blocks of time.
"""
# Avoid problem of TimeSpan __init__ annotation referencing TimeSpan before it is in namespace
from __future__ import annotations

import copy
from typing import Mapping

from functools import singledispatchmethod
import operator
from typing import TypeAlias, overload, override
import numpy as np
import pandas as pd
import datetime
from datetime import timedelta, tzinfo
import zoneinfo
import pytz
import dateutil
from pandas.core.tools.datetimes import DatetimeScalar
import numpy.typing as npt

from util import classfuncs
from core import serialisation

SECONDS_IN_DAY = (24 * 3600)

SECONDS_TO_HOURS = 1.0 / 3600.0
SECONDS_TO_DAYS = 1.0 / SECONDS_IN_DAY
NANOSECONDS_TO_DAYS = SECONDS_TO_DAYS / 1e9

SEASON_NAMES = [
    'Year',
    'Wtr',
    'Spr',
    'Smr',
    'Aut'
]

PEAK_PERIODS = [
    {'start': datetime.time(17,00),
     'end': datetime.time(20,00),
     'bst': True,
     'index': 1}
]

TimedeltaScalar: TypeAlias = timedelta|np.timedelta64|str|int|float
TimeZoneScalar: TypeAlias = str|tzinfo

def timestamp_to_dict(ts: pd.Timestamp) -> Mapping:
    return {
        'ts_input' : str(ts),
        'tz': str(ts.tz)
    }

def timestamp_from_dict(ts_dict: Mapping) -> pd.Timestamp:
    return pd.Timestamp(**ts_dict)

def timedelta_to_dict(td: pd.Timedelta) -> Mapping:
    return{
        'value': str(td)
    }

def timedelta_from_dict(td_dict: Mapping) -> pd.Timedelta:
    return pd.Timedelta(**td_dict)

class TimeSpan(serialisation.SerialiseToDictMixin):
    _tz = 'utc'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'TimeSpan'

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
        o = copy.copy(self)
        o.end = o.end + pd.Timedelta(time_delta)
        return o
    
    def __sub__(self, time_delta:TimedeltaScalar):
        o = copy.copy(self)
        o.end = o.end - pd.Timedelta(time_delta)
        return o

    def __mul__(self, times:int|float):
        o = copy.copy(self)
        o.end = o.start + o.delta * times
        return o
    
    def __truediv__(self, denom:int|float):
        o = copy.copy(self)
        o.end = o.start + o.delta / denom
        return o

    def __str__(self):
        return str(self.start) + " - " + str(self.end)

    def __repr__(self):
        return (
            "" + classfuncs.get_class(self)
            +  "(" + repr(self.start) + ", " 
            + repr(self.end) + ")"
        )
    
    def to_dict(self) -> Mapping:
        odict = {
            'class': classfuncs.get_class(self),
            'start': timestamp_to_dict(self._start_dt),
            'end': timestamp_to_dict(self._end_dt)
        }
        if hasattr(self, '_tz'):
            odict['tz'] = str(self._tz)
        return odict
    
    @classmethod
    def from_dict(cls, ip: Mapping) -> TimeSpan:
        ip = copy.copy(ip)

        ip['start'] = timestamp_from_dict(ip.get('start'))
        ip['end'] = timestamp_from_dict(ip.get('end'))

        # To allow for the self-dispatch magic, need to
        # set start as a positional arg
        posargs = (ip.pop('start'),)

        if ('class' in ip.keys()):
            ip.pop('class')
        
        return cls(*posargs, **ip)

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
    _default_timestep = pd.Timedelta(1, 'h')

    @singledispatchmethod
    def __init__(
        self, 
        start: TimeSpan | DatetimeScalar,
        end: DatetimeScalar | None = None,
        tz: TimeZoneScalar|None = None,
        timestep: TimedeltaScalar|None = None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('`start` must be an identifiable date, is %s', start)

    @override
    @__init__.register(DatetimeScalar)
    def _from_dates(self, 
        start: DatetimeScalar,
        end: DatetimeScalar, 
        tz: TimeZoneScalar|None = None,
        timestep: TimedeltaScalar|None = None
    ):
        super().__init__(start, end, tz)
        if timestep is not None:
            self.timestep = timestep
        else:
            self.timestep = copy.copy(self._default_timestep)
        
    @override
    @classmethod
    def from_none(cls):
        o = super(RegTimeSpan, cls).from_none()
        o.set_timestep(1, "h")
        return o
            
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
    def from_dates(
        cls,
        start_datetime: DatetimeScalar,
        end_datetime: DatetimeScalar,
        timestep:TimedeltaScalar,
        tz:TimeZoneScalar|None='utc',
        unit=None
    ):
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
    
    def __eq__(self, other: TimeSpan|RegTimeSpan) -> bool:
        """
        Do start, end and timestep of time spans match?

        Reduces to start and end if other is a TimeSpan, for symmetry.
        """
        if not isinstance(other, TimeSpan):
            raise ValueError('Other must be a TimeSpan instance, is %s', type(other))
        
        ok = super().__eq__(other)

        if isinstance(other, RegTimeSpan):
            ok = ok and (self.timestep == other.timestep)
        
        return ok

    def __ne__(self, other: TimeSpan|RegTimeSpan) -> bool:
        """
        Do not start, end and timestep of time spans match?
        """
        return not(self == other)

    def __str__(self):
        return (
            str(self.start) 
            + " - " + str(self.end) 
            + ", timestep: " + str(self.timestep)
        )

    def __repr__(self):
        return (
            "" + classfuncs.get_class(self) 
            + "(" + repr(self.start) + ", "
            + repr(self.end) 
            + " timestep = " + repr(self.timestep) + ")"
        )
    
    def to_dict(self) -> Mapping:
        odict = super().to_dict()
        odict['timestep'] = timedelta_to_dict(self._timestep)
        return odict
    
    @classmethod
    def from_dict(cls, ip: Mapping) -> RegTimeSpan:
        ip = copy.copy(ip)

        ip['timestep'] = timedelta_from_dict(ip.get('timestep'))
        return super(RegTimeSpan, cls).from_dict(ip)

# RegTimeSpan copy constructor
@RegTimeSpan.__init__.register(TimeSpan)
def RegTimeSpan_from_other(self, start: TimeSpan, end: None = None):
    super(RegTimeSpan, self).__init__(start)
    if isinstance(start, RegTimeSpan):
        self._timestep = start.timestep

setattr(RegTimeSpan, '_from_other', RegTimeSpan_from_other)

class OffsetRegTimeSpan(RegTimeSpan):
    """
    A regular timespan offset from another timespan by a number of timesteps.

    The purpose of this class is to allow a small timeseries to be repeated 
    (with offset) to represent a longer timeseries which may start at a 
    different time.
    """

    _offset_initialised = False

    # Setting the offset is all done post-intialisation apart from in copy
    # so no need to override __init__
    # However, need to make sure is caught by singledispatchmethod
    # otherwise copy constructor will replace parent class'
    # and as a result of this, will need to reattach all the methods
    # which is done after the fact
    @singledispatchmethod
    def __init__(
        self, 
        start: TimeSpan | DatetimeScalar,
        end: DatetimeScalar | None = None,
        tz: TimeZoneScalar|None = None,
        timestep: TimedeltaScalar|None = None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('`start` must be an identifiable date, is %s', start)
    
    # There may be a smarter way of doing this. I do not know it.
    @override
    @__init__.register(DatetimeScalar)
    def _from_dates(self, 
        start: DatetimeScalar,
        end: DatetimeScalar, 
        tz: TimeZoneScalar|None = None,
        timestep: TimedeltaScalar|None = None
    ):
        super().__init__(start, end, tz, timestep)
        self.wrap_right = True # Default to keeping the last element and dropping the first, useful for retrospective meter readings.
    
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

        NB - the timespan is assumed wrapped with overlapping end and start, so the either the start index or the end index is never realised.
        By default, this is the start index.
        e.g. if the timespan covers 1 year from 2020-01-01T00:00:00 to 2021-01-01T00:00:00, then the index for the latter date will never be returned
        """
        if self.wrap_right:
            if isinstance(index, int) and index == 0:
                # Even on a wrap_right, if starting at the start of the local ts, return that index
                return index
            
            idx = index % self.n_interval
            if isinstance(idx, int):
                if idx==0:
                    # We have wrapped at least once, so must return the last index
                    return self.n_interval
                return idx
            else:
                # Only return the last index if we have wrapped
                idx[np.logical_and(idx==0, index != 0)] = self.n_interval
                return idx
        else:
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

    def __eq__(self, other: TimeSpan) -> bool:
        """
        Do start, end and timestep of time spans match?

        Reduces to start and end if other is a TimeSpan, for symmetry.
        """
        if not isinstance(other, TimeSpan):
            raise ValueError('Other must be a TimeSpan instance, is ', type(other))
        
        ok = super().__eq__(other)

        if isinstance(other, OffsetRegTimeSpan):
            if self._offset_initialised:
                ok = (
                    ok 
                    and (self._local_start == other._local_start) 
                    and (self._remote_start == other._remote_start)
                )
        
        return ok

    def __ne__(self, other: TimeSpan) -> bool:
        """
        Do not time spans match?
        """
        return not(self == other)

    def __str__(self):
        root_str = super().__str__()
        if (self._offset_initialised):
            return (
                root_str 
                + ', offset: ' 
                + str(self._local_start), " local to " 
                + str(self._remote_start), " remote"
            )
        else:
            return (
                root_str
                + ', offset not initialised'
            )

    def __repr__(self):
        root_str = (
            "" + classfuncs.get_class(self) 
            + "(" + repr(self.start) + ", "
            + repr(self.end) 
            + " timestep = " + repr(self.timestep)
        )
        if self._offset_initialised:
            return (
                root_str
                + ", local_start = " + repr(self._local_start) 
                + ", remote_start = " + repr(self._remote_start)
                + ")"
            )
        return root_str + ")"

    def to_dict(self) -> Mapping:
        odict = super().to_dict()
        if self._offset_initialised:
            odict['local_start'] = timestamp_to_dict(self._local_start)
            odict['remote_start'] = timestamp_to_dict(self._remote_start)
        return odict
    
    @classmethod
    def from_dict(cls, ip: Mapping) -> OffsetRegTimeSpan:
        ip = copy.copy(ip)

        local_start = ip.pop('local_start', None)
        remote_start = ip.pop('remote_start', None)
        o = super(OffsetRegTimeSpan, cls).from_dict(ip)

        if local_start is not None:
            o.set_offset(
                timestamp_from_dict(local_start),
                timestamp_from_dict(remote_start)
            )
        return o

# OffsetRegTimeSpan copy constructor
@OffsetRegTimeSpan.__init__.register(TimeSpan)
def OffsetRegTimeSpan_from_other(self, start: TimeSpan, end: None = None):
    super(OffsetRegTimeSpan, self).__init__(start)
    if isinstance(start, OffsetRegTimeSpan):
        self._offset_initialised = start.offset_initialised
        self._local_start = start.local_start
        self._remote_start = start.remote_start

_TIMESPAN_CONSTRUCTORS = {
    'TimeSpan': TimeSpan,
    'RegTimeSpan': RegTimeSpan,
    'OffsetRegTimeSpan': OffsetRegTimeSpan
}

def timespan_from_dict(ip: Mapping):
    """
    Returns an instance of the correct timespan from a dictionary.
    """
    ip = copy.copy(ip)
    classname = ip.pop('class')
    constructor = _TIMESPAN_CONSTRUCTORS.get(classname)
    if constructor is None:
        raise ValueError('No timespan class found for ', classname)
    return constructor.from_dict(ip)

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
    Return array integers indicating which season (1-4) datetime belongs to in series

    Seasons are:
    0 = Year = Jan - Dec; used for summaries
    1 = Winter = Dec, Jan, Feb
    2 = Spring = Mar, Apr, May
    3 = Summer = Jun, Jul, Aug
    4 = Autumn = Sep, Oct, Nov
    """
    monthn = datetimes.dt.month
    return np.where(
        monthn >= 12,
        1,
        np.where(
            monthn >= 9,
            4,
            np.where(
                monthn >= 6,
                3,
                np.where(
                    monthn >= 3,
                    2,
                    1
                )
            )
        )
    )

def month_index(
    datetimes: pd.Series|pd.DatetimeIndex,
    ref_datetime: pd.Timestamp|None = None
) -> npt.NDArray[np.int32]:
    """
    An array of integers indicating sequential month datetime belongs to in series

    A month is determined to have passed if the month or year number has
    increased and the day is greater than or equal to the reference. If the
    reference is > 28, then the month will change at the last day of the month
    if the month day is not achievable.

    Not timezone safe.
    """
    if isinstance(datetimes, pd.DatetimeIndex):
        datetimes = pd.Series(datetimes)
    
    if ref_datetime is None:
        ref_datetime = datetimes.iloc[0]

    ref_day = ref_datetime.day
    ref_month = ref_datetime.month
    ref_year = ref_datetime.year

    return (
        (
            (datetimes.dt.year - ref_year) * 12 +
            (datetimes.dt.month - ref_month) +
            -1 * (
                (datetimes.dt.daysinmonth >= ref_day) * (datetimes.dt.day < ref_day) +
                (datetimes.dt.daysinmonth < ref_day) * (np.logical_not(datetimes.dt.is_month_end))
            )
        )
        .to_numpy(dtype = np.int32)
    )

def day_index(datetimes:pd.Series,
              ref_datetime: pd.Timestamp|None = None) -> npt.NDArray[np.int32]:
    """
    Return array integers indicating which day datetime belongs to in series

    A day is determined to have passed if 24 hours have passed
    """
    if ref_datetime is None:
        ref_datetime = datetimes.iloc[0]
    
    deltas = (
        (datetimes - ref_datetime)
        .dt.total_seconds()
        .to_numpy(dtype=np.int32)
    )
    return deltas // SECONDS_IN_DAY

def peaktime_index(datetimes,
                   peak_periods = PEAK_PERIODS):
    """
    Return integer array of peak period indicators
    """
    retval = np.zeros(len(datetimes), dtype=np.int32)
    for prd in peak_periods:
        if prd.get('bst'):
            tms = datetimes.tz_convert(pytz.timezone('Europe/London')).time
            is_interval = np.logical_and(
                tms > prd.get('start'),
                tms <= prd.get('end')
            )
            retval[is_interval] = prd.get('index')
    return retval
    