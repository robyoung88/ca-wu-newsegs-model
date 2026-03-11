from __future__ import annotations
from abc import ABCMeta, abstractmethod
import numpy as np
from src.core.timespan import TimeSpan

class ABCNewsegsModuleResult(metaclass=ABCMeta):
    @property
    @abstractmethod
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        ...

    @property
    @abstractmethod
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        ...

class NewsegsModule(metaclass=ABCMeta):
    """
    Basic abstract class serving module results
    """
    @abstractmethod
    def run(self, time_span:TimeSpan) -> ABCNewsegsModuleResult:
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
    def model(self, callback_model:newsegsmodel.NewsegsModel):
        ...

    @abstractmethod
    def to_dict(self):
        """
        Configuration as a dictionary
        """
        ...
    
    @abstractmethod
    def load_dict(self):
        """
        Update configuration using a dictionary
        """
        ...
