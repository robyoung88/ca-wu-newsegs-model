# A test implementation of NewsegsGeneration

from src.newsegsgeneration import NewsegsGeneration
import numpy as np

class TestNewsegsGeneration(NewsegsGeneration):
    def __init__(self):
        self._basegen = 1.0
        self._time_resolution = 3600.0/2.0

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

    def run(self, start_datetime, end_datetime):
        self._dts = np.arange(np.datetime64(start_datetime),
                        np.datetime64(end_datetime),
                        np.timedelta64(int(self._time_resolution), 's'))

        return np.repeat(self._basegen, len(self._dts))
