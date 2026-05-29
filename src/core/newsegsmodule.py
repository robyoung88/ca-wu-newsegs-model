from __future__ import annotations

from abc import ABCMeta, abstractmethod
import datetime
import uuid
from functools import lru_cache


import numpy as np
import pandas as pd
from src.core.timespan import TimeSpan, RegTimeSpan
from collections.abc import Iterable, Collection, Mapping

class ABCNewsegsModuleResult(metaclass=ABCMeta):
    run_module_uuid = 1
    last_run = datetime.datetime.now()
    
    def __init__(
        self,
        run_module: NewsegsModule | int,
        last_run: datetime.datetime | None = None,
    ):
        if isinstance(run_module, NewsegsModule):
            if last_run is None:
                last_run = run_module.last_run
            run_module = run_module.uuid
        self.run_module_uuid = run_module
        if last_run is None:
            raise ValueError('`last_run` cannot be None if run_module is not a NewsegsModule, is {}'.format(type(run_module)))
        self.last_run = last_run

    @property
    @abstractmethod
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        ...

    @property
    @abstractmethod
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        ...
        
    @abstractmethod
    def get_meter_names(self) -> Iterable:
        ...

    @abstractmethod
    def get_meter_types(self) -> Iterable:
        ...

    @abstractmethod
    def get_dsm_names(self) -> Iterable:
        ...

    @abstractmethod
    def get_dsm_types(self) -> Iterable:
        ...

    @abstractmethod
    def get_timespan(self) -> RegTimeSpan:
        ...

    def meters_to_pandas(self) -> pd.DataFrame:
        """
        Return the meter data as a pandas dataframe

        Caution - this implementation could become unweildy for large results
        """
        return defer_meters_to_pandas(self)
        
    def dsm_to_pandas(self) -> pd.DataFrame:
        """
        Return the dsm data as a pandas dataframe

        Caution - this implementation could become unweildy for large results
        """
        return defer_dsm_to_pandas(self)

    def __hash__(self):
        """The hash is dependent on the module uuid and run time."""
        return hash(
            (
                self.run_module_uuid, 
                self.last_run,
            )
        )


@lru_cache
def defer_meters_to_pandas(res: ABCNewsegsModuleResult):
    datetime = res.get_timespan().to_pandas()
    return pd.DataFrame(data = res.meters.T,
                        index = datetime,
                        columns = res.get_meter_names())

@lru_cache
def defer_dsm_to_pandas(res: ABCNewsegsModuleResult):
    datetime = res.get_timespan().to_pandas()
    return pd.DataFrame(data = res.dsm.T,
                        index = datetime,
                        columns = res.get_dsm_names())

def filter_meters(
    results: ABCNewsegsModuleResult,
    meter_type: Collection|str|None = None,
    meter_name: Collection|str|None = None,                
) -> Collection[str]:
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
    results: ABCNewsegsModuleResult,
    meter_type: Collection|str|None = None,
    meter_name: Collection|str|None = None,
) -> Collection[int]:
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

class NewsegsModule(metaclass=ABCMeta):
    """
    Basic abstract class serving module results
    """

    _dirty = True
    _model = None

    def __init__(self, *args, **kwargs):
        self.uuid = str(uuid.uuid4())

    @abstractmethod
    def run(
        self,
        timespan:TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> ABCNewsegsModuleResult:
        if run_start is None:
            run_start = datetime.datetime.now()
        self.last_run = run_start
        # Returns none as this is still abstract
   
    @property
    @abstractmethod
    def model(self):
        """
        The callback model associated with the module
        """

    @model.setter
    @abstractmethod
    def model(self, model: NewsegsModel):
        ...

    @abstractmethod
    def to_dict(self):
        """
        Configuration as a dictionary
        """
        ...
    
    @abstractmethod
    def sync_with_dict(self, config: Mapping) -> None:
        """
        Update configuration using a dictionary.
        """

    @classmethod
    @abstractmethod
    def from_dict(cls, config: Mapping) -> NewsegsModule:
        """
        An instance of the module configured per a dictionary.
        """

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self._dirty

    @dirty.setter
    def dirty(self, val:bool) -> None:
        self._dirty = val
