"""Provides implementation of NewsegsGeneration for Sprake Model."""
from __future__ import annotations

import os
import copy
import datetime
from typing import Any, Type, cast, override, Mapping, Sequence
from functools import singledispatchmethod

import numpy as np
import numpy.typing as npt
import pandas as pd

from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from .newsegsgeneration import NewsegsGeneration
from newsegsmodelframework.core import location
from newsegsmodelframework.core import generation
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.core import newsegsmoduleresult

from config import settings
_LOOKUP_DIR = settings.get('SprakeDataLoc')

NOMINAL_WT_HEIGHT = 10.0

def get_sprake_gamesa_126():
    pcurve = (
        pd.read_excel(
            os.path.join(
                _LOOKUP_DIR,
                'wind_power_curve_investigation.xlsx'
            ),
            sheet_name="gamesa_25_power_curve",
            header=0
        )
    )
    
    tloc = location.RaisedLocation.from_none()
    tloc.height_agl = NOMINAL_WT_HEIGHT
    
    turbine = generation.WindTurbineElecGenerator.from_characteristics(
        cut_in=2.0,
        cut_out=21.0,
        rated_power=2500.0,
        swept_area=np.pi*(0.5 * 126)**2,
        hub_height=NOMINAL_WT_HEIGHT,
        name="Gamesa 126 (Sprake)",
        loc = tloc,
        power_curve=pcurve.to_numpy().T
    )

    return turbine

def get_sprake_ned100():
    cpcurve = (
        pd.read_excel(
            os.path.join(
                _LOOKUP_DIR,
                'power-curve-ned-100.xlsx'
            ),
            sheet_name='power_curve',
            header=0
        )
        .loc[:,['wind_speed','coeff_power']]
    )
    tloc = location.RaisedLocation.from_none()
    tloc.height_agl = NOMINAL_WT_HEIGHT
    turbine = generation.WindTurbineElecGenerator.from_characteristics(
        cut_in=3.0,
        cut_out=20.0,
        rated_power=100.0,
        swept_area=np.pi*(0.5 * 24)**2,
        hub_height=NOMINAL_WT_HEIGHT,
        name="Norvento nED 100 (Sprake)",
        loc = tloc,
        cp_curve=cpcurve.to_numpy().T
    )

    return turbine

class SprakeGenerationResult(newsegsmoduleresult.NewsegsModuleResult):
    """Container for results of SprakeGeneration Module"""
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
    """Implementation of NewsegsGeneration for Sprake Model."""

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

        self._generator.generators[1].location.height_agl = 2. # pyright: ignore[reportAttributeAccessIssue]

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

    @classmethod
    def from_none(cls) -> SprakeGeneration:
        turbine = get_sprake_ned100()
        return cls(turbine)

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
    def location(self) -> location.Location:# | Sequence[location.Location]:
        return self.generator.location#[0]
    
    @location.setter
    def location(self, loc: location.Location):
        self.generator.location = loc

    @property
    def wind_capacity(self) -> float:
        """
        Capacity (kW) of wind turbines
        """
        return self.generator.generators[0].nameplate_capacity
    
    @wind_capacity.setter
    def wind_capacity(self, capacity: float) -> None:
        if self.wind_capacity != capacity:
            turbine_size = self.generator.generators[0].turbine.nameplate_capacity # pyright: ignore[reportAttributeAccessIssue]
            n_turbines = capacity / turbine_size
            self.generator.generators[0].n_turbines = n_turbines # pyright: ignore[reportAttributeAccessIssue]
            self.dirty = True        
    
    @property
    def pv_capacity(self) -> float:
        """
        Capacity (kWp) of PV array
        """
        return self.generator.generators[1].nameplate_capacity
    
    @pv_capacity.setter
    def pv_capacity(self, capacity: float) -> None:
        if self.pv_capacity != capacity:
            pv_size = self.generator.generators[1].pv_array.nameplate_capacity # pyright: ignore[reportAttributeAccessIssue]
            n_arrays = capacity / pv_size
            self.generator.generators[1].n_arrays = n_arrays # pyright: ignore[reportAttributeAccessIssue]
            self.dirty = True

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
    
    @override
    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        odict['wind_capacity'] = self.wind_capacity
        odict['pv_capacity'] = self.pv_capacity
        odict['location'] = self.location.to_dict() # pyright: ignore[reportAttributeAccessIssue]
        return odict
    
    @override
    @classmethod
    def from_dict(
        cls: type[SprakeGeneration], 
        config: dict[str, Any]
    ) -> SprakeGeneration:
        inst = cls.from_none()
        inst.update(config)
        #cast(RaisedLocation, inst.generator.generators[1].location).height_agl = 2.
        return inst

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

# Exclude generator as not necessary - add it back in afterwards
SprakeGeneration._excluded_attributes = (
    super(SprakeGeneration, SprakeGeneration)._excluded_attributes
    + ('_generator',)
)
    