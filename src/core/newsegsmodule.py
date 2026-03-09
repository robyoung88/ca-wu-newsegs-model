from __future__ import annotations
from abc import ABCMeta
import numpy as np
from core.timespan import TimeSpan

class NewsegsModuleResult(metaclass=ABCMeta):
    @property
    @abstractmethod
    def energy(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
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
    def run(self, time_span:TimeSpan) -> NewsegsModuleResult:
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
    def model(self, callback_model:newsegsmodel.NewsegsModel)