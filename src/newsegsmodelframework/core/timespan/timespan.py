"""
Ways of defining and comparing blocks of time.
"""
# Avoid problem of TimeSpan __init__ annotation referencing TimeSpan before it is in namespace
from __future__ import annotations

import copy
import datetime
from datetime import timedelta, tzinfo
from functools import singledispatchmethod
from typing import Any, Type, TypeVar, TypeAlias, overload, override

import numpy as np
import numpy.typing as npt
import pandas as pd
from pandas.core.tools.datetimes import DatetimeScalar
import pytz

from newsegsmodelframework.core.serialisation import StateSerialiseToDictMixin
from newsegsmodelframework.util import classfuncs

SECONDS_IN_DAY = (24 * 3600)
"""int - number of seconds in 24 hours"""

SECONDS_TO_HOURS = 1.0 / 3600.0
"""float - ``hrs = secs * SECONDS_TO_HOURS``"""
SECONDS_TO_DAYS = 1.0 / SECONDS_IN_DAY
"""float - Assumes 24 hour day - ``days = secs * SECONDS_TO_DAYS``"""
NANOSECONDS_TO_DAYS = SECONDS_TO_DAYS / 1e9
"""float - Assumes 24 hour day - ``days = ns * NANOSECONDS_TO_DAYS``"""

SEASON_NAMES = [
    'Year',
    'Wtr',
    'Spr',
    'Smr',
    'Aut'
]
"""list[str] - Short labels for tables. Includes 'Year' at index 0.

Value: ['Year', 'Wtr', 'Spr', 'Smr', 'Aut']
"""

PEAK_PERIODS = [
    {'start': datetime.time(17,00),
     'end': datetime.time(20,00),
     'bst': True,
     'index': 1}
]
"""list[dict[str, datetime.time | bool | int]] - List of time intervals considered "peak" for aggregation.

Each element includes the following key-value pairs:
    - 'start' : datetime.time - Start of interval
    - 'end' : datetime.time - End of interval
    - 'bst' : bool - Keep the interval aligned with BST (not UTC)
    - 'index' : int - Cardinality of the period. Starts at 1.
"""

TimedeltaScalar: TypeAlias = timedelta|np.timedelta64|str|int|float
"""TypeAlias - representation of a difference in (date)time."""
TimeZoneScalar: TypeAlias = str|tzinfo
"""TypeAlias - representation of a timezone"""

TIndex = TypeVar("TIndex", bound=npt.NDArray[np.integer])
TTimeSpan = TypeVar("TTimeSpan", bound="TimeSpan")

class TimeSpan(StateSerialiseToDictMixin):
    """Represents a range of time between a start and an end datetime.

    This class wraps datetime handling and timezone rationalization for a
    continuous time span. It supports construction from date-like scalars,
    normalization of timezone-aware timestamps, and cached timedelta
    computation for the span.

    Attributes:
        _tz (str|tzinfo): The timezone used for the time span.
    """

    _tz = 'utc'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'TimeSpan'
    _delta: pd.Timedelta

    @singledispatchmethod
    def __init__(
        self, 
        start: TimeSpan | DatetimeScalar,
        end: DatetimeScalar | None = None,
        tz: TimeZoneScalar|None = None
    ) -> None:
        """Initialize a TimeSpan instance.

        This method uses singledispatch and so requires an unnamed first
        argument which is not `None`. Concrete overloads are:

        - __init__(self, start: DatetimeScalar, end: DatetimeScalar, tz: TimeZoneScalar|None = None)
            Construct from explicit start and end date-like values.

        - __init__(self, start: TimeSpan)
            Construct as a copy from an existing TimeSpan instance.

        The generic implementation raises a ValueError when an unsupported
        `start` type is provided.

        For initiation without first argument, use `TimeSpan.from_none()`

        Args:
                start: The primary constructor argument; type-dispatched by the
                        singledispatchmethod registration to resolve the concrete
                        initializer to use.
                end: Optional end datetime (used by the DatetimeScalar overload).
                tz: Optional timezone to apply to the span.

        Raises:
                ValueError: If `start` is not an identifiable date-like value or
                        a TimeSpan for the copy constructor.
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
    def from_none(cls: type[TTimeSpan]) -> TTimeSpan:
        """Create a default TimeSpan instance.

        Returns:
            TimeSpan: A new TimeSpan spanning from 2002-01-01T00:00:00 to
                2015-01-01T00:00:00.
        """
        return cls("2002-01-01T00:00:00", "2015-01-01T00:00:00")

    def _post_calc(self):
        """Perform derived calculations after key datetime properties change."""
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
    def rationalise_datetime(this_datetime:DatetimeScalar, tz:TimeZoneScalar|None=None) -> pd.Timestamp:
        """Return a timezone-rationalized pandas Timestamp.

        Args:
            this_datetime (DatetimeScalar): Input timestamp-like value.
            tz (TimeZoneScalar|None): Optional timezone to apply.

        Returns:
            pd.Timestamp: A timezone-aware timestamp.
        """
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
        """pd.Timestamp: Start datetime of the time span."""
        return self._start_dt

    @start.setter
    def start(self, start_datetime: DatetimeScalar):
        if hasattr(start_datetime, 'tz'):
            self.set_start(start_datetime)
        elif hasattr(self, '_tz'):
            self.set_start(start_datetime, self._tz)
        else:
            self.set_start(start_datetime)

    def set_start(
        self, 
        start_datetime: DatetimeScalar, 
        tz: TimeZoneScalar|None =None
    ):
        """Set the start datetime for the time span.

        Args:
            start_datetime (DatetimeScalar): The new start datetime.
            tz (TimeZoneScalar|None): Optional timezone to apply.
        """
        self._start_dt = TimeSpan.rationalise_datetime(start_datetime, tz)
        self._tz = self._start_dt.tz
        self._post_calc()

    @property
    def end(self):
        """pd.Timestamp: End datetime of the time span."""
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
        """Set the end datetime for the time span.

        Args:
            end_datetime (DatetimeScalar): The new end datetime.
            tz (TimeZoneScalar|None): Optional timezone to apply.
        """
        self._end_dt = TimeSpan.rationalise_datetime(end_datetime, tz)
        self._post_calc()

    @property
    def tz(self):
        """str|tzinfo|None: Timezone of the time span."""
        if hasattr(self, "_tz"):
            return self._tz
        else:
            return None

    @tz.setter
    def tz(self, tz:TimeZoneScalar|None):
        """Set the timezone for the current time span.

        Args:
            tz (TimeZoneScalar|None): Timezone to apply to start and end.
        """
        if hasattr(self, '_start_dt'):
            self._start_dt = TimeSpan.rationalise_datetime(self._start_dt, tz)
        if hasattr(self, '_end_dt'):
            self._end_dt = TimeSpan.rationalise_datetime(self._end_dt, tz)
        #self._tz = self._start_dt.tz
        self._post_calc()

    @property
    def delta(self) -> pd.Timedelta:
        """pd.Timedelta: Time duration between start and end."""
        if hasattr(self, '_delta'):
            return self._delta
        raise AttributeError('TimeSpan has not been set')

    def set_delta(self, time_delta:TimedeltaScalar):
        """Advance the end timestamp by a timedelta.

        Args:
            time_delta (TimedeltaScalar): Amount to add to the current span.
        """
        if isinstance(time_delta, pd.Timedelta):
            self.end = self.start + pd.Timedelta(time_delta)
        else:
            self.end = self.start + pd.Timedelta(time_delta, unit='h')

    @classmethod
    def from_dates(cls: type[TTimeSpan], start_datetime: DatetimeScalar, end_datetime: DatetimeScalar, tz:TimeZoneScalar|None='utc') -> TTimeSpan:
        """Create a TimeSpan from explicit start and end dates.

        Args:
            start_datetime (DatetimeScalar): Start of the span.
            end_datetime (DatetimeScalar): End of the span.
            tz (TimeZoneScalar|None): Optional timezone to apply.

        Returns:
            TimeSpan: New TimeSpan instance.
        """
        o = cls()
        o.start = start_datetime
        o.end = end_datetime
        if not (tz is None):
            o.tz = tz
        return o
    
    @classmethod
    def from_date_delta(
        cls: type[TTimeSpan],
        start_datetime: DatetimeScalar,
        time_delta: TimedeltaScalar,
        tz: TimeZoneScalar | None = 'utc'
    ) -> TTimeSpan:
        """Create a TimeSpan from a start date and duration.

        Args:
            start_datetime (DatetimeScalar): Start of the span.
            time_delta (TimedeltaScalar): Duration to add to the start.
            tz (TimeZoneScalar|None): Optional timezone to apply.

        Returns:
            TimeSpan: New TimeSpan instance.
        """
        o = cls()
        o.start = start_datetime
        if type(time_delta in ('str','int','float')):
            o.end = o.start + pd.Timedelta(time_delta, unit='h')
        else:
            o.end = o.start + pd.Timedelta(time_delta)
        if not (tz is None):
            o.tz = tz
        
        return o

    @classmethod
    def from_timespan(cls: type[TTimeSpan], timespan: TimeSpan) -> TTimeSpan:
        """Create a copy of an existing TimeSpan.

        Args:
            timespan (TimeSpan): Existing TimeSpan instance.

        Returns:
            TimeSpan: Copied TimeSpan instance.
        """
        return cls(timespan)

    @classmethod
    @override
    def from_dict(cls: type[TTimeSpan], config: dict[str, Any]) -> TTimeSpan:
        """Create a TimeSpan from a serialized dictionary.

        Overrides [SerialiseToDictMixin.from_dict][newsegsmodelframework.core.serialisation.SerialiseToDictMixin.from_dict]

        Args:
            config (dict[str, Any]): Serialized TimeSpan configuration.

        Returns:
            TimeSpan: New TimeSpan instance.
        """
        inst = super(TimeSpan, cls).from_dict(config)
        if hasattr(inst, '_tz') and isinstance(inst._tz, str):
            inst._tz = pytz.timezone(inst._tz) 
        return inst

    def __lt__(self, other: TimeSpan) -> bool:
        """Does this time span start before other?"""
        return (self.start < other.start)
    
    def __le__(self, other: TimeSpan) -> bool:
        """Does this time span start at or before other?"""
        return (self.start <= other.start)

    def __eq__(self, other) -> bool:
        """Do both start and end of time spans match?"""
        if not isinstance(other, TimeSpan):
            raise TypeError(f'Comparison not implemented for type {type(self)} against {type(other)}')
        return (self.start == other.start) and (self.end == other.end)

    def __ne__(self, other) -> bool:
        """Do not both start and end of time spans match?"""
        if not isinstance(other, TimeSpan):
            raise TypeError(f'Comparison not implemented for type {type(self)} against {type(other)}')
        return (self.start != other.start) or (self.end != other.end)

    def __ge__(self, other: TimeSpan) -> bool:
        """Does this time span end at or after other?"""
        return (self.end >= other.end)

    def __gt__(self, other: TimeSpan) -> bool:
        """Does this time span end after other?"""
        return (self.end > other.end)
    
    def __add__(self, time_delta: TimedeltaScalar):
        """Return a new TimeSpan with the end shifted forward.

        Args:
            time_delta (TimedeltaScalar): Amount to add to the span end.

        Returns:
            TimeSpan: New TimeSpan instance with adjusted end.
        """
        o = copy.copy(self)
        o.end = o.end + pd.Timedelta(time_delta)
        return o
    
    def __sub__(self, time_delta: TimedeltaScalar):
        """Return a new TimeSpan with the end shifted backward.

        Args:
            time_delta (TimedeltaScalar): Amount to subtract from the span end.

        Returns:
            TimeSpan: New TimeSpan instance with adjusted end.
        """
        o = copy.copy(self)
        o.end = o.end - pd.Timedelta(time_delta)
        return o

    def __mul__(self, times: int|float):
        """Return a new TimeSpan scaled by a multiplier.

        Args:
            times (int|float): Multiplier for the span duration.

        Returns:
            TimeSpan: New TimeSpan with scaled duration.
        """
        o = copy.copy(self)
        o.end = o.start + o.delta * times
        return o
    
    def __truediv__(self, denom: int|float):
        """Return a new TimeSpan with duration divided by a scalar.

        Args:
            denom (int|float): Divisor for the span duration.

        Returns:
            TimeSpan: New TimeSpan with shortened duration.
        """
        o = copy.copy(self)
        o.end = o.start + o.delta / denom
        return o

    def __str__(self):
        # Return a human-readable string for the time span.
        return str(self.start) + " - " + str(self.end)

    def __repr__(self):
        # Return a machine-readable representation of the time span.
        return (
            "" + classfuncs.get_class(self)
            +  "(" + repr(self.start) + ", " 
            + repr(self.end) + ")"
        )
    
# TimeSpan copy constructor
@TimeSpan.__init__.register(TimeSpan) # pyright: ignore[reportFunctionMemberAccess]
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
    """A TimeSpan which strides between its start and end in equally-spaced TimeDeltas.

    Extends [TimeSpan][newsegsmodelframework.core.timespan.TimeSpan] with a regular timestep within the span.
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
        """Initialize a RegTimeSpan instance.

        This method uses singledispatch and so requires an unnamed first
        argument which is not `None`. The concrete overloads are:

        - __init__(self, start: DatetimeScalar, end: DatetimeScalar,
            tz: TimeZoneScalar|None = None,
            timestep: TimedeltaScalar|None = None)

        - __init__(self, start: TimeSpan)

        For initiation without first argument, use `RegTimeSpan.from_none()`.

        Args:
            start: The primary constructor argument; type-dispatched by the
                singledispatchmethod registration.
            end: Optional end datetime for the DatetimeScalar overload.
            tz: Optional timezone to apply to the span.
            timestep: Optional timestep between interval points.

        Raises:
            ValueError: If `start` is not an identifiable date-like value or a
                TimeSpan for the copy constructor.
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
        """Initialize from explicit start and end datetimes.

        Args:
            start: Start of the span.
            end: End of the span.
            tz: Optional timezone to apply.
            timestep: Optional timestep between interval points.
        """
        super().__init__(start, end, tz)
        if timestep is not None:
            self.timestep = timestep
        else:
            self.timestep = copy.copy(self._default_timestep)
        
    @override
    @classmethod
    def from_none(cls):
        """Create a default RegTimeSpan instance.

        Returns:
            RegTimeSpan: New instance with a default hourly timestep.
        """
        o = super(RegTimeSpan, cls).from_none()
        o.set_timestep(1, "h")
        return o
            
    def _post_calc(self):
        """Perform derived calculations after key datetime properties change.

        Updates the cached interval count when both `delta` and `timestep`
        are available.
        """
        super()._post_calc()
        if hasattr(self, "_timestep"):
            if hasattr(self, "_delta"):
                self._n = self.delta // self.timestep

    @property
    def timestep(self) -> pd.Timedelta:
        """pd.Timedelta: The regular timestep between interval points."""
        return self._timestep
    
    @timestep.setter
    def timestep(self, timestep:TimedeltaScalar) -> None:
        self.set_timestep(timestep)
    
    def set_timestep(self, timestep:TimedeltaScalar, unit=None) -> None:
        """Set the timestep for the regular timespan.

        Args:
            timestep: New timestep value.
            unit: Optional unit to apply when `timestep` is a scalar.
        """
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
    def from_dates( # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        start_datetime: DatetimeScalar,
        end_datetime: DatetimeScalar,
        timestep: TimedeltaScalar,
        tz: TimeZoneScalar | None='utc',
        unit=None
    ):
        """Create a RegTimeSpan from explicit start, end, and timestep values.

        Args:
            start_datetime (DatetimeScalar): Start of the span.
            end_datetime (DatetimeScalar): End of the span.
            timestep (TimedeltaScalar): Regular timestep for the span.
            tz (TimeZoneScalar | None): Optional timezone to apply.
            unit: Optional unit to apply when ``timestep`` is a scalar.

        Returns:
            RegTimeSpan: New regular timespan instance.
        """
        o = super(RegTimeSpan, cls).from_dates(start_datetime,end_datetime,tz)
        o.set_timestep(timestep, unit)
        return o

    @property
    def n_interval(self) -> int:
        """Number of full timesteps contained in the span.

        Returns:
            int: Number of full timesteps.
        """
        return self._n

    @property
    def n_node(self) -> int:
        """Number of nodes in the span, including the start and end points.

        Returns:
            int: Number of nodes in the span.
        """
        return self._n + 1

    @property
    def end_timeseries(self) -> pd.Timestamp:
        """The actual final timestamp for the time series.

        Returns:
            pd.Timestamp: The final timestamp for the series.
        """
        return self.start + self.n_interval * self.timestep

    def to_pandas(self) -> pd.DatetimeIndex:
        """Return a pandas DatetimeIndex for the regular interval span.

        Returns:
            pd.DatetimeIndex: DatetimeIndex for the timespan.
        """
        return pd.date_range(self.start,self.end,freq=self.timestep)
    
    def __eq__(self, other: TimeSpan|RegTimeSpan) -> bool:
        """Return True if start, end, and timestep match another time span.

        Args:
            other (TimeSpan | RegTimeSpan): Time span to compare.

        Returns:
            bool: True if the spans are equal.
        """
        if not isinstance(other, TimeSpan):
            raise ValueError('Other must be a TimeSpan instance, is %s', type(other))
        
        ok = super().__eq__(other)

        if isinstance(other, RegTimeSpan):
            ok = ok and (self.timestep == other.timestep)
        
        return ok

    def __ne__(self, other: TimeSpan|RegTimeSpan) -> bool:
        """Return True if the time spans are not equal.

        Args:
            other (TimeSpan | RegTimeSpan): Time span to compare.

        Returns:
            bool: True if the spans are not equal.
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

# RegTimeSpan copy constructor
@RegTimeSpan.__init__.register(TimeSpan) # pyright: ignore[reportFunctionMemberAccess]
def RegTimeSpan_from_other(self, start: TimeSpan, end: None = None):
    """Initialise a `RegTimeSpan` as a copy of another time span.

    The timestep is copied if the other is a `RegTimeSpan`.

    Args:
        start: The object to copy.
        end: Not used.
    """
    super(RegTimeSpan, self).__init__(start) # pyright: ignore[reportCallIssue]
    if isinstance(start, RegTimeSpan):
        self._timestep = start.timestep

setattr(RegTimeSpan, '_from_other', RegTimeSpan_from_other)

class OffsetRegTimeSpan(RegTimeSpan):
    """
    A RegTimeSpan offset from another TimeSpan by a number of timesteps.

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
        """Initialise an OffsetRegTimeSpan instance.
        
        This method uses singledispatch and so requires an unnamed first
        argument which is not `None`. Concrete overloads are:

        - __init__(self, start: DatetimeScalar, end: DatetimeScalar,
                    tz: TimeZoneScalar|None = None,
                    timestep: TimedeltaScalar|None = None)
            Construct from explicit start and end date-like values.

        - __init__(self, start: TimeSpan)
            Construct as a copy from an existing TimeSpan instance.

        The generic implementation raises a ValueError when an unsupported
        `start` type is provided.

        For initiation without first argument, use `OffsetRegTimeSpan.from_none()`

        Args:
            start: The primary constructor argument; type-dispatched by the
                    singledispatchmethod registration to resolve the concrete
                    initializer to use.
            end: Optional end datetime (used by the DatetimeScalar overload).
            tz: Optional timezone to apply to the span.
            timestep: Optional timestep between interval points.

        Raises:
            ValueError: If `start` is not an identifiable date-like value or
                    a TimeSpan for the copy constructor.
        """
        raise ValueError(f'`start` must be an identifiable date, is {start}')
    
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
    def offset_initialised(self) -> bool:
        """bool: Has an offset been specified for this instance?"""
        return self._offset_initialised    

    @property
    def local_start(self) -> pd.Timestamp:
        """pd.Timestamp: The reference timestamp of the local timespan"""
        return self._local_start
    
    @property
    def remote_start(self) -> pd.Timestamp:
        """pd.Timestamp: The reference timestamp of the remote timespan"""
        return self._remote_start

    def set_offset(
        self, 
        local_start:DatetimeScalar, 
        remote_start:DatetimeScalar
    ):
        """Set the local and remote anchor timestamps.

        Args:
            local_start: Local anchor timestamp.
            remote_start: Remote anchor timestamp.
        """
        if not(isinstance(local_start, pd.Timestamp)):
            local_start = pd.Timestamp(local_start, tz=self.tz)
        if not(isinstance(remote_start, pd.Timestamp)):
            remote_start = pd.Timestamp(remote_start, tz=self.tz)
        self._local_start = local_start
        self._remote_start = remote_start
        self._offset_initialised = True

    @property
    def offset_local(self) -> int:
        """Number of timesteps from this timespan start to the local anchor.

        Returns:
            int: Number of timesteps to the local anchor (normalized).
        """
        return self.normalise_index(int((self.local_start - self.start)//self.timestep))

    @overload
    def normalise_index(self, index:int) -> int:
        ...

    @overload
    def normalise_index(
        self, 
        index: TIndex
    ) -> TIndex:
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
        """Return indices in the local timeseries corresponding to a remote
        timespan.

        Args:
            remote_timespan: The remote TimeSpan to map from.

        Returns:
            numpy.ndarray: Integer indices into the local timeseries.
        """
        delta = remote_timespan.delta
        n_interval = delta // self.timestep

        # How far to move from our reference offset to reach the requested timespan start
        start_off = int((remote_timespan.start - self.remote_start) // self.timestep)
        i0 = self.offset_local + start_off
        i1 = i0 + n_interval + 1
        return self.normalise_index(np.arange(i0, i1))

    def _post_calc(self):
        """Post-construction calculations; ensure defaults for offsets."""
        super()._post_calc()
        if not self._offset_initialised and hasattr(self, "_start_dt"):
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

    def __str__(self) -> str:
        root_str = super().__str__()
        if (self._offset_initialised):
            return (
                root_str
                + ', offset: '
                + str(self._local_start) + " local to " 
                + str(self._remote_start) + " remote"
            )
        else:
            return (
                root_str
                + ', offset not initialised'
            )

    def __repr__(self) -> str:
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

# OffsetRegTimeSpan copy constructor
@OffsetRegTimeSpan.__init__.register(TimeSpan) # pyright: ignore[reportFunctionMemberAccess]
def OffsetRegTimeSpan_from_other(self, start: TimeSpan, end: None = None):
    """Initialise an `OffsetRegTimeSpan` as a copy of another time span.

    The offsets are copied if the other is an `OffsetRegTimeSpan`.

    Args:
        start: The object to copy.
        end: Not used.
    """
    super(OffsetRegTimeSpan, self).__init__(start) # pyright: ignore[reportCallIssue]
    if isinstance(start, OffsetRegTimeSpan):
        self._offset_initialised = start.offset_initialised
        self._local_start = start.local_start
        self._remote_start = start.remote_start

_TIMESPAN_CONSTRUCTORS = {
    'TimeSpan': TimeSpan,
    'RegTimeSpan': RegTimeSpan,
    'OffsetRegTimeSpan': OffsetRegTimeSpan
}

def timespan_from_dict(ip: dict) -> TimeSpan:
    """Return an instance of the correct timespan from a dictionary.

    Args:
        ip: Dictionary containing timespan data, including a 'class' key.

    Returns:
        TimeSpan: The reconstructed timespan instance.
    """
    ip = copy.copy(ip)
    classname = ip.pop('class')
    constructor = _TIMESPAN_CONSTRUCTORS.get(classname)
    if constructor is None:
        raise ValueError('No timespan class found for ', classname)
    return constructor.from_dict(ip)

def delta_days(datetimes: pd.Series) -> pd.Series:
    """Return indicator for day changes in timeseries.

    Useful for calculating standing charges, this looks for changes in year day
    between adjacent series entries and indicates "1" if at least one midnight
    has passed. The last entry is always set to 0 to prevent standing charges
    on zero-length intervals.

    Args:
        datetimes: Series of datetime values.

    Returns:
        pd.Series: Series of integer indicators for day changes.
    """
    yearday = datetimes.dt.day_of_year
    delta_day = (yearday != yearday.shift(1, fill_value=yearday.iloc[0] - 1)).astype(int)
    delta_day.iloc[-1] = 0
    return delta_day

def year_index(datetimes:pd.Series) -> npt.NDArray[np.int64]:
    """Return array integers indicating which year datetime belongs to in series.

    A year is determined to have passed if the numeric year has increased and the
    day of year is greater than or equal to the first day of the series. This
    implies that the calendar date of increment may vary depending on whether the
    present year is a leap year.

    Args:
        datetimes: Series of datetime values.

    Returns:
        npt.NDArray[np.int64]: Array of year indices.
    """
    yearday = datetimes.dt.day_of_year
    year = datetimes.dt.year
    startday = yearday.iloc[0]
    startyear = year.iloc[0]
    return np.array(
        ((year - startyear - 1) + 1 * ((yearday - startday) >= 0)),
        dtype=np.int64
    )

def season_index(datetimes:pd.Series) -> npt.NDArray[np.int32]:
    """Return array integers indicating which season (1-4) datetime belongs to in series.

    Seasons are:
        0 = Year = Jan - Dec; used for summaries
        1 = Winter = Dec, Jan, Feb
        2 = Spring = Mar, Apr, May
        3 = Summer = Jun, Jul, Aug
        4 = Autumn = Sep, Oct, Nov

    Args:
        datetimes: Series of datetime values.

    Returns:
        npt.NDArray[np.int32]: Array of season indices.
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
    datetimes: pd.Series | pd.DatetimeIndex,
    ref_datetime: pd.Timestamp | None = None
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
    
    assert isinstance(ref_datetime, pd.Timestamp)

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

def day_index(datetimes: pd.Series[pd.Timestamp],
              ref_datetime: pd.Timestamp | None = None) -> npt.NDArray[np.int64]:
    """
    Return array integers indicating which day datetime belongs to in series

    A day is determined to have passed if 24 hours have passed
    """
    if ref_datetime is None:
        ref_datetime = datetimes.iloc[0]

    assert isinstance(ref_datetime, pd.Timestamp)

    deltas = (
        (datetimes - ref_datetime)
        .dt.total_seconds()
        .to_numpy(dtype=np.int64)
    )
    return (deltas // SECONDS_IN_DAY).astype(np.int64)

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
    