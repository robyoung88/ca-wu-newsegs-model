from __future__ import annotations
import re, copy
from src.newsegsgeneration import NewsegsGeneration
from src.core import ABCNewsegsModuleResult
from src.core import RegTimeSpan
from src.core.generation import PowerPlantHeterogeneousGenerators, PowerPlantHomogeneousPV
from src.core.generation import PowerPlantHomogeneousWind, generator_from_dict
from src.core.generation import WindTurbineElecGenerator, SprakePVGISElecGenerator
#from src.newsegsmodel.newsegsmodel import NewsegsModel
import numpy as np
import numpy.typing as npt

class SprakeGenerationResult(ABCNewsegsModuleResult):
    def __init__(self,
                 timespan: RegTimeSpan,
                 wind_energy:np.ndarray[tuple[int], np.dtype[np.number]], 
                 solar_energy:np.ndarray[tuple[int], np.dtype[np.number]]
                 ) -> None:
        self._timespan = copy.copy(timespan)
        self.set_wind(wind_energy)
        self.set_solar(solar_energy)

    def get_timespan(self) -> RegTimeSpan:
        return self._timespan

    @property
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """
        Metered export electricity. The Sprake model does not consider import electricity for parasitic loads
        """
        minlength = np.min([len(self._wind), len(self._solar)])
        o_arr = np.empty((2,minlength), dtype=np.float64)
        o_arr[0,:] = self._wind[0:minlength]
        o_arr[1,:] = self._solar[0:minlength]
        return o_arr

    @property
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """
        DSM signal. The Sprake model provides no signal for demand side management from generation
        """
        return np.empty((0,0))

    def get_meter_names(self):
        return ('wind_export', 'solar_export')

    def get_meter_types(self):
        return ('export', 'export')

    def get_dsm_names(self):
        return ()
    
    def get_dsm_types(self):
        return ()
    
    def set_wind(self, wind_energy:np.ndarray[tuple[int], np.dtype[np.number]]) -> None:
        self._wind = wind_energy

    def set_solar(self, solar_energy:np.ndarray[tuple[int], np.dtype[np.number]]) -> None:
        self._solar = solar_energy
    
class SprakeGeneration(NewsegsGeneration):

    _default_name = "Sprake Generation Module"

    def __init__(self, turbine:WindTurbineElecGenerator):
        self._generator = PowerPlantHeterogeneousGenerators()
        self._generator.append(PowerPlantHomogeneousWind())
        self._generator.append(PowerPlantHomogeneousPV())
        self._generator.generators[0].location = turbine.location
        self._generator.generators[0].turbine = turbine
        self._generator.generators[1].pv_array = SprakePVGISElecGenerator()
        self._name = self._default_name

    @property
    def model(self) -> NewsegsModel|None:
        return self._model

    @model.setter
    def model(self, model:NewsegsModel) -> None:
        self._model = model
        self._generator.model = model
        self.dirty = True
    
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def generator(self) -> PowerPlantHeterogeneousGenerators:
        return self._generator

    def run(self, timespan:TimeSpan) -> SprakeGenerationResult:
        energy = self._generator.run(timespan)
        self.dirty = False
        return SprakeGenerationResult(timespan, energy[0,:], energy[1,:])

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             turbine:WindTurbineElecGenerator
                             ) -> SprakeGeneration:
        o = cls(turbine)
        o.name = name
        return o

    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'turbine': self._generator.generators[0].to_dict()
        }
        return odict

    @classmethod
    def from_dict(cls, input:Mapping) -> SprakeGeneration:
        if input.get('turbine', None) is not None:
            input['turbine'] = generator_from_dict(input['turbine'])
        return cls.from_characteristics(**input)    
