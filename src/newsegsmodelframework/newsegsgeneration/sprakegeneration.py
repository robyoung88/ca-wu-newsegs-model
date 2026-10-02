"""Provides implementation of NewsegsGeneration for Sprake Model."""
from __future__ import annotations

from dataclasses import asdict
import os
import copy
import datetime
from typing import Any, override, Mapping
from functools import singledispatchmethod

import numpy as np
import pandas as pd

from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core.trackeddata import revision_dataclass
from .newsegsgeneration import NewsegsGeneration, NewsegsGenerationConfig
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
    turbine.revision = 0
    turbine._config._last_syncronised = -1

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


@revision_dataclass
class SprakeGenerationConfig(NewsegsGenerationConfig):
    wind_capacity: float = 1.0
    pv_capacity: float = 1.0


class SprakeGeneration(NewsegsGeneration):
    """Implementation of NewsegsGeneration for Sprake Model."""

    _name = "Sprake Generation Module"

    @override
    def _generate_config(self, *args, **kwargs) -> SprakeGenerationConfig:
        return SprakeGenerationConfig(*args, **kwargs)
    _config: SprakeGenerationConfig # pyright: ignore[reportIncompatibleVariableOverride]

    generator = generation.NewsegsGeneratorProperty(
        default = None,
        oftype = generation.PowerPlantHeterogeneousGenerators
    ) # pyright: ignore[reportAssignmentType]

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: generation.WindTurbineElecGenerator | generation.PowerPlantHeterogeneousGenerators | SprakeGeneration,
    ) -> None:
        raise ValueError(f'First argument must be a WindTurbineElecGenerator or a PowerPlantHeterogeneousGenerators or a SprakeGeneration, is {type(dispatch_arg)}')
    
    # Copy constructor is registered underneath class definition for late-bind.

    @__init__.register(generation.WindTurbineElecGenerator)
    def _from_WindTurbineElecGenerator(
        self,
        turbine: generation.WindTurbineElecGenerator,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        self.generator = generation.PowerPlantHeterogeneousGenerators([
            generation.PowerPlantHomogeneousWind(turbine),
            generation.PowerPlantHomogeneousPV(
                generation.SprakePVGISElecGenerator.from_none()
            )
        ])

        # Set the capacities again
        self.pv_capacity = self._config.pv_capacity
        self.wind_capacity = self._config.wind_capacity

        if 'location' in kwargs.keys():
            self.location = self._config.location # pyright: ignore[reportAttributeAccessIssue]

        self.generator.generators[1].location.height_agl = 2. # pyright: ignore[reportAttributeAccessIssue]
        # Once constructed, the generator is not saved out so we can syncronise it now
        self.generator.chain_syncronise()

    @__init__.register(generation.PowerPlantHeterogeneousGenerators)
    def _from_PowerPlantHeterogeneousGenerators(
        self,
        generator: generation.PowerPlantHeterogeneousGenerators,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        self._generator = copy.deepcopy(generator)
        self.generator.chain_syncronise()

        # Set the capacities again
        self.pv_capacity = self._config.pv_capacity
        self.wind_capacity = self._config.wind_capacity

    @classmethod
    def from_none(cls) -> SprakeGeneration:
        turbine = get_sprake_ned100()
        return cls(turbine)

    @property
    @override
    def model(self) -> NewsegsModelInterface:
        try:
            return self.generator.model
        except AttributeError:
            return super().model
    
    @model.setter
    @override
    def model(self, model: NewsegsModelInterface) -> None:
        try:
            self.generator.model = model
            self.generator.chain_syncronise()
        except AttributeError:
            pass
        model_setter = NewsegsGeneration.model.fset
        assert model_setter is not None
        model_setter(self, model)

    @property
    # @override # This is technically an override, but pylance doesn't know it
    def location(self) -> location.Location:
        try:
            return self.generator.location
        except AttributeError:
            return super().location # type: ignore
    
    @location.setter
    def location(self, loc: location.Location):
        # Ensure location is only a location, i.e. not an elevated or aspect location
        loc = location.Location(loc)
        try:
            self.generator.location = loc
            self.generator.chain_syncronise()
        except AttributeError:
            pass
        self._config.location = loc # pyright: ignore[reportAttributeAccessIssue]

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

        return SprakeGenerationResult(
            self.id,
            self.last_run,
            timespan = r_timespan,
            wind_energy = energy[0,:],
            solar_energy = energy[1,:]
        )
    
    @property
    def wind_capacity(self) -> float:
        """
        Capacity (kW) of wind turbines
        """
        wind_cap = self._config.wind_capacity
        if self.generator and not self.generator.generators[0].nameplate_capacity == wind_cap:
            self.generator.generators[0].set_nameplate_capacity(wind_cap)
            self.generator.chain_syncronise()
        return wind_cap
    
    @wind_capacity.setter
    def wind_capacity(self, capacity: float) -> None:
        if self._config.wind_capacity != capacity:
            self._config.wind_capacity = capacity
        if self.generator:
            self.generator.generators[0].set_nameplate_capacity(capacity)
            self.generator.chain_syncronise()
    
    @property
    def pv_capacity(self) -> float:
        """
        Capacity (kWp) of PV array
        """
        pv_cap = self._config.pv_capacity
        if self.generator and not self.generator.generators[1].nameplate_capacity == pv_cap:
            self.generator.generators[1].set_nameplate_capacity(pv_cap)
            self.generator.chain_syncronise()
        return pv_cap
    
    @pv_capacity.setter
    def pv_capacity(self, capacity: float) -> None:
        if self._config.pv_capacity != capacity:
            self._config.pv_capacity = capacity
        if self.generator:
            self.generator.generators[1].set_nameplate_capacity(capacity)
            self.generator.chain_syncronise()

    @override
    def update(self, config):
        super().update(config)
        r0 = self.revision
        if isinstance(config, Mapping):
            if '_config' in config.keys():
                if 'pv_capacity' in config['_config'].keys():
                    self.pv_capacity = self._config.pv_capacity
                if 'wind_capacity' in config['_config'].keys():
                    self.wind_capacity = self._config.wind_capacity
        self.generator.chain_syncronise()
        self.revision = r0
        
    
    @override
    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        odict['wind_capacity'] = self.wind_capacity
        odict['pv_capacity'] = self.pv_capacity
        #odict['location'] = self.location.to_dict() # pyright: ignore[reportAttributeAccessIssue]
        return odict
    
    @override
    @classmethod
    def from_dict(
        cls: type[SprakeGeneration], 
        config: dict[str, Any]
    ) -> SprakeGeneration:
        inst = cls.from_none()
        inst.update(config)
        inst.wind_capacity = inst.wind_capacity
        inst.pv_capacity = inst.pv_capacity
        inst.location = inst._config.location # pyright: ignore[reportAttributeAccessIssue]
        #cast(RaisedLocation, inst.generator.generators[1].location).height_agl = 2.
        return inst

# SprakeGeneration copy constructor
@SprakeGeneration.__init__.register(SprakeGeneration) # pyright: ignore[reportFunctionMemberAccess]
def _SprakeGeneration_from_other(
    self,
    other: SprakeGeneration
) -> None:
    super(SprakeGeneration, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys(): # pyright: ignore[reportArgumentType]
        setattr(self, k, copy.copy(getattr(other, k)))

    self.generator = copy.deepcopy(other.generator)
    self.generator.chain_syncronise()

# Exclude generator as not necessary - add it back in afterwards
SprakeGeneration._excluded_attributes = (
    super(SprakeGeneration, SprakeGeneration)._excluded_attributes
    + ('_generator',)
)
    