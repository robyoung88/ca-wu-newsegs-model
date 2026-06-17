from __future__ import annotations
import copy
import datetime
from typing import Any, override, Mapping, Sequence
from functools import singledispatchmethod

import numpy as np
import numpy.typing as npt

from core.environmentserverinterface import EnvironmentServerInterface
from core.newsegsmodelinterface import NewsegsModelInterface
from newsegsgeneration.newsegsgeneration import NewsegsGeneration
from util import classfuncs
from core import newsegsmodule
from core import location
from core import generation
from core import timespan as modtimespan
from core import newsegsmoduleresult

class SprakeGenerationResult(newsegsmoduleresult.NewsegsModuleResult):
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
        model: newsegsmodel.NewsegsModel | None = None, # pyright: ignore[reportUndefinedVariable]
        loc: location.Location | None = None,
    ) -> None:
        raise ValueError('First argument must be a WindTurbineElecGenerator or a PowerPlantHeterogeneousGenerators or a SprakeGeneration, is %s', type(turbine))
    
    # Copy constructor is registered underneath class definition for late-bind.

    @__init__.register(generation.WindTurbineElecGenerator)
    def _from_WindTurbineElecGenerator(
        self,
        turbine: generation.WindTurbineElecGenerator,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None, # pyright: ignore[reportUndefinedVariable]
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
        model: newsegsmodel.NewsegsModel | None = None # pyright: ignore[reportUndefinedVariable]
    ) -> None:
        super().__init__()
        self._generator = copy.deepcopy(generator)
        
        if name is not None:
            self.name = name
        
        if model is not None:
            self.model = model

    @property
    def generator(self) -> generation.PowerPlantHeterogeneousGenerators:
        if self._generator is None:
            raise AttributeError('Generator not yet assigned to module')
        return self._generator

    @property
    @override
    def model(self) -> NewsegsModelInterface:
        return self.generator.model
    
    @model.setter
    @override
    def model(self, model: NewsegsModelInterface) -> None:
        self.generator.model = model
        self.dirty = True

    def run(
        self,
        timespan: modtimespan.TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> SprakeGenerationResult:
        super().run(timespan, run_start)
        energy = self.generator.run(timespan)
        timestep = self.model.get_default_timestep()
        r_timespan = modtimespan.RegTimeSpan(timespan)
        r_timespan.timestep = timestep
        self.dirty = False
        return SprakeGenerationResult(
            self.id,
            self.last_run,
            timespan = r_timespan,
            wind_energy = energy[0,:],
            solar_energy = energy[1,:]
        )

    def set_location(self, loc: location.Location) -> None:
        # Ensure location is only a location, i.e. not an elevated or aspect location
        loc = location.Location(loc)
        self.generator.location = loc

    @property
    @override
    def location(self) -> location.Location | Sequence[location.Location]:
        return self.generator.location
    
    @location.setter
    def location(self, loc: location.Location):
        self.generator.location = loc

    @classmethod
    def from_characteristics(cls,
                             generator: generation.PowerPlantHeterogeneousGenerators,
                             name: str|None = None,
                             model: newsegsmodel.NewsegsModel | None = None, # pyright: ignore[reportUndefinedVariable]
                             ) -> SprakeGeneration:
        o = cls(generator)

        if name is not None:
            o.name = name
        
        if model is not None:
            o.model = model
        
        return o

# SprakeGeneration copy constructor
@SprakeGeneration.__init__.register(SprakeGeneration) # pyright: ignore[reportFunctionMemberAccess]
def _SprakeGeneration_from_other(
    self,
    other: SprakeGeneration
) -> None:
    super(SprakeGeneration, self).__init__()
    self._generator = copy.deepcopy(other.generator)
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass
