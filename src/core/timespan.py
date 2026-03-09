# Avoid problem of TimeSpan __init__ annotation referencing TimeSpan before it is in namespace
from __future__ import annotations

from copy import copy
import operator
from typing import TypeAlias
import numpy as np
import pandas as pd
from datetime import timedelta, tzinfo
import zoneinfo
import pytz
import dateutil
from pandas.core.tools.datetimes import DatetimeScalar, Timedelta

# -----------------------------------------------------------------------------
# Ways of defining and comparing blocks of time

TimedeltaScalar: TypeAlias = Timedelta|timedelta|np.timedelta64|str|int|float
TimeZoneScalar: TypeAlias = str|tzinfo

class TimeSpan:
    def __init__(self, other:TimeSpan|None=None) -> None:
        """
            Initialise a TimeSpan using another TimeSpan
        """
        if not(other is None):
            if not (isinstance(other, TimeSpan)):
                raise ValueError("timespan " + str(other) + " is not a TimeSpan instance")
            
            self._start_dt = other.start
            self._end_dt = other.end
            self._tz = other.tz
            self._post_calc()
        
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
            self.set_start(start_datetime, self.__tz)
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
        return self._tz

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
    
    def __add__(self:T, time_delta:TimedeltaScalar):
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

class RegTimeSpan(TimeSpan):
    """
    A TimeSpan which strides between its start and end in equally-spaced TimeDeltas
    """

    def __init__(self, other:TimeSpan|None) -> None:
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
            self._timestep = pd.Timedelta(timestep, unit = "h")
        self._post_calc()

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
        return self.to_pandas()[-1]

    def to_pandas(self):
        return pd.date_range(self.start,self.end,freq=self.timestep)
    