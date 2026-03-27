from __future__ import annotations
from abc import ABCMeta, abstractmethod
import numpy as np
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
