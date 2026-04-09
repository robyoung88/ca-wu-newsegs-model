from __future__ import annotations
from abc import ABCMeta, abstractmethod
import numpy as np
import pandas as pd
from src.core.timespan import TimeSpan, RegTimeSpan
from collections.abc import Iterable

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

def filter_meters(results: ABCNewsegsModuleResult,
                  meter_type: str
) -> Iterable:
    """
    The meters which match a particular type.
    """
    nms = results.get_meter_names()
    typs = results.get_meter_types()
    return [mtr for mtr, typ in zip(nms, typs) if typ == meter_type]

class NewsegsModule(metaclass=ABCMeta):
    """
    Basic abstract class serving module results
    """
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
