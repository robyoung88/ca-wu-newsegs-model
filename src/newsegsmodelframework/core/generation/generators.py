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

import copy
from dataclasses import asdict, field
import json
from typing import Any, Optional, SupportsIndex
import warnings
from abc import ABCMeta, abstractmethod
from collections.abc import Callable, Collection, Iterable
from typing import cast, override, SupportsFloat, Type, TypeVar
from functools import singledispatchmethod

import numpy as np
import numpy.typing as npt
import pandas as pd
import pvlib

from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core import SerialiseToDictMixin, newsegscomponent
from newsegsmodelframework.core import serialisation
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.core import location
from newsegsmodelframework.core.newsegsmodule import NewsegsModule
from newsegsmodelframework.core.serialisedtrackeddata import SerialisedConfigurationMixin
from newsegsmodelframework.core.trackeddata import ConfigurationMixin, DataWithRevision, ObservableList, RevisionNotifierMixin, revision_dataclass
from newsegsmodelframework.util import jsonfuncs

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

@revision_dataclass
class ABCElecGeneratorConfig(DataWithRevision):
    location: location.Location = field(default_factory = location.Location.from_none)


class ABCElecGenerator(
    SerialisedConfigurationMixin,
    metaclass = ABCMeta
):
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
    _name: str = 'Generator'
    _model: NewsegsModelInterface

    _constructor_class = 'Generator'

    @override
    def _generate_config(self, *args, **kwargs) -> ABCElecGeneratorConfig:
        return ABCElecGeneratorConfig(*args, **kwargs)

    def __init__(
        self, 
        *args, 
        name: Optional[str] = None,
        model: Optional[NewsegsModelInterface] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        if name:
            self.name = name
        if model:
            self.model = model

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
    def name(self) -> str:
        """
        A friendly string identifier for the configuration.

        Not strictly unique, but used for identification of stored configurations.
        """
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def model(self) -> NewsegsModelInterface: 
        """
        The callback NewsegsModel model associated with the generator.
        """
        if self._model is None:
            raise AttributeError('model has not been set')
        return self._model

    @model.setter
    def model(self, model: NewsegsModelInterface):
        self._model = model

    @property
    @abstractmethod
    def nameplate_capacity(self) -> float:
        """
        The total nameplate capacity in kW.
        """

    @classmethod
    @override
    def from_dict(cls, config):
        config = config.copy()
        #cfg = config.pop('_config', None)
        inst = cls.__new__(cls)
        inst._config = inst._generate_config()
        inst.update(config)
        #if cfg:
        #    for k, v in cfg.items():
        #        setattr(inst, k, v)
        return inst

ABCElecGenerator._excluded_attributes = super(ABCElecGenerator,ABCElecGenerator)._excluded_attributes + ('_model',)


class NewsegsGeneratorProperty(newsegscomponent.ComponentProperty):
    """Assign a property as a generator, so that it is assigned the current model on attachment."""
    @override
    def __set__(self, instance: ConfigurationMixin, value: ConfigurationMixin):
        if not isinstance(instance, (NewsegsModule, ABCElecGenerator)):
            raise TypeError(f'Property accessing {self.name} should only be applied to a NewsegsModule, is attribute of {type(instance)}')
        if not isinstance(value, ABCElecGenerator):
            raise TypeError(f'Property assigned to {self.name} should be an ABCElecGenerator, is {type(value)}')

        current_model = getattr(instance, 'model', None)
        super().__set__(instance, value)

        if current_model:
            getattr(instance, self.name).model = current_model


@revision_dataclass
class ABCScalingPowerPlantConfig(ABCElecGeneratorConfig):
    n: float = 1.


class ABCScalingPowerPlant(ABCElecGenerator):
    """
    Represents a power plant of homogeneous generating units
    """
    _name = 'Power plant'

    @override
    def _generate_config(self, *args, **kwargs) -> ABCScalingPowerPlantConfig:
        return ABCScalingPowerPlantConfig(*args, **kwargs)

    @abstractmethod
    def set_nameplate_capacity(self, nameplate_capacity: Real) -> None:
        """
        Alter the Real of generating units to match the desired nameplate capacity
        """


_wteg_default_cp_curve = np.asarray(
    [
        [0,  3,  5,   10, 25, 26, 50],
        [0.0,0.0,0.25,0.4,0.1,0.0,0.0]
    ]
).reshape((2,-1))


@revision_dataclass
class WindTurbineElecGeneratorConfig(ABCElecGeneratorConfig):
    location: location.RaisedLocation = field(default_factory = location.RaisedLocation.from_none) # pyright: ignore[reportIncompatibleVariableOverride]
    
    default_cp_curve: np.ndarray = field(default_factory = lambda: copy.copy(_wteg_default_cp_curve))
    cut_in: float = 0.
    """Mean wind speed (m/s) below which no output (not enforced in Cp)."""
    cut_out: float = 50.
    """Mean wind speed (m/s) above which no output (not enforced in Cp)."""
    rated_power: float = 0.245
    """Alternative name for nameplate_capacity (kW)."""
    swept_area: float = 1.
    """Area (m²) swept by blades, used in combination with Cp curve for power output."""
    hub_height: float = 10.
    """Height of rotor centre (m) for environmental data access."""
    cp: Callable = field(default_factory = lambda: _cp_interpolant_factory(_wteg_default_cp_curve))
    """Function taking axial wind speeds and returning Cp.
    
    It is not recommended to set this directly - use set_cp_curve
    """
    _cp_curve: np.ndarray = field(default_factory = lambda: copy.copy(_wteg_default_cp_curve))

    _excluded_attributes = ('cp',)
    
    @override
    def json_dumps(self) -> str:
        return json.dumps(self.to_dict(), cls = jsonfuncs.NumpyEncoder)

    @override
    def update(self, config: dict[str, Any] | type[serialisation.T]):
        super().update(config)
        if isinstance(config, dict) and '_cp_curve' in config.keys():
            self.set_cp_curve(np.asarray(self._cp_curve))

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
        self.cp = _cp_interpolant_factory(cp_curve)

    def set_power_curve(
        self,
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

    def __getstate__(self):
        """
        State for pickling.
        """
        odict = self.__dict__.copy()
        odict.pop('cp', None)
        return odict

    def __setstate__(self, state):
        """
        Set the state of a new instance - for unpickling.

        Essentially copies over the state to the __dict__ then
        forces creation of the _cp_func.
        """
        vars(self).update(state)
        self.set_cp_curve(self._cp_curve)


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

    _name = "Wind Turbine"

    @override
    def _generate_config(self, *args, **kwargs) -> WindTurbineElecGeneratorConfig:
        return WindTurbineElecGeneratorConfig(*args, **kwargs)

    _config: WindTurbineElecGeneratorConfig # pyright: ignore[reportIncompatibleVariableOverride]

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]] | WindTurbineElecGenerator,
        *args,
        **kwargs
    ) -> None:
        """
        Default assumes None
        """
        raise ValueError('First argument must be a cp curve or a WindTurbineElecGenerator, is %s', type(dispatch_arg))

    # Copy constructor is registered underneath class definition for late-bind.
    @__init__.register(np.ndarray)
    def _from_cp_curve(
        self,
        cp_curve: np.ndarray[tuple[int,int], np.dtype[np.floating[Any]]],
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.set_cp_curve(cp_curve)
        # Set hub_height through property to ensure that location is also set
    
    @classmethod
    def from_none(cls) -> WindTurbineElecGenerator:
        return cls(_wteg_default_cp_curve)

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
    def rotor_diameter(self) -> float:
        """
        Alternative accessor for swept_area. Diameter (m) of swept circle.

        Note that for a coned rotor, this diameter is less than the length of
        the blade plus half the diameter of the hub. Use the diameter used in
        Cp calculation.
        """
        return 2.0 * np.sqrt(self.swept_area) / np.pi

    @rotor_diameter.setter
    def rotor_diameter(self, diameter: Real) -> None:
        self.swept_area = np.pi * (0.5 * float(diameter)) ** 2

    @property
    def hub_height(self) -> float:
        """
        Height of rotor centre (m) for environmental data access.
        """
        return self._config.hub_height

    @hub_height.setter
    def hub_height(self, height: Real) -> None:
        self._config.hub_height = float(height)
        try:
            self.location.height_agl = self._config.hub_height
        except AttributeError:
            pass

    @property
    def location(self) -> location.RaisedLocation:
        return self._config.location

    @location.setter
    def location(self, loc: location.Location) -> None:
        if (
            isinstance(loc, location.RaisedLocation)
            and loc.height_agl != self.hub_height
        ):
            warnings.warn(('Provided location includes a height unequal to '
                           'hub, and will be ignored.'),
                          UserWarning)

        self._config.location = location.RaisedLocation(loc)
        self._config.location.height_agl = self.hub_height

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
        return self._config.set_cp_curve(cp_curve)

    def set_power_curve(
        self,
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
        return self._config.set_power_curve(power_curve, air_density)

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
        power = (0.5 * air_density * self.swept_area * self.cp(wind_speeds) # pyright: ignore[reportOperatorIssue]
                 * wind_speeds**3) / 1000.0

        deltatime = lenvs.get_wind_timestep().seconds * modtimespan.SECONDS_TO_HOURS

        # Assumption: returned timeseries is regular and indexed to the wind
        # speed times
        energy = power * deltatime

        # First time has no preceding interval
        energy[0] = 0.0 # pyright: ignore[reportIndexIssue]

        return energy.reshape((1,-1)) # pyright: ignore[reportReturnType, reportAttributeAccessIssue]

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
    
    _excluded_attributes = ('_model',)

    @override
    def json_dumps(self) -> str:
        return json.dumps(self.to_dict(), cls = jsonfuncs.NumpyEncoder)

# WindTurbineElecGenerator copy constructor
@WindTurbineElecGenerator.__init__.register(WindTurbineElecGenerator) # pyright: ignore[reportFunctionMemberAccess]
def WindTurbineElecGenerator_from_other(
    self,
    other: WindTurbineElecGenerator
) -> None:
    super(WindTurbineElecGenerator, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys():
        if not k in ('cp'):
            setattr(self, k, copy.copy(getattr(other, k)))

    self.set_cp_curve(self._config._cp_curve)


class NewsegsWTGeneratorProperty(NewsegsGeneratorProperty):
    """Assign a property as a WT generator, so that model and location are inherited."""
    @override
    def __set__(self, instance: ConfigurationMixin, value: ConfigurationMixin):
        if not isinstance(instance, (NewsegsModule, ABCElecGenerator)):
            raise TypeError(f'Property accessing {self.name} should only be applied to a NewsegsModule or ABCElecGenerator, is attribute of {type(instance)}')
        if not isinstance(value, ABCElecGenerator):
            raise TypeError(f'Property assigned to {self.name} should be an ABCElecGenerator, is {type(value)}')

        current_location = getattr(instance, 'location', None)
        # Model is handled by NewsegsGeneratorProperty
        super().__set__(instance, copy.deepcopy(value))

        if current_location:
            getattr(instance, self.name).location = current_location


@revision_dataclass
class PowerPlantHomogeneousWindConfig(ABCScalingPowerPlantConfig):
    ...


class PowerPlantHomogeneousWind(ABCScalingPowerPlant):
    """
    A power plant consisting of a Real of identical wind turbines.
    
    The Real of turbines may be non-integer, and all are at a single nominal
    location.
    """
    _name = "Wind Farm"

    @override
    def _generate_config(self, *args, **kwargs) -> PowerPlantHomogeneousWindConfig:
        return PowerPlantHomogeneousWindConfig(*args, **kwargs)
    _config: PowerPlantHomogeneousWindConfig # pyright: ignore[reportIncompatibleVariableOverride]

    turbine = NewsegsWTGeneratorProperty(
        default = None,
        oftype = WindTurbineElecGenerator
    )

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: WindTurbineElecGenerator | PowerPlantHomogeneousWind,
        *args,
        **kwargs
    ) -> None:
        raise ValueError('First argument must be a WindTurbineElecGenerator or PowerPlantHomogeneousWind, is %s', type(dispatch_arg))
    
    # Copy constructor is registered underneath class definition for late-bind
    @__init__.register(WindTurbineElecGenerator)
    def _from_WindTurbineElecGenerator(
        self,
        turbine: WindTurbineElecGenerator,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        # Take a copy of the turbine, primarily to ensure that
        # changing its location does not break its parent
        self.turbine = copy.deepcopy(turbine)
    
    @classmethod
    def from_none(cls) -> PowerPlantHomogeneousWind:
        return cls(WindTurbineElecGenerator.from_none())

    @property
    @override
    def model(self) -> NewsegsModelInterface:
        """
        The NewSEGS Model for environmental data.

        This is stored within the turbine instance to maintain sync and so
        cannot be accessed prior to a turbine being assigned.
        """
        try:
            return self.turbine.model
        except AttributeError:
            return super().model
    
    @model.setter
    @override
    def model(self, model: NewsegsModelInterface) -> None:
        try:
            self.turbine.model = model
        except AttributeError:
            pass
        model_setter = ABCScalingPowerPlant.model.fset
        assert model_setter is not None
        model_setter(self, model)
    
    @property
    def location(self) -> location.RaisedLocation:
        """
        The location of the power plant

        This is stored within the turbine instance to maintain sync and so
        cannot be accessed prior to a turbine being assigned.
        """
        try:
            return self.turbine.location
        except AttributeError:
            return super().location # pyright: ignore[reportAttributeAccessIssue]

    @location.setter
    def location(self, loc: location.Location) -> None:
        try:
            self.turbine.location = loc
        except AttributeError:
            pass
        try:
            super().location = loc # type: ignore
        except AttributeError:
            self._config.location = loc

    @property
    def n_turbines(self) -> float:
        return self.n

    @n_turbines.setter
    def n_turbines(self, n: Real) -> None:
        n = float(n)
        if n < 0:
            raise ValueError(f"Number of turbines must be positive, is {n}")
        self.n = n

    @property
    def nameplate_capacity(self):
        return self.turbine.rated_power * self.n

    @override
    def set_nameplate_capacity(self, nameplate_capacity: Real) -> None:
        """
        Alter the number of generators to match the required capacity.
        """
        n_turb = float(nameplate_capacity) / self.turbine.rated_power
        self.n = n_turb

    @property
    def swept_area(self):
        return self.turbine.swept_area * self.n
    
    def run(
            self, 
            timespan: modtimespan.TimeSpan
        ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        return self.n * self.turbine.run(timespan)

    @classmethod
    def from_characteristics(
        cls: Type['PowerPlantHomogeneousWind'],
        turbine: WindTurbineElecGenerator,
        n: Real,
        loc: location.RaisedLocation | None = None,
        name: str|None = None,
        model: NewsegsModelInterface | None = None,
    ) -> 'PowerPlantHomogeneousWind':
        a = locals()
        del a['cls']
        del a['turbine']

        return cls(turbine, **a)

# PowerPlantHomogeneousWind copy constructor
@PowerPlantHomogeneousWind.__init__.register(PowerPlantHomogeneousWind) # pyright: ignore[reportFunctionMemberAccess]
def PowerPlantHomogeneousWind_from_other(
    self,
    other: PowerPlantHomogeneousWind
) -> None:
    super(PowerPlantHomogeneousWind, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys():
        setattr(self, k, copy.copy(getattr(other, k)))

    self.turbine = other.turbine


def _default_pv_location():
    loc = location.AspectLocation.from_none()
    loc.azimuth = 180.
    loc.pitch = 35.
    return loc


@revision_dataclass
class ABCPVElecGeneratorConfig(ABCElecGeneratorConfig):
    location: location.AspectLocation = field(default_factory = _default_pv_location) # pyright: ignore[reportIncompatibleVariableOverride]

    peak_power: float = 1.0
    total_area: float = -1.0
    """
    The total area of the module or array in m², including frame

    When setting the total or collector area of the array, if a `.frame_factor` is defined, the other area will be set automatically. If this behaviour is not desired, set `.frame_factor=None`
    """
    collector_area: float = -1.0
    """
    The area of collector surface of the module or array in m²

    When setting the total or collector area of the array, if a `.frame_factor` is defined, the other area will be set automatically. If this behaviour is not desired, set `.frame_factor=None`
    """
    frame_factor: float = -1.0
    """
    The ratio of collector area to total area

    If setting the frame_factor, then the collector area will be automatically recalculated from the total area.
    """
    frame_factor_set: bool = field(init = False, default = False)

    def __post_init__(self):
        if self.frame_factor >= 0:
            self.frame_factor_set = True
        
        if self.total_area < 0:
            if self.frame_factor_set:
                if self.frame_factor > 0:
                    self.total_area = self.collector_area / self.frame_factor
                elif self.frame_factor == 0:
                    self.total_area = self.collector_area
            else:
                self.total_area = self.peak_power / 0.435
                if self.collector_area < 0:
                    self.collector_area = self.total_area
        else:
            if not self.frame_factor_set:
                self.frame_factor = 1.0
            
            self.collector_area = self.frame_factor * self.total_area

        if not self.frame_factor_set:
            if self.frame_factor < 0:
                self.frame_factor = self.collector_area / self.total_area


class ABCPVElecGenerator(ABCElecGenerator):
    """
    Abstract base class for all PV generation models
    """
    _name = "PV array"

    @override
    def _generate_config(self, *args, **kwargs) -> ABCPVElecGeneratorConfig:
        return ABCPVElecGeneratorConfig(*args, **kwargs)

    _config: ABCPVElecGeneratorConfig # pyright: ignore[reportIncompatibleVariableOverride]

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: Real | ABCPVElecGenerator,
        *args,
        **kwargs
    ) -> None:
        """
        Default assumes None
        """
        raise ValueError('First argument must be a numeric peak power (STC) or an ABCPVElecGenerator, is %s', type(dispatch_arg))

    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(Real)
    def _from_Real(
        self,
        peak_power: Real,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, peak_power = peak_power, **kwargs)

    @classmethod
    def from_none(cls) -> ABCPVElecGenerator:
        return cls(1.0)

    @property
    @override
    def nameplate_capacity(self) -> float:
        return self.peak_power

    @property
    def total_area(self) -> float:
        """
        The total area of the module or array in m², including frame

        When setting the total or collector area of the array, if a `.frame_factor` is defined, the other area will be set automatically. If this behaviour is not desired, set `.frame_factor=None`
        """
        return self._config.total_area

    @total_area.setter
    def total_area(self, area: Real) -> None:
        area = float(area)
        if area < 0:
            raise ValueError("`area` should be positive, is %s", area)
        self._config.total_area = area
        if self._config.frame_factor_set:
            self.collector_area = self._config.total_area * self._config.frame_factor

    @property
    def collector_area(self) -> float:
        """
        The area of collector surface of the module or array in m²

        When setting the total or collector area of the array, if a `.frame_factor` is defined, the other area will be set automatically. If this behaviour is not desired, set `.frame_factor=None`
        """
        return self._config.collector_area

    @collector_area.setter
    def collector_area(self, area: Real) -> None:
        area = float(area)
        if area < 0:
            raise ValueError("`area` should be positive, is %s", area)
        self._config.collector_area = area
        if self._config.frame_factor_set:
            self.total_area = self._config.collector_area / self._config.frame_factor
    
    @property
    def frame_factor(self) -> float|None:
        """
        The ratio of collector area to total area

        If setting the frame_factor, then the collector area will be automatically recalculated from the total area.
        """
        return self._config.frame_factor
    
    @frame_factor.setter
    def frame_factor(self, factor: float | None) -> None:
        if factor is None:
            self._config.frame_factor_set = False
            self._config.frame_factor = self._config.collector_area / self._config.total_area
        else:
            if factor > 1.0 or factor < 0.0:
                raise ValueError("`factor` must be in range [0,1] (or `None`), is %s", factor)
            self._config.frame_factor = factor
            self._config.frame_factor_set = True
            self._config.collector_area = self._config.total_area * factor

    @property
    def location(self) -> location.AspectLocation:
        return self._config.location

    @location.setter
    def location(self, loc: location.Location) -> None:
        if isinstance(loc, location.AspectLocation):
            newloc = location.AspectLocation(loc)
        else:
            l0 = self._config.location
            az = l0.azimuth
            pt = l0.pitch
            
            if isinstance(loc, location.RaisedLocation):
                newloc = location.AspectLocation(loc)
            else:
                ht = l0.height_agl
                newloc = location.AspectLocation(loc)
                newloc.height_agl = ht
                        
            newloc.azimuth = az
            newloc.pitch = pt
        self._config.location = newloc

    @classmethod
    def from_characteristics(
        cls: Type[T],
        peak_power: Real,
        loc: location.AspectLocation | None = None,
        total_area: Real | None = None,
        collector_area: Real | None = None,
        frame_factor: Real | None = None,
        name: str | None = None,
        model: NewsegsModelInterface | None = None
    ) -> T:
        
        a = locals()
        del a['cls']
        del a['peak_power']
        return cls(
            peak_power, # pyright: ignore[reportCallIssue]
            **a
        )

# ABCPVElecGenerator copy constructor
@ABCPVElecGenerator.__init__.register(ABCPVElecGenerator) # pyright: ignore[reportFunctionMemberAccess]
def ABCPVElecGenerator_from_other(
    self,
    other: ABCPVElecGenerator
) -> None:
    super(ABCPVElecGenerator, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys():
        if not k in ('cp'):
            setattr(self, k, copy.copy(getattr(other, k)))


@revision_dataclass
class SprakePVGISElecGeneratorConfig(ABCPVElecGeneratorConfig):
    dc_efficiency: float = 0.98
    inverter_efficiency: float = 0.96


class SprakePVGISElecGenerator(ABCPVElecGenerator):
    """
    An alternative Sprake PV generator for enhanced generation modelling.

    Matches up with the "enhance_gen" version of the excel model
    """
    _name = "Reduced PVGIS modelled panel"

    @override
    def _generate_config(self, *args, **kwargs) -> SprakePVGISElecGeneratorConfig:
        return SprakePVGISElecGeneratorConfig(*args, **kwargs)

    _config: SprakePVGISElecGeneratorConfig # pyright: ignore[reportIncompatibleVariableOverride]

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: Real | SprakePVGISElecGenerator,
        *args,
        **kwargs
    ) -> None:
        """
        Default assumes None
        """
        raise ValueError('First argument must be a numeric peak power (STC) or a SprakePVGISElecGenerator, is %s', type(dispatch_arg))

    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(Real)
    def _from_Real(
        self,
        peak_power: Real,
        *args,
        **kwargs
    ) -> None:
        from config import settings

        super().__init__(peak_power, *args, **kwargs)

        # As the Sprake model insolation is pinned to a single location,
        # we set this to a constant
        self.location = location.AspectLocation(
                settings.get('SprakeValidationLat'),
                settings.get('SprakeValidationLon'),
                azimuth = 180.,
                pitch = 35.
            )

    @classmethod
    def from_none(cls) -> SprakePVGISElecGenerator:
        return cls(1.0)
        
    def _set_pvlib_location(self):
        self._pvlib_location = location.PVLibLocation(
            self.location.lat,
            self.location.lon
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
            'dc_efficiency': self.dc_efficiency
        }

    def _set_inverter_parameters(self):
        self._inverter_parameters = {
            'pdc0': self.peak_power,
            'eta_inv_nom': self.inverter_efficiency
        }

    def _create_system(self):
        self._system = location.PVLibPVSystem(
            surface_tilt = int(self.location.pitch),
            surface_azimuth = int(self.location.azimuth),
            module_parameters = self._module_parameters,
            temperature_model_parameters = self._temperature_model_parameters,
            losses_parameters = self._losses_parameters,
            inverter_parameters = self._inverter_parameters
        )

    def _create_modelchain(self):
        import newsegsmodelframework.core.generation.generation_utils as generation_utils

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
        generation = np.asarray(self._mc.results.ac.values, copy = True).reshape((1,-1))
        
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
        model: NewsegsModelInterface | None = None,
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
        o.update(a)

        return o

SprakePVGISElecGenerator._excluded_attributes = tuple(super(SprakePVGISElecGenerator, SprakePVGISElecGenerator)._excluded_attributes) + (
    '_pvlib_location',
    '_module_parameters',
    '_temperature_module_parameters',
    '_losses_parameters',
    '_inverter_parameters',
    '_system',
    '_mc',

)

# SprakePVGISElecGenerator copy constructor
@SprakePVGISElecGenerator.__init__.register(SprakePVGISElecGenerator) # pyright: ignore[reportFunctionMemberAccess]
def SprakePVGISElecGenerator_from_other(
    self,
    other: SprakePVGISElecGenerator
) -> None:
    super(SprakePVGISElecGenerator, self).__init__(other) # pyright: ignore[reportCallIssue]
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys():
        if not k in ('cp'):
            setattr(self, k, copy.copy(getattr(other, k)))


class NewsegsPVGeneratorProperty(NewsegsGeneratorProperty):
    """Assign a property as a PV generator, so that model and location are inherited."""
    @override
    def __set__(self, instance: ConfigurationMixin, value: ConfigurationMixin):
        if not isinstance(instance, (NewsegsModule, ABCElecGenerator)):
            raise TypeError(f'Property accessing {self.name} should only be applied to a NewsegsModule or ABCElecGenerator, is attribute of {type(instance)}')
        if not isinstance(value, ABCElecGenerator):
            raise TypeError(f'Property assigned to {self.name} should be an ABCElecGenerator, is {type(value)}')

        current_location = getattr(instance, 'location', None)
        # Model is handled by NewsegsGeneratorProperty
        super().__set__(instance, copy.deepcopy(value))

        if current_location:
            getattr(instance, self.name).location = current_location


@revision_dataclass
class PowerPlantHomogeneousPVConfig(ABCScalingPowerPlantConfig):
    location: location.AspectLocation = field(default_factory = _default_pv_location) # pyright: ignore[reportIncompatibleVariableOverride]


class PowerPlantHomogeneousPV(ABCScalingPowerPlant):
    """
    A power plant consisting of a Real of identical PV modules.

    The Real of modules may be non-integer, and all are at a single nominal
    location and aspect and pitch, and do not self-shadow.
    """
    _name = "Solar PV Array"

    @override
    def _generate_config(self, *args, **kwargs) -> PowerPlantHomogeneousPVConfig:
        return PowerPlantHomogeneousPVConfig(*args, **kwargs)

    _config: PowerPlantHomogeneousPVConfig # pyright: ignore[reportIncompatibleVariableOverride]

    pv_array = NewsegsPVGeneratorProperty(
        default = None,
        oftype = ABCPVElecGenerator
    )
    
    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: ABCPVElecGenerator | PowerPlantHomogeneousPV,
        *args,
        **kwargs
    ) -> None:
        raise ValueError('First argument must be an ABCPVElecGenerator or PowerPlantHomogeneousPV, is %s', type(dispatch_arg))

    # Copy constructor is registered underneath class definition for late-bind
    @__init__.register(ABCPVElecGenerator)
    def _from_ABCPVElecGenerator(
        self,
        pv_array: ABCPVElecGenerator,
        *args,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)
        # Take a copy of the pv array, primarily to ensure that
        # changing its location does not break its parent
        self.pv_array = copy.deepcopy(pv_array)
    
    @classmethod
    def from_none(cls) -> PowerPlantHomogeneousPV:
        return cls(SprakePVGISElecGenerator.from_none())

    @property
    @override
    def model(self) -> NewsegsModelInterface:
        """
        The NewSEGS Model for environmental data.

        This is stored within the pv array instance to maintain sync and so
        cannot be accessed prior to a pv array being assigned.
        """
        try:
            return self.pv_array.model
        except AttributeError:
            return super().model
    
    @model.setter
    @override
    def model(self, model: NewsegsModelInterface) -> None:
        try:
            self.pv_array.model = model
        except AttributeError:
            pass
        model_setter = ABCScalingPowerPlant.model.fset
        assert model_setter is not None
        model_setter(self, model)

    @property
    def location(self) -> location.AspectLocation:
        try:
            return self.pv_array.location
        except AttributeError:
            return self._config.location
    
    @location.setter
    def location(self, loc: location.Location) -> None:
        try:
            self.pv_array.location = loc
        except AttributeError:
            pass
        try:
            super().location = loc # pyright: ignore[reportAttributeAccessIssue]
        except AttributeError:
            self._config.location = loc # pyright: ignore[reportAttributeAccessIssue]

    @property
    def n_arrays(self) -> float:
        return self.n

    @n_arrays.setter
    def n_arrays(self, n: Real) -> None:
        n = float(n)
        if n < 0:
            raise ValueError("Real of PV arrays must be positive, is %s", n)
        self.n = n

    @property
    def nameplate_capacity(self):
        return self.pv_array.nameplate_capacity * self.n

    @override
    def set_nameplate_capacity(self, nameplate_capacity: Real) -> None:
        """
        Alter the number of generators to match the required capacity.
        """
        n_array = float(nameplate_capacity) / self.pv_array.nameplate_capacity
        self.n = n_array
    
    @property
    def total_area(self):
        return self.pv_array.total_area * self.n
    
    @property
    def collector_area(self):
        return self.pv_array.collector_area * self.n

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
        model: NewsegsModelInterface | None = None,
    ) -> PowerPlantHomogeneousPV:

        a = locals()
        del a['cls']
        del a['pv_array']#

        return cls(
            pv_array,
            **a
        )

# PowerPlantHomogeneousPV copy constructor
@PowerPlantHomogeneousPV.__init__.register(PowerPlantHomogeneousPV) # pyright: ignore[reportFunctionMemberAccess]
def PowerPlantHomogeneousPV_from_other(
    self,
    other: PowerPlantHomogeneousPV
) -> None:
    super(PowerPlantHomogeneousPV, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys():
        setattr(self, k, copy.copy(getattr(other, k)))

    self.pv_array = other.pv_array


def _wrap_generator_value(val: Any, parent: ABCElecGenerator) -> Any:
    if isinstance(val, ABCElecGenerator):
        try:
            parent._config._add_child(val._config)
        except AttributeError:
            pass
        try:
            val.model = parent.model
        except AttributeError:
            pass
        # Do not sync location - let the parent decide
        # val.location = parent.location
        return val
    elif isinstance(val, list) and not isinstance(val, ObservableGeneratorList):
        return ObservableGeneratorList(val, parent = parent) # pyright: ignore[reportArgumentType]


class ObservableGeneratorList(list, RevisionNotifierMixin):

    def __init__(self, iterable = (), parent: Optional[RevisionNotifierMixin] = None):
        if parent is None:
            raise TypeError('ObservableModelLists should not be initiated without parents')
        if not isinstance(parent, ABCElecGenerator):
            raise TypeError('Parent of a generator list should be a generator')

        self._parent = parent
        RevisionNotifierMixin.__init__(self)
        wrapped = [_wrap_generator_value(item, parent) for item in iterable]
        super().__init__(wrapped)
        parent._add_child(self)

    def __setitem__(self, index, value):
        old_val = super().__getitem__(index)
        new_val = _wrap_generator_value(value, self._parent)
        if old_val != new_val:
            if isinstance(old_val, RevisionNotifierMixin):
                self._parent._remove_child(old_val)
            elif isinstance(old_val, Iterable):
                for x in old_val:
                    if isinstance(x, RevisionNotifierMixin):
                        self._parent._remove_child(x)
            super().__setitem__(index, new_val)
            self._notify_change()

    def append(self, item):
        super().append(_wrap_generator_value(item, self._parent))
        self._notify_change()

    def extend(self, iterable: Iterable) -> None:
        wrapped = [_wrap_generator_value(item, self._parent) for item in iterable]
        if wrapped:
            super().extend(wrapped)
            self._notify_change()

    def insert(self, index, item):
        super().insert(index, _wrap_generator_value(item, self._parent))
        self._notify_change()

    def pop(self, index: SupportsIndex = -1):
        item = super().pop(index)
        self._notify_change()
        if isinstance(item, RevisionNotifierMixin):
            self._parent._remove_child(item)
        return item

    def remove(self, value):
        try:
            idx = self.index(value)
            item = self[idx]
        except ValueError:
            # Let the standard error be raised
            super().remove(value)
            return

        if isinstance(item, RevisionNotifierMixin):
            self._parent._remove_child(item)
        
        super().remove(value)
        self._notify_change()

    def clear(self):
        if len(self) > 0:
            for item in self:
                if isinstance(item, RevisionNotifierMixin):
                    self._parent._remove_child(item)
            super().clear()
            self._notify_change()


class NewsegsGeneratorListProperty(newsegscomponent.ComponentProperty):
    """Assign a property as a list of generators."""
    @override
    def __set__(self, instance: ConfigurationMixin, value: ObservableGeneratorList): # type: ignore

        current_model = getattr(instance, 'model', None)

        value = _wrap_generator_value(value, instance) # pyright: ignore[reportArgumentType]
        #if not isinstance(value, ObservableGeneratorList):
            
        # Do not call super, as we need to add the list as a child, not a _config attribute
        #super().__set__(instance, value)

        old_val = getattr(instance, self.name, None)
        if old_val is not None and old_val is not value:
            instance._config._remove_child(old_val)

        #instance._config._add_child(value)
        #for item in value:
        #    _wrap_generator_value(item, instance) # pyright: ignore[reportArgumentType]
        instance._config._notify_change()

        setattr(instance, self.name, value)

        getattr(instance, self.name)._parent = instance
        
        if current_model:
            setattr(instance, 'model', current_model)


@revision_dataclass
class PowerPlantHeterogeneousGeneratorsConfig(ABCElecGeneratorConfig):
    ...


class PowerPlantHeterogeneousGenerators(ABCElecGenerator):
    """
    A power plant consisting of a Real of different generator types, locations, aspects etc
    """
    _name = "Site power plant"

    @override
    def _generate_config(self, *args, **kwargs) -> PowerPlantHeterogeneousGeneratorsConfig:
        return PowerPlantHeterogeneousGeneratorsConfig(*args, **kwargs)

    _config: PowerPlantHeterogeneousGeneratorsConfig # pyright: ignore[reportIncompatibleVariableOverride]

    generators = NewsegsGeneratorListProperty(
        default = list,
        oftype = list
    )

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: Collection[ABCScalingPowerPlant] | PowerPlantHeterogeneousGenerators,
        *args,
        do_copy: bool = True,
        **kwargs
    ) -> None:
        raise ValueError('First argument must be a collection of `ABCElecGenerator`s or a PowerPlantHeterogeneousGenerators, is %s', type(dispatch_arg))

    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(Collection)
    def _from_collection(
        self,
        generators: Collection[ABCScalingPowerPlant],
        *args,
        do_copy: bool = True,
        **kwargs
    ) -> None:
        super().__init__(*args, **kwargs)

        if do_copy:
            self.generators = [copy.deepcopy(gen) for gen in generators]
        else:
            self.generators = [gen for gen in generators]

        # On init, set location
        self.location = self._config.location
    
    @classmethod
    def from_none(cls) -> PowerPlantHeterogeneousGenerators:
        return cls([
            PowerPlantHomogeneousWind.from_none(),
            PowerPlantHomogeneousPV.from_none(),
        ])
        
    @property
    def model(self) -> NewsegsModelInterface:
        try:
            return self.generators[0].model
        except IndexError:
            return super().model

    @model.setter
    def model(self, model: NewsegsModelInterface) -> None:
        for generator in self.generators:
            generator.model = model
        model_setter = ABCElecGenerator.model.fset
        assert model_setter is not None
        model_setter(self, model)

    @property
    def location(self) -> location.Location:
        if len(self.generators):
            return self.generators[0].location
        return self._config.location
    
    @location.setter
    def location(self, loc: location.Location):
        loc = location.Location(loc) # Drop any height or aspect information in this generic setter
        for gen in self.generators:
            gen.location = loc
        self._config.location = loc
    
    def append(self, generator: ABCScalingPowerPlant) -> None:
        self.generators.append(generator)
        # Currently, set all generators to same spot location?
        # No, leave as they are when they enter.
        # self.location = self._config.location
        
    def clear(self) -> None:
        self.generators.clear()

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
        self.generators.insert(index, generator)
    
    def pop(self, index:int=-1) -> ABCElecGenerator:
        return self.generators.pop(index)

    def __len__(self):
        return len(self.generators)

    def set_n(self, n: npt.ArrayLike):
        n = np.asarray(n).flatten()
        if len(n) != len(self):
            raise ValueError("`n` should be same length as `.generators`")
        for i, n_value in enumerate(n):
            self.generators[i].n = n_value
    
    def run(
        self,
        timespan: modtimespan.TimeSpan
    ) -> np.ndarray[tuple[int,int], np.dtype[np.float64]]:
        # Verify that all are using the same model
        self.model = self.generators[0].model

        olist = [x.run(timespan) for x in self.generators]
        return np.array(olist).reshape((len(self.generators),-1))

    @property
    @override
    def nameplate_capacity(self) -> float:
        cap = 0
        for gen in self._generators:
            cap += gen.nameplate_capacity
        return cap

    @classmethod
    def from_characteristics(
        cls,
        generators: list[ABCScalingPowerPlant],
        name: str | None = None,
        model: NewsegsModelInterface | None = None,
    ) -> PowerPlantHeterogeneousGenerators:
        a = locals()
        del a['cls']
        del a['generators']

        return cls(
            generators,
            **a
        )

# PowerPlantHeterogeneousGenerators copy constructor
@PowerPlantHeterogeneousGenerators.__init__.register(PowerPlantHeterogeneousGenerators) # pyright: ignore[reportFunctionMemberAccess]
def PowerPlantHeterogeneousGenerators_from_other(
    self,
    other: PowerPlantHeterogeneousGenerators
) -> None:
    super(PowerPlantHeterogeneousGenerators, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys():
        setattr(self, k, copy.copy(getattr(other, k)))

    self.generators = []
    for gen in other.generators:
        self.generators.append(copy.deepcopy(gen))
    self.location = self._config.location


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
