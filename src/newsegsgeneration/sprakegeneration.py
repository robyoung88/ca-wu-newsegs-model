from __future__ import annotations
import copy
from typing import override, Mapping
from functools import singledispatchmethod

import numpy as np
import numpy.typing as npt

from src.newsegsgeneration.newsegsgeneration import NewsegsGeneration
from src.util import classfuncs
from src.core import newsegsmodule
from src.core import location
from src.core import generation
from src.core import timespan as modtimespan

class SprakeGenerationResult(newsegsmodule.ABCNewsegsModuleResult):
    def __init__(
        self,
        *args,
        timespan: modtimespan.RegTimeSpan,
        wind_energy: np.ndarray[tuple[int], np.dtype[np.number]],
        solar_energy: np.ndarray[tuple[int], np.dtype[np.number]],
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._timespan = copy.copy(timespan)
        self.set_wind(wind_energy)
        self.set_solar(solar_energy)

    def get_timespan(self) -> modtimespan.RegTimeSpan:
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

    _name = "Sprake Generation Module"

    @singledispatchmethod
    def __init__(
        self,
        turbine: generation.WindTurbineElecGenerator | generation.PowerPlantHeterogeneousGenerators | SprakeGeneration,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None,
        loc: location.Location | None = None,
    ) -> None:
        raise ValueError('First argument must be a WindTurbineElecGenerator or a PowerPlantHeterogeneousGenerators or a SprakeGeneration, is %s', type(turbine))
    
    # Copy constructor is registered underneath class definition for late-bind.

    @__init__.register(generation.WindTurbineElecGenerator)
    def _from_WindTurbineElecGenerator(
        self,
        turbine: generation.WindTurbineElecGenerator,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None,
        loc: location.Location | None = None,
    ) -> None:
        super().__init__()
        self._generator = generation.PowerPlantHeterogeneousGenerators([
            generation.PowerPlantHomogeneousWind(turbine),
            generation.PowerPlantHomogeneousPV(
                generation.SprakePVGISElecGenerator.from_none()
            )
        ])

        if loc is not None:
            self.set_location(loc)
        
        if name is not None:
            self.name = name
        
        if model is not None:
            self.model = model

    @__init__.register(generation.PowerPlantHeterogeneousGenerators)
    def _from_PowerPlantHeterogeneousGenerators(
        self,
        generator: generation.PowerPlantHeterogeneousGenerators,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None
    ) -> None:
        super().__init__()
        self._generator = copy.deepcopy(generator)
        
        if name is not None:
            self.name = name
        
        if model is not None:
            self.model = model

    @property
    def model(self) -> newsegsmodel.NewsegsModel | None:
        return self._generator.model

    @model.setter
    def model(self, model: newsegsmodel.NewsegsModel) -> None:
        self._generator.model = model
        self.dirty = True
    
    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def generator(self) -> generation.PowerPlantHeterogeneousGenerators:
        return self._generator

    def run(
        self,
        timespan: modtimespan.TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> SprakeGenerationResult:
        super().run(timespan, run_start)
        energy = self._generator.run(timespan)
        self.dirty = False
        return SprakeGenerationResult(
            self,
            timespan = timespan,
            wind_energy = energy[0,:],
            solar_energy = energy[1,:]
        )

    def set_location(self, loc: location.Location) -> None:
        # Ensure location is only a location, i.e. not an elevated or aspect location
        loc = location.Location(loc)
        self._generator.location = loc

    @classmethod
    def from_characteristics(cls,
                             generator: generation.PowerPlantHeterogeneousGenerators,
                             name: str|None = None,
                             model: newsegsmodel.NewsegsModel | None = None,
                             ) -> SprakeGeneration:
        o = cls(generator)

        if name is not None:
            o.name = name
        
        if model is not None:
            o.model = model
        
        return o

    @override
    def to_dict(self) -> Mapping:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'generator': self._generator.to_dict()
        }
        return odict
    
    @override
    def sync_with_dict(self, config: Mapping) -> None:
        config = copy.copy(config)

        generator = config.pop('generator', None)
        if generator is not None:
            if isinstance(generator, Mapping):
                generator = generation.generator_from_dict(generator)
            self._generator = generator
        
        conf_keys = config.keys()
        for k in conf_keys:
            if hasattr(self, k):
                v = config.get(k)

                # If the attribute is a read-write property, its class attribute 
                # will have an fset
                try:
                    prop = getattr(type(self), k)
                    if hasattr(prop, 'fset'):
                        getattr(prop, 'fset')(self, v)
                    else:
                        # Otherwise, we assume it is a simple attribute that may be overwritten
                        setattr(self, k, v)
                except AttributeError:
                    setattr(self, k, v)

    @override
    @classmethod
    def from_dict(cls, input: Mapping) -> SprakeGeneration:
        input = copy.copy(input)
        input.pop('class', None)
        if input.get('generator', None) is not None:
            input['generator'] = generation.generator_from_dict(input['generator'])
        return cls.from_characteristics(**input)

# SprakeGeneration copy constructor
@SprakeGeneration.__init__.register(SprakeGeneration)
def _SprakeGeneration_from_other(
    self,
    other: SprakeGeneration
) -> None:
    super(SprakeGeneration, self).__init__()
    self._generator = copy.deepcopy(other.generator)
    self.name = other.name
    self.model = other.model
