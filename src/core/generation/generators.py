"""
Representations of energy converters for use in NewsegsGeneration.

A collection of classes used for representation of converters of environmental
to electrical energy which may be used as part of composition of a 
NewsegsGeneration module.

Exports:
    ABCElecGenerator: Abstract base class for all generators.
    WindTurbineElecGenerator: Simple WTG using a Cp curve for transformation
                              of average wind speeds (e.g. 10 min).
    PowerPlantHomogeneousWind: Scaling of WindTurbineElecGenerator to represent
                               a Real of independent homogeneous wind
                               turbines across a homogeneous site.
    ABCPVElecGenerator: Extension of ABCElecGenerator as an abstract base class
                        for solar photovoltaic generators.
    SprakePVElecGenerator: Extension of ABCPVElecGenerator using the simple PV
                           model of Sprake dependent only upon horizontal flux.
    PowerPlantHomogeneousPV: Scaling of an ABCPVElecGenerator to represent
                             a Real of independent modules across a 
                             homogeneous site.
    PowerPlantHeterogeneousGenerators: Composition of a Real of 
                                       ABCElecGenerators.
    
    GENERATOR_CONSTRUCTORS: A dictionary of all the implementations of
                            ABCElecGenerator defined in this module.

    generator_from_dict: Returns a generator when provided its dictionary
                         representation (from .to_dict() method).
"""
from __future__ import annotations

import re
import copy
from typing import Any
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Mapping, Collection, Iterable
from typing import cast, override, SupportsFloat, Type, TypeVar
from functools import singledispatchmethod

import numpy as np
import numpy.typing as npt
import pandas as pd
import pvlib

from util import classfuncs
from core import newsegscomponent
from core import timespan as modtimespan
from core import location
from core import environmentserverinterface

T = TypeVar('T')
Real = SupportsFloat

def _cp_interpolant_factory(
    cp_curve: np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]],
) -> Callable[[npt.ArrayLike], npt.ArrayLike]:
    """
    Returns a function taking axial mean wind speeds and returning Cp.

    Args:
        cp_curve: 2D array of Cp data, where row 0 is axial wind speeds (m/s)
                  and row 1 is Cp value.
    """
    def interpolant(x):
        return np.interp(
            x, 
            cp_curve[0,:].astype(np.float64), 
            cp_curve[1,:].astype(np.float64), 
            left=0.0, 
            right=0.0
        )
    return interpolant

