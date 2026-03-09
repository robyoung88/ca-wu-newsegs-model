# A test implementation of NewsegsGeneration

from src.newsegsgeneration import NewsegsGeneration
from src.core import RegTimeSpan
from src.core import ABCNewsegsModuleResult
import numpy as np

class TestNewsegsGenerationResult(ABCNewsegsModuleResult):
    @property
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        return self._meters
    
    @property
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        return np.asarray(None)
    
    def set_result(self, oarray):
        self._meters = oarray

    def get_export_meters(self):
        return np.arange(self._meters.shape[0]//2)

class TestNewsegsGeneration(NewsegsGeneration):
    def __init__(self):
        self._basegen = 1.0

    @property
    def basegen(self) -> float:
        return self._basegen

    @basegen.setter
    def basegen(self, power:float) -> None:
        self._basegen = power

    @property
    def model(self):
        return self._model

    @model.setter
    def model(self, callback_model):
        self._model = callback_model
    
    @property
    def calculation_times(self):
        return self._dts

    def run(self, time_span:RegTimeSpan):
        self._dts = time_span.to_pandas()
        oarray = np.empty((1,len(self._dts)), dtype = np.float64)
        oarray[0,:] = np.repeat(self._basegen*time_span.timestep.seconds/3600.0, len(self._dts))
        res = TestNewsegsGenerationResult()
        res.set_result(oarray)
        return res
