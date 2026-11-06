"""
Module defining abstract base class for newsegs module results and helper functions.

NewsegsModuleResult encapsulates meter and DSM result arrays together with run metadata.
Helper utilities include pandas conversion and filtering by meter name/type.
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
import datetime
from typing import Sequence

import numpy as np
import pandas as pd

from newsegsmodelframework.core.timespan import RegTimeSpan

__all__ = [
    "NewsegsModuleResult",
    "defer_meters_to_pandas",
    "defer_dsm_to_pandas",
    "filter_meters",
    "filter_meter_indices",
]

class NewsegsModuleResult(metaclass = ABCMeta):
    """
    Abstract class holding module results
    
    Attributes:
        run_module_uuid: Unique identifier for the module run
        last_run: Timestamp of the last module execution
    
    Args:
        run_module_id: String identifier for the module run
        last_run: Datetime of when the module was last executed
    """
    run_module_uuid = 1
    last_run = datetime.datetime.now()
    
    def __init__(
        self,
        run_module_id: str,
        last_run: datetime.datetime,
    ):
        
        self.run_module_id = run_module_id
        self.last_run = last_run

    @property
    @abstractmethod
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """Array of the meter values (energy flows) of the run, with a row for each meter and a column for each timestep.
        """
        ...

    @property
    @abstractmethod
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """Array of the DSM (system state) values of the run, with a row for each value and a column for each timestep.
        """
        ...
        
    @abstractmethod
    def get_meter_names(self) -> Sequence[str]:
        """Names of the meters, in the order of the rows of `meters`.

        Returns:
            The names.
        """
        ...

    @abstractmethod
    def get_meter_types(self) -> Sequence[str]:
        """Types of the meters, in the order of the rows of `meters`.

        Returns:
            The types.
        """
        ...

    @abstractmethod
    def get_dsm_names(self) -> Sequence[str]:
        """Names of the DSM values, in the order of the rows of `dsm`.

        Returns:
            The names.
        """
        ...

    @abstractmethod
    def get_dsm_types(self) -> Sequence[str]:
        """Types of the DSM values, in the order of the rows of `dsm`.

        Returns:
            The types.
        """
        ...

    @abstractmethod
    def get_timespan(self) -> RegTimeSpan:
        """The time span of the run.

        Returns:
            The time span; the columns of `meters` and `dsm` are its timesteps.
        """
        ...

    def meters_to_pandas(self) -> pd.DataFrame:
        """
        Return the meter data as a pandas dataframe

        Caution - this implementation could become unweildy for large results

        Cached on the result, so freed with it.
        """
        return self._cached_frame('meters', defer_meters_to_pandas)
        
    def dsm_to_pandas(self) -> pd.DataFrame:
        """
        Return the dsm data as a pandas dataframe

        Caution - this implementation could become unweildy for large results

        Cached on the result, so freed with it.
        """
        return self._cached_frame('dsm', defer_dsm_to_pandas)

    def _cached_frame(self, name: str, convert) -> pd.DataFrame:
        # A module-level cache keyed on the result kept the results of every run alive
        cache = self.__dict__.setdefault('_frame_cache', {})
        if name not in cache:
            cache[name] = convert(self)
        return cache[name]

    def __getstate__(self) -> dict:
        # The dataframes are derived from the arrays, so are not saved with the result
        state = self.__dict__.copy()
        state.pop('_frame_cache', None)
        return state

    def __hash__(self):
        """The hash is dependent on the module uuid and run time."""
        return hash(
            (
                self.run_module_uuid, 
                self.last_run,
            )
        )

def defer_meters_to_pandas(res: NewsegsModuleResult) -> pd.DataFrame:
    """Convert the meters of a result to a dataframe, with a column for each meter indexed by time.

    Not cached: `NewsegsModuleResult.meters_to_pandas` caches it on the result.

    Args:
        res: The result.

    Returns:
        The dataframe; empty if there are no meters.
    """
    data = res.meters.T
    if len(data) == 0:
        return pd.DataFrame()
    
    datetime = res.get_timespan().to_pandas()
    return pd.DataFrame(
        data = data,
        index = datetime,
        columns = res.get_meter_names() # pyright: ignore[reportArgumentType]
    ) # type: ignore

def defer_dsm_to_pandas(res: NewsegsModuleResult) -> pd.DataFrame:
    """Convert the DSM values of a result to a dataframe, with a column for each value indexed by time.

    Not cached: `NewsegsModuleResult.dsm_to_pandas` caches it on the result.

    Args:
        res: The result.

    Returns:
        The dataframe; empty if there are no DSM values.
    """
    data = res.dsm.T
    if len(data) == 0:
        return pd.DataFrame()
    datetime = res.get_timespan().to_pandas()
    return pd.DataFrame(
        data = data,
        index = datetime,
        columns = res.get_dsm_names() # pyright: ignore[reportArgumentType]
    ) # type: ignore

def filter_meters(
    results: NewsegsModuleResult,
    meter_type: Sequence[str]|str|None = None,
    meter_name: Sequence[str]|str|None = None,                
) -> Sequence[str]:
    """
    The meter names which match a particular type and/or name collection
    """
    if meter_type is None and meter_name is None:
        raise ValueError('Need at least one of `meter_type` and `meter_name`')
    
    nms = results.get_meter_names()
    if meter_type is not None:
        typs = results.get_meter_types()

        if isinstance(meter_type, str):
            nms = [mtr for mtr, typ in zip(nms, typs) if typ == meter_type]
        else:
            nms = [mtr for mtr, typ in zip(nms, typs) if typ in meter_type]
    
    if meter_name is not None:
        if isinstance(meter_type, str):
            nms = [mtr for mtr in nms if mtr == meter_name]
        else:
            nms = [mtr for mtr in nms if mtr in meter_name]

    return nms

def filter_meter_indices(
    results: NewsegsModuleResult,
    meter_type: Sequence[str]|str|None = None,
    meter_name: Sequence[str]|str|None = None,
) -> Sequence[int]:
    """
    The meter indexes which match a particular type and/or name collection
    """
    if meter_type is None and meter_name is None:
        raise ValueError('Need at least one of `meter_type` and `meter_name`')
    
    nms = results.get_meter_names()
    indxs = range(len(nms))
    
    if meter_type is not None:
        typs = results.get_meter_types()

        if isinstance(meter_type, str):
            indxs = [indxs[i] for i, typ in enumerate(typs) if typ == meter_type]
            nms = [nms[i] for i in indxs]
        else:
            indxs = [indxs[i] for i, typ in enumerate(typs) if typ in meter_type]
            nms = [nms[i] for i in indxs]
    
    if meter_name is not None:
        if isinstance(meter_type, str):
            indxs = [indxs[i] for i, nm in enumerate(nms) if nm == meter_name]
        else:
            indxs = [indxs[i] for i, nm in enumerate(nms) if nm in meter_name]

    return indxs