class ABCElecGenerator(newsegscomponent.NewsegsComponent):
    """
    Represents a converter of environmental conditions to electrical energy.

    An abstract class which is implemented for the individual or grouped 
    converters composed in a NewsegsGeneration implementation. The interface
    allows for the following activities:

    - running (i.e. predicting electrical output over a TimeSpan).
    - setting and accessing a NewsegsModel used for serving environmental data.
    - accessing a name for the current generator configuration.
    - storing the generator configuration as a python dictionary.
    - setting and accessing the location data for the generator.
    - accessing the nameplate electrical capacity of the generator.
    """
    _name = 'Generator'

    @abstractmethod
    def run(
        self, timespan: modtimespan.TimeSpan
    ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        """
        Returns an array of generation data over the provided TimeSpan.

        By default, the returned data is the Real of units produced in the
        preceding time interval in kWh. Deviations from this are indicated in
        the override / extension documentation.
        """

    @property
    @abstractmethod
    def name(self) -> str:
        """
        A friendly string identifier for the configuration.

        Not strictly unique, but used for identification of stored configurations.
        """

    @property
    @abstractmethod
    def model(self) -> environmentserverinterface.EnvironmentServerIntrface: 
        """
        The callback NewsegsModel model associated with the generator.
        """

    @model.setter
    @abstractmethod
    def model(self, model: environmentserverinterface.EnvironmentServerIntrface):
        ...

    @abstractmethod
    def to_dict(self) -> Mapping:
        """
        Returns Generator/Powerplant configuration as a dictionary.
        """

    def sync_with_dict(self, config: dict[str, Any]) -> None:
        """
        Update configuration using a dictionary.

        In the default implementation, will go through each key in the dict.
        If there is an attribute with an fset attribute, then assume it is a
        read-write property and update it via the fset. Otherwise, set the
        attribute directly.
        """
        for k in config.keys():
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
    
    @classmethod
    @abstractmethod
    def from_dict(cls: Type['ABCElecGenerator'], config: dict[str, Any]) -> 'ABCElecGenerator':
        """
        An instance of the generator configured per a dictionary.
        """

    @property
    @abstractmethod
    def location(self) -> location.Location:
        """
        The Location of the generator for environmental conditions.
        """

    @location.setter
    @abstractmethod
    def location(self, loc: location.Location):
        ...

    @property
    @abstractmethod
    def nameplate_capacity(self) -> float:
        """
        The total nameplate capacity in kW.
        """

class ABCScalingPowerPlant(ABCElecGenerator):
    """
    Represents a power plant of homogeneous generating units
    """
    _name = 'Power plant'
    _n = 1

    @property
    def n(self) -> float:
        """
        The Real of generating units in the power plant
        """
        return self._n
    
    @n.setter
    def n(self, n) -> None:
        self._n = n

    @abstractmethod
    def set_nameplate_capacity(self, nameplate_capacity: Real) -> None:
        """
        Alter the Real of generating units to match the desired nameplate capacity
        """

class WindTurbineElecGenerator(ABCElecGenerator):
    """
    Simple WTG using a Cp curve for transformation of wind speed.

    This WTG requests wind speeds from the model's local environment server,
    and applies these directly to a stored, piecewise-linearly interpolated
    Cp curve.

    Assumptions:
        
        - Wind speed averaging intervals from environment server appropriate
          for Cp Curve.
        
        - Axial alignment sufficient at all times for Cp curve accuracy.

            - (Corollary) negliglible vertical component of wind speed.
        
        - Wind turbine availability 100%.

        - No degredation in performance over time.
    """

    _default_cp_curve = np.asarray(
        [
            [0,  3,  5,   10, 25, 26, 50],
            [0.0,0.0,0.25,0.4,0.1,0.0,0.0]
        ]).reshape((2,-1))

    _name = "Wind Turbine"

    @singledispatchmethod
    def __init__(
        self,
        cp_curve: np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]] | WindTurbineElecGenerator,
        swept_area: Real | None = None,
        hub_height: Real | None = None,
        rated_power: Real | None = None,
        cut_in: Real | None = None,
        cut_out: Real | None = None,
        loc: location.Location | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        """
        Default assumes None
        """
        raise ValueError('First argument must be a cp curve or a WindTurbineElecGenerator, is %s', type(cp_curve))

    # Copy constructor is registered underneath class definition for late-bind.
    @__init__.register(np.ndarray)
    def _from_cp_curve(
        self,
        cp_curve: np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]],
        swept_area: Real | None = None,
        hub_height: Real | None = None,
        rated_power: Real | None = None,
        cut_in: Real | None = None,
        cut_out: Real | None = None,
        loc: location.Location | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        
        self.set_cp_curve(cp_curve)
        self._swept_area = float(swept_area) if swept_area is not None else 1.
        self._hub_height = float(hub_height) if hub_height is not None else 10.
        self._rated_power = float(rated_power) if rated_power is not None else 0.245
        self._cut_in = float(cut_in) if cut_in is not None else 0.
        self._cut_out = float(cut_out) if cut_out is not None else 25.

        if loc is None:
            loc = location.RaisedLocation.from_none()
            loc.height_agl = self._hub_height
            self._location = loc
        else:
            self.location = loc
        
        if name is not None:
            self._name = name
        
        if model is not None:
            self._model = model
        else:
            self._model = None
    
    @classmethod
    def from_none(cls) -> WindTurbineElecGenerator:
        return cls(cls._default_cp_curve)

    @property
    @override
    def model(self) -> environmentserverinterface.EnvironmentServerIntrface:
        if self._model is None:
            raise AttributeError('model has not been set')
        return self._model

    @model.setter
    def model(self, model: environmentserverinterface.EnvironmentServerIntrface) -> None:
        self._model = model

    @property
    def cut_in(self) -> float:
        """
        Mean wind speed (m/s) below which no output (not enforced in Cp).
        """
        return self._cut_in

    @cut_in.setter
    def cut_in(self, cut_in: Real) -> None:
        self._cut_in = float(cut_in)

    @property
    def cut_out(self) -> float:
        """
        Mean wind speed (m/s) above which no output (not enforced in Cp).
        """
        return self._cut_out

    @cut_out.setter
    def cut_out(self, cut_out: Real) -> None:
        self._cut_out = float(cut_out)

    @property
    def rated_power(self) -> float:
        """
        Alternative name for nameplate_capacity (kW).
        """
        return self._rated_power

    @rated_power.setter
    def rated_power(self, rated_power: Real) -> None:
        self._rated_power = float(rated_power)

    @property
    @override
    def nameplate_capacity(self) -> float:
        """
        Power (kW) at rated wind speed.

        Not necessarily peak generator output over any averaging period, and
        not enforced as a maximum in Cp curve.
        """
        return self.rated_power

    @property
    def swept_area(self) -> float:
        """
        Area (m²) swept by blades, used in combination with Cp curve for
        power output.
        """
        return self._swept_area

    @swept_area.setter
    def swept_area(self, swept_area: Real) -> None:
        self._swept_area = float(swept_area)

    @property
    def rotor_diameter(self) -> float:
        """
        Alternative accessor for swept_area. Diameter (m) of swept circle.

        Note that for a coned rotor, this diameter is less than the length of
        the blade plus half the diameter of the hub. Use the diameter used in
        Cp calculation.
        """
        return 2.0 * np.sqrt(self._swept_area) / np.pi

    @rotor_diameter.setter
    def rotor_diameter(self, diameter: Real) -> None:
        self._swept_area = np.pi * (0.5 * float(diameter)) ** 2

    @property
    def hub_height(self) -> float:
        """
        Height of rotor centre (m) for environmental data access.
        """
        return self._hub_height

    @hub_height.setter
    def hub_height(self, height: Real) -> None:
        self._hub_height = float(height)
        try:
            self.location.height_agl = height
        except AttributeError:
            pass

    @property
    @override
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    @override
    def location(self) -> location.RaisedLocation:
        if self._location is None:
            raise AttributeError('location has not been set')
        return self._location

    @location.setter
    def location(self, loc: location.Location) -> None:
        if (
            isinstance(loc, location.RaisedLocation)
            and loc.height_agl != self.hub_height
        ):
            warnings.warn(('Provided location includes a height unequal to '
                           'hub, and will be ignored.'),
                          UserWarning)

        self._location = location.RaisedLocation(loc)
        self._location.height_agl = self.hub_height

    def set_cp_curve(
        self,
        cp_curve: np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]]
    ) -> None:
        """
        Set the Cp function using an array of wind speed - Cp pairs.

        Output power is modelled by:
            P = Cp * 0.5 * rho * A * U³
        where rho is air density, A is the swept area of the turbine, and U
        is the axial wind speed. Cp is the ratio of converted to total kinetic
        power in the wind and is generally limited to a maximum of 16/27 (i.e.)
        the 'Betz limit'.
        """
        if np.any(cp_curve[1,:]> 16/27):
            warnings.warn(
                ('Cp curve contains entries exceeding the Betz limit. This is '
                'implausible with a standard HAWT. Check your power curve.'),
                UserWarning)
        if np.any(cp_curve[1,:] < 0.0):
            warnings.warn(
                ('Cp curve contains negative values. Self-consumption should '
                'be handled separately. They will be overwritten by zeros.'),
                UserWarning)
            cp_curve = copy.copy(cp_curve)
            cp_curve[1,cp_curve[1,:]<0.0] = 0.0
        self._cp_curve = copy.copy(cp_curve)
        self._cp_func = _cp_interpolant_factory(cp_curve)

    def set_power_curve(self,
                        power_curve:
                            np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]],
                        air_density: float = 1.225
                        ) -> None:
        """
        Set Cp using a power curve.

        Note that this calculation is dependent upon swept area. If the swept
        area has not been set prior to use of this method, the Cp curve will be
        incorrect.

        Args:
            power_curve: 2D array of power data, where row 0 is axial wind 
                         speeds (m/s) and row 1 is output power (kW).
            air_density: The air density (kg/m³) used for determination of
                         the power curve.
        """
        
        available_power = (
            0.5 * air_density * self.swept_area
            * power_curve[0,:] * power_curve[0,:] * power_curve[0,:]
        ) / 1000.0 # in kW, to match power curve

        cp_curve = copy.copy(power_curve)

        with np.errstate(divide='ignore', invalid='ignore'):
            cp_curve[1,:] = power_curve[1,:] / available_power

        cp_curve[1,:] = np.where(available_power<=0.0, 0.0, cp_curve[1,:])

        self.set_cp_curve(cp_curve)

    @property
    def cp(self) -> Callable:
        """
        Function taking axial wind speeds and returning Cp.
        """
        return self._cp_func

    @override
    def run(
        self, timespan: modtimespan.TimeSpan
    ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        """
        Returns an array of generation data over the provided TimeSpan.

        Returned array is a timeseries of electrical energy (kWh) produced by
        the WTG under idealised conditions, assuming the provided Cp or power
        curve is applicable at all times.

        Output power is modelled by:
            P = Cp * 0.5 * rho * A * U³
        where rho is air density, A is the swept area of the turbine, and U
        is the axial wind speed.

        Assumptions:
            - Wind speed averaging intervals from environment server 
              appropriate for Cp Curve.
        
            - Axial alignment sufficient at all times for Cp curve accuracy.
                - (Corollary) negliglible vertical component of wind speed.
        
            - Wind turbine availability 100%.

            - No degredation in performance over time.
        """
        if self.model is None:
            raise ValueError(
                (
                    'Generator %s requires a model to serve environmental data' # pylint: disable=consider-using-f-string
                ) % self._name
            )
        lenvs = self.model.local_env
        wind_speeds = lenvs.get_wind_speeds(self.location, timespan)
        air_density = lenvs.get_air_density(self.location, timespan)

        # Power in kW. This is retrospective - i.e. is assumed to be a mean 
        # over the previous measuring period
        power = (0.5 * air_density * self.swept_area * self.cp(wind_speeds)
                 * wind_speeds**3) / 1000.0

        deltatime = lenvs.get_wind_timestep().seconds * modtimespan.SECONDS_TO_HOURS

        # Assumption: returned timeseries is regular and indexed to the wind
        # speed times
        energy = power * deltatime

        # First time has no preceding interval
        energy[0] = 0.0

        return energy.reshape((1,-1))

    @classmethod
    def from_characteristics(
        cls: Type['WindTurbineElecGenerator'],
        cut_in: Real,
        cut_out: Real,
        rated_power: Real,
        swept_area: Real,
        hub_height: Real,
        name: str | None = None,
        loc: location.Location | None = None,
        cp_curve:
            np.ndarray[tuple[int,int], np.dtype[np.float64]] | None = None,
        power_curve:
            np.ndarray[tuple[int,int], np.dtype[np.float64]] | None = None,
    ) -> 'WindTurbineElecGenerator':
        """
        Return a new WindTurbineElecGenerator given its key characteristics.
        """
        o = cls.from_none()

        o.swept_area = swept_area
        o.hub_height = hub_height
        o.rated_power = rated_power
        o.cut_in = cut_in
        o.cut_out = cut_out

        if name is not None:
            o.name = name

        if loc is not None:
            o.location = loc

        if not cp_curve is None:
            cp_curve = np.asarray(cp_curve)
            o.set_cp_curve(cp_curve)
        elif not power_curve is None:
            o.set_power_curve(power_curve)
        else:
            raise ValueError("Either cp_curve or power_curve must be specified")

        return o

    @override
    def to_dict(self) -> dict:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'cut_in': self._cut_in,
            'cut_out': self._cut_out,
            'rated_power': self._rated_power,
            'swept_area': self._swept_area,
            'hub_height': self._hub_height,
            'loc': self._location.to_dict(),
            'cp_curve': self._cp_curve
        }

        return odict
    
    @override
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        config = copy.copy(config)

        cp_curve = config.pop('cp_curve', None)
        if cp_curve is not None:
            cp_curve = np.asarray(cp_curve)
            self.set_cp_curve(cp_curve)
        
        loc = config.pop('loc', None)
        if loc is not None:
            with warnings.catch_warnings():
                warnings.simplefilter('ignore')
                if isinstance(loc, location.Location):
                    self.location = loc
                elif isinstance(loc, dict):
                    self.location = location.location_from_dict(loc)

        super().sync_with_dict(config)

    @classmethod
    def from_dict(
        cls: Type[WindTurbineElecGenerator],
        config: dict[str, Any]
    ) -> WindTurbineElecGenerator:
        """
        Return a WindTurbineElecGenerator from a dictionary.
        """
        config = copy.copy(config)
        config.pop('class', None)
        if config.get('loc', None) is not None:
            config['loc'] = location.location_from_dict(config['loc'])
        return cls.from_characteristics(**config)
    
    def __getstate__(self):
        """
        State for pickling.

        Essentially just provides the __dict__ contents, but after
        stripping out the _cp_func so that it may be re-built after
        unpickling.
        """
        odict = self.__dict__.copy()
        odict.pop('_cp_func', None)
        return odict
    
    def __setstate__(self, state):
        """
        Set the state of a new instance - for unpickling.

        Essentially copies over the state to the __dict__ then
        forces creation of the _cp_func.
        """
        vars(self).update(state)
        self.set_cp_curve(self._cp_curve)

