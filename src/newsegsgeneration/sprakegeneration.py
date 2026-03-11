
from src.newsegsgeneration import NewsegsGeneration
from src.core import ABCNewsegsModuleResult
from src.core import RegTimeSpan
import numpy as np
import numpy.typing as npt

class SprakeGenerationResult(ABCNewsegsModuleResult):
    @property
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """
        Metered export electricity. The Sprake model does not consider import electricity for parasitic loads
        """
        return self._meters

    @property
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """
        DSM signal. The Sprake model provides no signal for demand side management from generation
        """
        return np.asarray(None)

    def get_meter_names(self):
        return ['wind', 'solar']
    
class SprakeGeneration(NewsegsGeneration):
    def __init__(self):
        self._wt_characteristics = None
        self._pv_characteristics = None