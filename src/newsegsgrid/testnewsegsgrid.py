# A test implementation of NewsegsGrid

from src.newsegsgrid import NewsegsGrid
import numpy as np

class TestNewsegsGrid(NewsegsGrid):
    def __init__(self):
        self._baserate = 0.1
        self._standingcharge = 0.5
        self._time_resolution = 3600.0/2.0

    @property
    def baserate(self) -> float:
        return self.baserate

    @baserate.setter
    def baserate(self, rate:float) -> None:
        self._baserate = rate
    
    @property
    def standingcharge(self) -> float:
        return self._standingcharge
    
    @standingcharge.setter
    def standingcharge(self, charge:float) -> None:
        self._standingcharge = charge
    
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
        oarray = np.empty((2,len(self._dts)), dtype=np.float64)
        oarray[0,:] = np.repeat(self._baserate, len(self._dts))
        oarray[1,:] = np.repeat(self._standingcharge*(self._time_resolution/(24.0*3600.0)), len(self._dts))
        return oarray