# WindTurbineElecGenerator copy constructor
@WindTurbineElecGenerator.__init__.register(WindTurbineElecGenerator) # pyright: ignore[reportFunctionMemberAccess]
def WindTurbineElecGenerator_from_other(
    self,
    other: WindTurbineElecGenerator
) -> None:
    self.set_cp_curve(other._cp_curve)
    self._swept_area = other.swept_area
    self._hub_height = other.hub_height
    self._rated_power = other.rated_power
    self._cut_in = other.cut_in
    self._cut_out = other.cut_out
    self.location = copy.copy(other.location)
    self._name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

class PowerPlantHomogeneousWind(ABCScalingPowerPlant):
    """
    A power plant consisting of a Real of identical wind turbines.
    
    The Real of turbines may be non-integer, and all are at a single nominal
    location.
    """
    _name = "Wind Farm"

    @singledispatchmethod
    def __init__(
        self,
        turbine: WindTurbineElecGenerator | PowerPlantHomogeneousWind,
        loc: location.Location | None = None,
        n: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        raise ValueError('First argument must be a WindTurbineElecGenerator or PowerPlantHomogeneousWind, is %s', type(turbine))
    
    # Copy constructor is registered underneath class definition for late-bind
    @__init__.register(WindTurbineElecGenerator)
    def _from_WindTurbineElecGenerator(
        self,
        turbine: WindTurbineElecGenerator,
        loc: location.Location | None = None,
        n: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        # Take a copy of the turbine, primarily to ensure that
        # changing its location does not break its parent
        self._turbine = copy.deepcopy(turbine)
        if loc is not None:
            self._turbine.location = loc
        
        self._n = float(n) if n is not None else 1.
        
        if name is not None:
            self._name = name
        
        if model is not None:
            # Go via property to push this to turbine
            self.model = model
    
    @classmethod
    def from_none(cls) -> PowerPlantHomogeneousWind:
        return cls(WindTurbineElecGenerator.from_none())

    @property
    def model(self) -> environmentserverinterface.EnvironmentServerIntrface:
        """
        The NewSEGS Model for environmental data.

        This is stored within the turbine instance to maintain sync and so
        cannot be accessed prior to a turbine being assigned.
        """
        return self.turbine.model
    
    @model.setter
    def model(self, model: environmentserverinterface.EnvironmentServerIntrface) -> None:
        self.turbine.model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name
    
    @property
    def location(self) -> location.RaisedLocation:
        """
        The location of the power plant

        This is stored within the turbine instance to maintain sync and so
        cannot be accessed prior to a turbine being assigned.
        """
        return self.turbine.location

    @location.setter
    def location(self, loc: location.Location) -> None:
        self.turbine.location = loc

    @property
    def turbine(self) -> WindTurbineElecGenerator:
        if self._turbine is None:
            raise AttributeError('turbine is not set')
        return self._turbine

    @turbine.setter
    def turbine(self, turbine: WindTurbineElecGenerator) -> None:
        if hasattr(self, '_turbine') and self._turbine is not None:
            try:
                loc = self._turbine.location
            except AttributeError:
                loc = None
            try:
                mdl = self._turbine.model
            except AttributeError:
                mdl = None
        else:
            loc = None
            mdl = None

        self._turbine = copy.deepcopy(turbine)

        if loc is not None:
            self._turbine.location = loc
        if mdl is not None:
            self._turbine.model = mdl

    @property
    def n_turbines(self) -> float:
        return self._n

    @n_turbines.setter
    def n_turbines(self, n: Real) -> None:
        n = float(n)
        if n < 0:
            raise ValueError("Real of turbines must be positive, is %s", n)
        self._n = n

    @property
    def nameplate_capacity(self):
        return self.turbine.rated_power * self._n

    @override
    def set_nameplate_capacity(self, nameplate_capacity: Real) -> None:
        """
        Alter the Real of generators to match the required capacity.
        """
        n_turb = float(nameplate_capacity) / self.turbine.rated_power
        self.n = n_turb

    @property
    def swept_area(self):
        return self.turbine.swept_area * self._n
    
    def run(
            self, 
            timespan: modtimespan.TimeSpan
        ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        return self._n * self.turbine.run(timespan)

    @classmethod
    def from_characteristics(
        cls: Type['PowerPlantHomogeneousWind'],
        turbine: WindTurbineElecGenerator,
        n: Real,
        loc: location.RaisedLocation | None = None,
        name: str|None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None,
    ) -> 'PowerPlantHomogeneousWind':
        a = locals()
        del a['cls']
        del a['turbine']

        return cls(turbine, **a)

    @override
    def to_dict(self) -> Mapping:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'turbine': self.turbine.to_dict(),
            "n": self._n
        }
        return odict
    
    @override
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        config = copy.copy(config)
        turbine = config.pop('turbine', None)
        if turbine is not None:
            if isinstance(turbine, dict):
                turbine = generator_from_dict(turbine)
                if not isinstance(turbine, WindTurbineElecGenerator):
                    raise TypeError(f'generator is of incorrect type: {type(turbine)}')
            self._turbine = turbine
            # Expect the location to get overwritten in the setter;
            # as this is recovery, we do actually want the location
            # though we don't want to mess with the model.
            self.location = turbine.location
        
        # This looks risky, but practically may only result in
        # some redundant attributes if the config is bad.
        super().sync_with_dict(config)
    
    @classmethod
    def from_dict(
        cls: Type['PowerPlantHomogeneousWind'],
        config: dict[str, Any]
    ) -> 'PowerPlantHomogeneousWind':
        ip = copy.copy(config)
        ip.pop('class', None)

        if ip.get('turbine', None) is not None:
            ip['turbine'] = generator_from_dict(ip['turbine'])
            if not isinstance(ip['turbine'], WindTurbineElecGenerator):
                    raise TypeError(f'generator is of incorrect type: {type(ip['turbine'])}')

        return cls.from_characteristics(**ip)

# PowerPlantHomogeneousWind copy constructor
@PowerPlantHomogeneousWind.__init__.register(PowerPlantHomogeneousWind) # pyright: ignore[reportFunctionMemberAccess]
def PowerPlantHomogeneousWind_from_other(
    self,
    other: PowerPlantHomogeneousWind
) -> None:
    self._turbine = copy.deepcopy(other.turbine) # Bypass setter to avoid location and model synchronisation
    self.n = other.n
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

class ABCPVElecGenerator(ABCElecGenerator):
    """
    Abstract base class for all PV generation models
    """
    _name = "PV array"

    @singledispatchmethod
    def __init__(
        self,
        peak_power: Real | ABCPVElecGenerator,
        loc: location.AspectLocation | None = None,
        total_area: Real | None = None,
        collector_area: Real | None = None,
        frame_factor: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        """
        Default assumes None
        """
        raise ValueError('First argument must be a numeric peak power (STC) or an ABCPVElecGenerator, is %s', type(peak_power))

    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(Real)
    def _from_Real(
        self,
        peak_power: Real,
        loc: location.AspectLocation | None = None,
        total_area: Real | None = None,
        collector_area: Real | None = None,
        frame_factor: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        self._peak_power = float(peak_power)
        self._total_area = float(total_area) if total_area is not None else self._peak_power / 0.435
        if collector_area is not None:
            self._collector_area = float(collector_area)
            self._frame_factor = self._collector_area / self._total_area
        elif frame_factor is not None:
            self._frame_factor = float(frame_factor)
            self._collector_area = self._frame_factor * self._total_area
        else:
            self._frame_factor = 1.0
            self._collector_area = self._frame_factor * self._total_area
        
        if loc is None:
            loc = location.AspectLocation.from_none()
            loc.azimuth = 180.
            loc.pitch = 35.
            self._location = loc
        else:
            self._location = loc
        
        if name is not None:
            self._name = name
        
        if model is not None:
            self._model = model
        else:
            self._model = None

    @classmethod
    def from_none(cls) -> ABCPVElecGenerator:
        return cls(1.0)

    @property
    def model(self) -> environmentserverinterface.EnvironmentServerIntrface:
        if self._model is None:
            raise AttributeError('model has not been set')
        return self._model
    
    @model.setter
    def model(self, model: environmentserverinterface.EnvironmentServerIntrface) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def peak_power(self) -> float:
        return self._peak_power
    
    @peak_power.setter
    def peak_power(self, power: Real) -> None:
        power = float(power)
        if power < 0:
            raise ValueError("`peak_power` should be positive, is %s", power)
        self._peak_power = power

    @property
    def nameplate_capacity(self) -> float:
        return self.peak_power

    @property
    def total_area(self) -> float:
        """
        The total area of the module or array in m², including frame

        When setting the total or collector area of the array, if a `.frame_factor` is defined, the other area will be set automatically. If this behaviour is not desired, set `.frame_factor=None`
        """
        return self._total_area

    @total_area.setter
    def total_area(self, area: Real) -> None:
        area = float(area)
        if area < 0:
            raise ValueError("`area` should be positive, is %s", area)
        self._total_area = area
        if not self._frame_factor is None:
            self._collector_area = self._total_area * self._frame_factor

    @property
    def collector_area(self) -> float:
        """
        The area of collector surface of the module or array in m²

        When setting the total or collector area of the array, if a `.frame_factor` is defined, the other area will be set automatically. If this behaviour is not desired, set `.frame_factor=None`
        """
        return self._collector_area

    @collector_area.setter
    def collector_area(self, area: Real) -> None:
        area = float(area)
        if area < 0:
            raise ValueError("`area` should be positive, is %s", area)
        self._collector_area = area
        if not self._frame_factor is None:
            self._total_area = self._collector_area / self._frame_factor
    
    @property
    def frame_factor(self) -> float|None:
        """
        The ratio of collector area to total area

        If setting the frame_factor, then the collector area will be automatically recalculated from the total area.
        """
        return self._frame_factor
    
    @frame_factor.setter
    def frame_factor(self, factor:float|None) -> None:
        if not factor is None:
            if factor > 1.0 or factor < 0.0:
                raise ValueError("`factor` must be in range [0,1] (or `None`), is %s", factor)
        self._frame_factor = factor
        # Reset total area to force recalculation of collector area
        self.total_area = self._total_area

    @property
    def location(self) -> location.AspectLocation:
        return self._location

    @location.setter
    def location(self, loc: location.Location) -> None:
        if isinstance(loc, location.AspectLocation):
            self._location = location.AspectLocation(loc)
        else:
            az = self._location.azimuth
            pt = self._location.pitch
            
            if isinstance(loc, location.RaisedLocation):
                self._location = location.AspectLocation(loc)
            else:
                ht = self._location.height_agl
                self._location = location.AspectLocation(loc)
                self._location.height_agl = ht
                        
            self._location.azimuth = az
            self._location.pitch = pt

    @classmethod
    def from_characteristics(
        cls: Type[T],
        peak_power: Real,
        loc: location.AspectLocation | None = None,
        total_area: Real | None = None,
        collector_area: Real | None = None,
        frame_factor: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> T:
        
        a = locals()
        del a['cls']
        del a['peak_power']
        return cls(
            peak_power, # pyright: ignore[reportCallIssue]
            **a
        )
    
    @override
    def to_dict(self) -> dict[str, Any]:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'peak_power': self._peak_power,
            'loc': self._location.to_dict(),
            'total_area': self._total_area,
            'collector_area': self._collector_area,
            'frame_factor': self._frame_factor,
        }

        return odict
    
    @override
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        config = copy.copy(config)

        loc = config.pop('loc', None)
        if loc is not None:
            if isinstance(loc, dict):
                loc = location.location_from_dict(loc)
            self.location = loc
        
        # This looks risky, but practically may only result in
        # some redundant attributes if the config is bad.
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

    @classmethod
    def from_dict(
        cls: Type[ABCPVElecGenerator],
        config: dict[str, Any]
    ) -> ABCPVElecGenerator:
        ip = copy.copy(config)
        ip.pop('class', None)
        if ip.get('loc', None) is not None:
            ip['loc'] = location.location_from_dict(ip['loc'])
        return cls.from_characteristics(**ip)

# ABCPVElecGenerator copy constructor
@ABCPVElecGenerator.__init__.register(ABCPVElecGenerator) # pyright: ignore[reportFunctionMemberAccess]
def ABCPVElecGenerator_from_other(
    self,
    other: ABCPVElecGenerator
) -> None:
    self._peak_power = other.peak_power
    self._location = copy.copy(other.location)
    self._total_area = other.total_area
    self._collector_area = other.collector_area
    self._frame_factor = other.frame_factor
    self._name = other.name
    try:
        self._model = other.model
    except AttributeError:
        pass

##### Fully deprecated ####
# class SprakePVElecGenerator(ABCPVElecGenerator):
#     _name = "Simple PV Panel"

#     @override
#     def __init__( # pyright: ignore[reportIncompatibleVariableOverride]
#         self,
#         other:SprakePVElecGenerator|None = None
#     ) -> None:
#         super().__init__(other)
#         if other is None:
#             self._self_consumption = 0.04
#             self._aspect_factor = 0.7
#         elif isinstance(other, SprakePVElecGenerator):
#             self._self_consumption = other.self_consumption
#             self._aspect_factor = other.aspect_factor
#         else:
#             raise ValueError("'other' must be a SprakePVElecGenerator")

#     @property
#     def self_consumption(self) -> float:
#         """
#         The maximum self-consumption of the module or array in kW. 

#         In the Sprake model, this is taken from mean production rate over the timestep. If the result is < 0, then it is clipped to 0
#         """
#         return self._self_consumption

#     @self_consumption.setter
#     def self_consumption(self, self_consumption_kw:int|float) -> None:
#         if self_consumption_kw < 0:
#             warnings.warn("Self consumption is defined positive - negative implies baseline generation without solar resource")
#         if self_consumption_kw > self._peak_power:
#             warnings.warn("Self-consumption greater than peak power under STC. Have you checked units?")
#         self._self_consumption = self_consumption_kw
    
#     @property
#     def aspect_factor(self) -> float:
#         """
#         The Sprake model reduces production at all times by a factor reflecting the reduction from total horizontal radiation received by collectors due to pitch and azimuth of collectors.

#         This simple model does not vary this loss by the actual solar position and the azimuth and pitch of the array
#         """
#         return self._aspect_factor

#     @aspect_factor.setter
#     def aspect_factor(self, factor:float) -> None:
#         assert factor >= 0.0, "`factor` should be positive."
#         if factor > 1.0:
#             warnings.warn("Setting `factor` > 1 implies some form of concentrating technology is in use.")
#         self._aspect_factor = factor

#     def run(
#         self,
#         timespan: modtimespan.TimeSpan
#     ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
#         if self.model is None:
#             raise ValueError("Electrical generator requires a model to serve environmental data")
#         global_horizontal_flux = self.model.local_env.get_horizontal_solar_flux(self.location, timespan)
#         # Scale flux to collector area
#         # NB - in Sprake model, the aspect factor does not get applied until after the removal of
#         # self-consumption. This is counter-intuitive, and we have reversed it here
#         collector_flux = global_horizontal_flux * self.collector_area * self.aspect_factor - self.self_consumption
#         collector_flux = np.asarray(collector_flux)
        
#         # Apply assumption of no consumption when under low irradiation
#         collector_flux[collector_flux<0.0] = 0.0

#         return collector_flux.reshape((1,-1))
#
#    @classmethod
#    def from_characteristics(
#        cls: Type[SprakePVElecGenerator],
#        *args,
#        self_consumption:float,
#        aspect_factor:float,
#        **kwargs
#    ) -> SprakePVElecGenerator:
#
#        o = super(SprakePVElecGenerator, cls).from_characteristics(*args, **kwargs)
#
#        o.self_consumption = self_consumption
#        o.aspect_factor = aspect_factor
#
#        return o
#    
#    def to_dict(self) -> dict[str, Any]:
#        odict = super().to_dict()
#        odict['self_consumption'] = self._self_consumption
#        odict['aspect_factor'] = self._aspect_factor
#
#        return odict

class SprakePVGISElecGenerator(ABCPVElecGenerator):
    """
    An alternative Sprake PV generator for enhanced generation modelling.

    Matches up with the "enhance_gen" version of the excel model
    """
    _name = "Reduced PVGIS modelled panel"

    @singledispatchmethod
    def __init__(
        self,
        peak_power: Real | SprakePVGISElecGenerator,
        dc_efficiency: Real = 0.98,
        inverter_efficiency: Real = 0.96,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        """
        Default assumes None
        """
        raise ValueError('First argument must be a numeric peak power (STC) or a SprakePVGISElecGenerator, is %s', type(peak_power))

    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(Real)
    def _from_Real(
        self,
        peak_power: Real,
        dc_efficiency: Real = 0.98,
        inverter_efficiency: Real = 0.96,
        **kwargs
    ) -> None:
        from config import settings

        super().__init__(peak_power, **kwargs)

        # As the Sprake model insolation is pinned to a single location,
        # we set this to a constant
        self.location = location.AspectLocation(
                settings.get('SprakeValidationLat'),
                settings.get('SprakeValidationLon'),
                azimuth = 180.,
                pitch = 35.
            )
        
        self._dc_efficiency = float(dc_efficiency)
        self._inverter_efficiency = float(inverter_efficiency)
    
    @classmethod
    def from_none(cls) -> SprakePVGISElecGenerator:
        return cls(1.0)
        
    def _set_pvlib_location(self):
        self._pvlib_location = pvlib.location.Location(
            self._location.lat,
            self._location.lon
        )

    def _set_module_parameters(self):
        self._module_parameters = {
            'pdc0': self.peak_power,
            'cell_type': 'csi',
            'a_r': 0.16 # Martin-Ruiz AOI modifier parameter
        }

    def _set_temperature_model_parameters(self):
        # NB - this temperature model is not actually used for DC output, 
        # but corresponds to the Faiman model.
        self._temperature_model_parameters = {
            'u0': 20.0, # c-Si Roof added or building integrated https://joint-research-centre.ec.europa.eu/photovoltaic-geographical-information-system-pvgis/getting-started-pvgis/pvgis-data-sources-calculation-methods_en#references
            'u1': 3.2
        }

    def _set_losses_parameters(self):
        self._losses_parameters = {
            'dc_efficiency': self._dc_efficiency
        }

    def _set_inverter_parameters(self):
        self._inverter_parameters = {
            'pdc0': self.peak_power,
            'eta_inv_nom': self._inverter_efficiency
        }

    def _create_system(self):
        self._system = pvlib.pvsystem.PVSystem(
            surface_tilt = int(self.location.pitch),
            surface_azimuth = int(self.location.azimuth),
            module_parameters = self._module_parameters,
            temperature_model_parameters = self._temperature_model_parameters,
            losses_parameters = self._losses_parameters,
            inverter_parameters = self._inverter_parameters
        )

    def _create_modelchain(self):
        import core.generation.generation_utils as generation_utils

        self._mc = pvlib.modelchain.ModelChain(
            self._system,
            self._pvlib_location,
            transposition_model = 'isotropic',
            aoi_model = 'martin_ruiz',
            spectral_model = 'no_loss',
            temperature_model = 'faiman',
            dc_model = generation_utils.huld_dcmodel_wrapper,
            losses_model = generation_utils.fixed_percent_dc_loss, # pyright: ignore[reportArgumentType]
            ac_model = 'pvwatts'
        )

    @property
    def dc_efficiency(self) -> float:
        return self._dc_efficiency
    
    @dc_efficiency.setter
    def dc_efficiency(self, eta: float ) -> None:
        self._dc_efficiency = eta
    
    @property
    def inverter_efficiency(self) -> float:
        return self._inverter_efficiency
    
    @inverter_efficiency.setter
    def inverter_efficiency(self, eta: float) -> None:
        self._inverter_efficiency = eta
    
    def run(
        self,
        timespan: modtimespan.TimeSpan
    ) -> np.ndarray[tuple[int, int], np.dtype[np.float64]]:

        if self.model is None:
            raise ValueError("Electrical generator requires a model to serve environmental data")
        
        global_horizontal_flux = (
            self.model.local_env.get_horizontal_solar_flux(
                self.location,
                timespan
            )
        )
        temp_air = (
            self.model.local_env.get_external_temperature(
                self.location,
                timespan
            )
        )
        wind_speed = (
            self.model.local_env.get_wind_speeds(
                self.location,
                timespan
            )
        )

        rad_times = self.model.local_env.get_true_datetimes(
            'horizontal_solar_flux',
            self.location,
            timespan
        )
        # This is a kludge to estimate solar position. Suffers particularly around sunrise/sunset.
        rad_times_centered = (
            rad_times - self.model.local_env.get_horizontal_solar_flux_timestep() / 2
        )

        self._set_pvlib_location()

        solarpos = cast(
            pd.DataFrame,
            self._pvlib_location.get_solarposition(rad_times_centered)
        )

        radiation_components = cast(
            pd.DataFrame,
            (
                pvlib.irradiance.erbs(
                    global_horizontal_flux,
                    solarpos['zenith'].values,
                    rad_times_centered # for extraterrestrial radiation
                )
            )
        )

        weather = (
            pd.DataFrame(
                dict(
                    ghi = global_horizontal_flux,
                    temp_air = temp_air,
                    wind_speed = wind_speed,
                    time = rad_times_centered
                )
            )
            .set_index('time')
            .join(radiation_components.loc[:, ['dni', 'dhi']])
            .assign(albedo = 0.25)
        )

        self._set_module_parameters()
        self._set_temperature_model_parameters()
        self._set_losses_parameters()
        self._set_inverter_parameters()
        self._create_system()
        self._create_modelchain()

        self._mc.run_model(weather)

        if self._mc.results.ac is None:
            raise ValueError('Model chain results have not been assigned')
        generation = np.asarray(self._mc.results.ac.values).reshape((1,-1))
        
        # No energy in first pseudo-timestep
        generation[:,0] = 0.0

        return generation
    
    @classmethod
    def from_characteristics(
        cls,
        peak_power: Real,
        loc: location.AspectLocation | None = None,
        total_area: Real | None = None,
        collector_area: Real | None = None,
        frame_factor: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None,
        dc_efficiency: Real | None = None,
        inverter_efficiency: Real | None = None
    ) -> SprakePVGISElecGenerator:

        # Because the super .from_characteristics classmethod dispatches
        # based on the actual class, the resultant ._from_Real init
        # method will be the local one and so it will not recognise all
        # arguments; i.e. the below pattern will not work
        #
        # a = locals()
        # del a['cls']
        # del a['__class__']
        # del a['dc_efficiency']
        # del a['inverter_efficiency']
        # o = super(SprakePVGISElecGenerator, cls).from_characteristics(**a)
        # o.dc_efficiency = dc_efficiency
        # o.inverter_efficiency = inverter_efficiency

        # Instead, we will use the sync method
        a = locals()
        del a['cls']
        o = cls.from_none()
        o.sync_with_dict(a)

        return o

    def to_dict(self) -> dict[str, Any]:
        odict = super().to_dict()
        odict['dc_efficiency'] = self._dc_efficiency
        odict['inverter_efficiency'] = self._inverter_efficiency

        return odict
    
    # sync_with_dict should inherit ok
    # from_dict should inherit ok

# SprakePVGISElecGenerator copy constructor
@SprakePVGISElecGenerator.__init__.register(SprakePVGISElecGenerator) # pyright: ignore[reportFunctionMemberAccess]
def SprakePVGISElecGenerator_from_other(
    self,
    other: SprakePVGISElecGenerator
) -> None:
    super(SprakePVGISElecGenerator, self).__init__(other) # pyright: ignore[reportCallIssue]
    self._dc_efficiency = other._dc_efficiency
    self._inverter_efficiency = other._inverter_efficiency

class PowerPlantHomogeneousPV(ABCScalingPowerPlant):
    """
    A power plant consisting of a Real of identical PV modules.

    The Real of modules may be non-integer, and all are at a single nominal
    location and aspect and pitch, and do not self-shadow.
    """
    _name = "Solar PV Array"
    
    @singledispatchmethod
    def __init__(
        self,
        pv_array: ABCPVElecGenerator | PowerPlantHomogeneousPV,
        loc: location.Location | None = None,
        n: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        raise ValueError('First argument must be an ABCPVElecGenerator or PowerPlantHomogeneousPV, is %s', type(pv_array))

    # Copy constructor is registered underneath class definition for late-bind
    @__init__.register(ABCPVElecGenerator)
    def _from_ABCPVElecGenerator(
        self,
        pv_array: ABCPVElecGenerator,
        loc: location.Location | None = None,
        n: Real | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None
    ) -> None:
        # Take a copy of the pv array, primarily to ensure that
        # changing its location does not break its parent
        self._pv_array = copy.deepcopy(pv_array)
        if loc is not None:
            self._pv_array.location = loc
        
        self._n = float(n) if n is not None else 1.

        if name is not None:
            self._name = name
        
        if model is not None:
            # Go via property to push this to pv array
            self.model = model
    
    @classmethod
    def from_none(cls) -> PowerPlantHomogeneousPV:
        return cls(SprakePVGISElecGenerator.from_none())
    
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, name):
        self._name = name

    @property
    def model(self) -> environmentserverinterface.EnvironmentServerIntrface:
        """
        The NewSEGS Model for environmental data.

        This is stored within the pv array instance to maintain sync and so
        cannot be accessed prior to a pv array being assigned.
        """
        return self.pv_array.model
    
    @model.setter
    def model(self, model: environmentserverinterface.EnvironmentServerIntrface) -> None:
        self._pv_array.model = model

    @property
    def location(self) -> location.AspectLocation:
        return self.pv_array.location
    
    @location.setter
    def location(self, loc: location.Location) -> None:
        self.pv_array.location = loc
    
    @property
    def pv_array(self) -> ABCPVElecGenerator:
        if self._pv_array is None:
            raise AttributeError('pv_array has not been set')
        return self._pv_array
    
    @pv_array.setter
    def pv_array(self, pv_array: ABCPVElecGenerator) -> None:
        try:
            loc = self.pv_array.location
        except AttributeError:
            loc = None
        try:
            mdl = self.pv_array.model
        except AttributeError:
            mdl = None
        else:
            loc = None
            mdl = None
        
        self._pv_array = copy.deepcopy(pv_array)

        if loc is not None:
            self._pv_array.location = loc
        if mdl is not None:
            self._pv_array.model = mdl

    @property
    def n_arrays(self) -> float:
        return self._n

    @n_arrays.setter
    def n_arrays(self, n: Real) -> None:
        n = float(n)
        if n < 0:
            raise ValueError("Real of PV arrays must be positive, is %s", n)
        self._n = n

    @property
    def nameplate_capacity(self):
        return self.pv_array.nameplate_capacity * self._n

    @override
    def set_nameplate_capacity(self, nameplate_capacity: Real) -> None:
        """
        Alter the number of generators to match the required capacity.
        """
        n_array = float(nameplate_capacity) / self.pv_array.nameplate_capacity
        self.n = n_array
    
    @property
    def total_area(self):
        return self.pv_array.total_area * self._n
    
    @property
    def collector_area(self):
        return self.pv_array.collector_area * self._n

    def run(
        self,
        timespan: modtimespan.TimeSpan
    ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        return self.n * self.pv_array.run(timespan)

    @classmethod
    def from_characteristics(
        cls,
        pv_array: ABCPVElecGenerator,
        n: Real,
        loc: location.AspectLocation | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None,
    ) -> PowerPlantHomogeneousPV:

        a = locals()
        del a['cls']
        del a['pv_array']#

        return cls(
            pv_array,
            **a
        )
    
    @override
    def to_dict(self) -> Mapping:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'pv_array': self._pv_array.to_dict(),
            'n': self._n
        }

        return odict

    @override
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        config = copy.copy(config)
        pv_array = config.pop('pv_array', None)
        if pv_array is not None:
            if isinstance(pv_array, dict):
                pv_array = generator_from_dict(pv_array)
                if not isinstance(pv_array, ABCPVElecGenerator):
                    raise TypeError(f'`pv_array is not of type ABCPVElecGenerator, is {type(pv_array)}')
            self._pv_array = pv_array
            # Expect the location to get overwritten in the setter;
            # as this is recovery, we do actually want the location
            # though we don't want to mess with the model.
            self.location = pv_array.location
        
        # This looks risky, but practically may only result in
        # some redundant attributes if the config is bad.
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

    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> PowerPlantHomogeneousPV:
        ip = copy.copy(config)
        ip.pop('class', None)

        if ip.get('pv_array', None) is not None:
            ip['pv_array'] = generator_from_dict(ip['pv_array'])
            if not isinstance(ip['pv_array'], ABCPVElecGenerator):
                raise TypeError(f'`pv_array is not of type ABCPVElecGenerator, is {type(ip['pv_array'])}')
        
        return cls.from_characteristics(**ip)

# PowerPlantHomogeneousPV copy constructor
@PowerPlantHomogeneousPV.__init__.register(PowerPlantHomogeneousPV) # pyright: ignore[reportFunctionMemberAccess]
def PowerPlantHomogeneousPV_from_other(
    self,
    other: PowerPlantHomogeneousPV
) -> None:
    self._pv_array = copy.deepcopy(other.pv_array)
    self.n = other.n
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

class PowerPlantHeterogeneousGenerators(ABCElecGenerator):
    """
    A power plant consisting of a Real of different generator types, locations, aspects etc
    """
    _name = "Site power plant"
    
    @singledispatchmethod
    def __init__(
        self,
        generators: Collection[ABCScalingPowerPlant] | PowerPlantHeterogeneousGenerators,
        loc: location.Location | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None,
        do_copy: bool = True
    ) -> None:
        raise ValueError('First argument must be a collection of `ABCElecGenerator`s or a PowerPlantHeterogeneousGenerators, is %s', type(generators))

    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(Collection)
    def _from_collection(
        self,
        generators: Collection[ABCScalingPowerPlant],
        loc: location.Location | None = None,
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None,
        do_copy: bool = True,
    ) -> None:
        if do_copy:
            self._generators = [copy.deepcopy(gen) for gen in generators]
        else:
            self._generators = [gen for gen in generators]
        
        if loc is not None:
            # How we deal with the location is a strong decision
            self.location = loc
        
        if name is not None:
            self._name = name
        
        if model is not None:
            self.model = model
    
    @classmethod
    def from_none(cls) -> PowerPlantHeterogeneousGenerators:
        return cls([
            PowerPlantHomogeneousWind.from_none(),
            PowerPlantHomogeneousPV.from_none(),
        ])
        
    @property
    def model(self) -> environmentserverinterface.EnvironmentServerIntrface:
        return self._generators[0].model

    @model.setter
    def model(self, model: environmentserverinterface.EnvironmentServerIntrface) -> None:
        for generator in self.generators:
            generator.model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def generators(self) -> list[ABCScalingPowerPlant]:
        return self._generators
    
    def append(self, generator: ABCScalingPowerPlant) -> None:
        try:
            gen_model = generator.model
        except AttributeError:
            gen_model = None

        if gen_model is None and self.generators:
            try:
                generator.model = self.generators[0].model
            except AttributeError:
                pass
        self._generators.append(generator)
    
    def clear(self) -> None:
        self._generators.clear()

    def extend(
            self, 
            other: PowerPlantHeterogeneousGenerators | Iterable[ABCScalingPowerPlant]
        ) -> None:
        if isinstance(other, PowerPlantHeterogeneousGenerators):
            for gen in other.generators:
                self.append(gen)
        else:
            for gen in other:
                self.append(gen)
    
    def insert(self, index: int, generator: ABCScalingPowerPlant) -> None:
        if generator.model is None and self.generators:
            generator.model = self.generators[0].model
        self._generators.insert(index, generator)
    
    def pop(self, index:int=-1) -> ABCElecGenerator:
        return self._generators.pop(index)

    def __len__(self):
        return len(self._generators)

    def set_n(self, n: npt.ArrayLike):
        n = np.asarray(n).flatten()
        if len(n) != len(self):
            raise ValueError("`n` should be same length as `.generators`")
        for i, n_value in enumerate(n):
            self._generators[i].n = n_value
    
    def run(
        self,
        timespan: modtimespan.TimeSpan
    ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        # Verify that all are using the same model
        self.model = self._generators[0].model

        olist = [x.run(timespan) for x in self._generators]
        return np.array(olist).reshape((len(self._generators),-1))

    @classmethod
    def from_characteristics(
        cls,
        generators: list[ABCScalingPowerPlant],
        name: str | None = None,
        model: environmentserverinterface.EnvironmentServerIntrface | None = None,
    ) -> PowerPlantHeterogeneousGenerators:
        a = locals()
        del a['cls']
        del a['generators']

        return cls(
            generators,
            **a
        )

    @override
    def to_dict(self) -> dict[str, Any]:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'generators': [x.to_dict() for x in self.generators]
        }
        return odict
    
    @override
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        config = copy.copy(config)
        generators = config.pop('generators', None)
        if generators is not None:
            try:
                mdl = self.model
            except AttributeError:
                mdl = None

            generators = [
                x if isinstance(x, ABCScalingPowerPlant) else generator_from_dict(x) for x in generators
            ]
            for x in generators:
                if not isinstance(x, ABCScalingPowerPlant):
                    raise TypeError(f'configuration contains generators of incorrect type: {type(x)}')
            generators = [
                cast(ABCScalingPowerPlant, x) for x in generators
            ]
            self.clear()
            self.extend(generators)
            # Sync up the model
            if mdl is not None:
                self.model = mdl
            # Note that the location is not synchronised for this type of generator
        
        # This looks risky, but practically may only result in
        # some redundant attributes if the config is bad.
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
    
    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> PowerPlantHeterogeneousGenerators:
        ip = copy.copy(config)
        ip.pop('class', None)

        if ip.get('generators', None) is not None:
            ip['generators'] = [generator_from_dict(x) for x in ip['generators']]
        
        return cls.from_characteristics(**ip)

    @property
    def location(self) -> location.Location:
        if self._generators is None:
            raise AttributeError('No generators have been added')
        
        return location.Location(self._generators[0].location)
    
    @location.setter
    def location(self, loc: location.Location):
        loc = location.Location(loc) # Drop any height or aspect information in this generic setter
        for gen in self.generators:
            gen.location = loc

    @property
    def nameplate_capacity(self):
        cap = 0
        for gen in self._generators:
            cap += gen.nameplate_capacity
        return cap

# PowerPlantHeterogeneousGenerators copy constructor
@PowerPlantHeterogeneousGenerators.__init__.register(PowerPlantHeterogeneousGenerators) # pyright: ignore[reportFunctionMemberAccess]
def PowerPlantHeterogeneousGenerators_from_other(
    self,
    other: PowerPlantHeterogeneousGenerators
) -> None:
    self._generators = copy.deepcopy(other.generators)
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

GENERATOR_CONSTRUCTORS = {
    'WindTurbineElecGenerator': WindTurbineElecGenerator,
    'PowerPlantHomogeneousWind': PowerPlantHomogeneousWind,
    'SprakePVGISElecGenerator': SprakePVGISElecGenerator,
    'PowerPlantHomogeneousPV': PowerPlantHomogeneousPV,
    'PowerPlantHeterogeneousGenerators': PowerPlantHeterogeneousGenerators,
}

def generator_from_dict(ip: dict[str, Any]) -> ABCElecGenerator:
    ip = copy.copy(ip)
    classname = ip.pop('class')
    if classname is None:
        raise ValueError(f'`class` not found in configuration dictionary with keys: {ip.keys()}')
    constructor = GENERATOR_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError(f'Constructor not found for {classname}')
    return constructor.from_dict(ip)
