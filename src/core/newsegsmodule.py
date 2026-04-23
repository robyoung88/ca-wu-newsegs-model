from __future__ import annotations
from abc import ABCMeta, abstractmethod
import numpy as np
import pandas as pd
from src.core.timespan import TimeSpan, RegTimeSpan
from collections.abc import Iterable, Collection

class ABCNewsegsModuleResult(metaclass=ABCMeta):
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
        datetime = self.get_timespan().to_pandas()
        return pd.DataFrame(data=self.meters.T,
                            index=datetime,
                            columns=self.get_meter_names())

    def dsm_to_pandas(self) -> pd.DataFrame:
        """
        Return the dsm data as a pandas dataframe

        Caution - this implementation could become unweildy for large results
        """
        datetime = self.get_timespan().to_pandas()
        return pd.DataFrame(data=self.dsm.T,
                            index=datetime,
                            columns=self.get_dsm_names())

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

    _dirty_flag = True

    @abstractmethod
    def run(self, timespan:TimeSpan) -> ABCNewsegsModuleResult:
        ...
   
    @property
    @abstractmethod
    def model(self):
        """
        The callback model associated with the module
        """
        ...

    @model.setter
    @abstractmethod
    def model(self, callback_model:NewsegsModel):
        ...

    @abstractmethod
    def to_dict(self):
        """
        Configuration as a dictionary
        """
        ...
    
    #@abstractmethod
    #def load_dict(self):
    #    """
    #    Update configuration using a dictionary
    #    """
    #    ...

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self._dirty_flag

    @dirty.setter
    def dirty(self, val:bool) -> None:
        self._dirty_flag = val
