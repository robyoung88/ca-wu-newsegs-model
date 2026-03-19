from __future__ import annotations
from abc import ABCMeta, abstractmethod
from collections.abc import Callable,Mapping
import numpy as np
import numpy.typing as npt
from copy import copy
from src.core import TimeSpan
from src.core import Location,RaisedLocation,AspectLocation,location_from_dict
#from src.newsegsmodel.newsegsmodel import NewsegsModel

#def __cp_interpolant_factory(cp_curve:np.ndarray[tuple[int,int], np.dtype[np.number]]) -> Callable[npt.ArrayLike,npt.ArrayLike]:
def _cp_interpolant_factory(cp_curve):
    def interpolant(x):
        return np.interp(x, cp_curve[0,:], cp_curve[1,:], left=0.0, right=0.0)
    return interpolant

class ABCElecGenerator(metaclass=ABCMeta):
    @abstractmethod
    def run(self, timespan:TimeSpan) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Something to return a friendly string identifier for the config
        """
        ...
    
    @property
    @abstractmethod
    def model(self):
        """
        The callback model associated with the generator
        """
        ...

    @model.setter
    @abstractmethod
    def model(self, callback_model):
        ...
    # def model(self, callback_model:newsegsmodel.NewsegsModel):

    @abstractmethod
    def to_dict(self):
        """
        Configuration as a dictionary
        """
        ...
    
    #@abstractmethod
    #def load_dict(self):
    #    """
    #    Update configuration using a dictionary
    #    """
    #    ...

    @property
    @abstractmethod
    def location(self) -> Location:
        ...

    @location.setter
    @abstractmethod
    def location(self, loc:Location):
        ...
    
    @property
    @abstractmethod
    def nameplate_capacity(self) -> float:
        ...

class WindTurbineElecGenerator(ABCElecGenerator):
    _default_cp_curve = np.asarray(
        [
            [0,  3,  5,   10, 25, 26, 50],
            [0.0,0.0,0.25,0.4,0.1,0.0,0.0]
        ]).reshape((2,-1))
    _default_name = "Wind Turbine"
    def __init__(self,
                 other:WindTurbineElecGenerator|None = None
                 ) -> None:
        if other is None:
            self._model = None
            self._name = self._default_name
            self._cut_in = 0.0
            self._cut_out = 50.0
            self._swept_area = 1.0
            self._hub_height = 10.0
            self._rated_power = 0.245
            self._location = RaisedLocation()
            self.set_cp_curve(type(self)._default_cp_curve)
        elif isinstance(other, WindTurbineElecGenerator):
            self._model = other.model
            self._name = other.name
            self._cut_in = other.cut_in
            self._cut_out = other.cut_out
            self._swept_area = other.swept_area
            self._hub_height = other.hub_height
            self._rated_power = other.rated_power
            self._location = other.location
            self.set_cp_curve(other._cp_curve)
        else:
            raise ValueError("'other' must be a WindTurbineElecGenerator")

    @property
    def model(self):# -> NewsegsModel|None:
        return self._model
    
    @model.setter
    def model(self, model) -> None:
        self._model = model

    @property
    def cut_in(self) -> float:
        return self._cut_in
    
    @cut_in.setter
    def cut_in(self, cut_in:float) -> None:
        self._cut_in = cut_in
    
    @property
    def cut_out(self) -> float:
        return self._cut_out
    
    @cut_out.setter
    def cut_out(self, cut_out:float) -> None:
        self._cut_out = cut_out
    
    @property
    def rated_power(self) -> float:
        return self._rated_power
    
    @rated_power.setter
    def rated_power(self, rated_power:float) -> None:
        self._rated_power = rated_power

    @property
    def nameplate_capacity(self) -> float:
        return self.rated_power

    @property
    def swept_area(self) -> float:
        return self._swept_area
    
    @swept_area.setter
    def swept_area(self, swept_area:float) -> None:
        self._swept_area = swept_area

    @property
    def rotor_diameter(self) -> float:
        return 2.0 * np.sqrt(self._swept_area) / np.pi
    
    @rotor_diameter.setter
    def rotor_diameter(self, diameter:float) -> None:
        self._swept_area = np.pi * (0.5 * diameter) ** 2
    
    @property
    def hub_height(self) -> float:
        return self._hub_height

    @hub_height.setter
    def hub_height(self, height:float) -> None:
        self._hub_height = height
        if hasattr(self, '_location'):
            self._location.height_agl = height

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def location(self) -> RaisedLocation:
        return self._location

    @location.setter
    def location(self, loc:Location) -> None:
        if (isinstance(loc, RaisedLocation) and loc.height_agl != self.hub_height):
            raise UserWarning("Provided location includes a height unequal to hub, and will be ignored")
        self._location = RaisedLocation(loc)
        self._location.height_agl = self.hub_height
    
    def set_cp_curve(self, 
                     cp_curve:np.ndarray[tuple[int,int], np.dtype[np.number]]
                     ) -> None:
        if np.any(cp_curve[1,:]> 16/27):
            raise UserWarning("Cp curve contains entries exceeding the Betz limit. This is implausible with a standard HAWT. Check your power curve")
        if np.any(cp_curve[1,:] < 0.0):
            raise UserWarning("Cp curve contains negative values. Self-consumption should be handled separately. They will be overwritten by zeros")
            cp_curve = copy(cp_curve)
            cp_curve[1,cp_curve[1,:]<0.0] = 0.0
        self._cp_curve = cp_curve
        self._cp_func = _cp_interpolant_factory(cp_curve)
    
    def set_power_curve(self,
                        power_curve:np.ndarray[tuple[int,int], np.dtype[np.number]],
                        air_density:float=1.225
                        ) -> None:
        """
        The power curve is used to derive the coefficient of performance. Air density should be that used for derivation of the power curve.
        """
        available_power = 0.5 * air_density * self.swept_area * power_curve[0,:] * power_curve[0,:] * power_curve[0,:]
        cp_curve = copy(power_curve)
        with np.errstate(divide='ignore', invalid='ignore'):
            cp_curve[1,:] = power_curve[1,:] / available_power
        cp_curve[1,:] = np.where(available_power<=0.0, 0.0, cp_curve[1,:])
        self.set_cp_curve(cp_curve)

    @property
    def cp(self) -> Callable:
        return self._cp_func

    def run(self, timespan:TimeSpan) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        if self.model is None:
            raise ValueError("Electrical generator requires a model to serve environmental data")
        wind_speeds = self.model.local_env.get_wind_speeds(self.location, timespan)
        air_density = self.model.local_env.get_air_density(self.location, timespan)
        return (0.5 * air_density * self.swept_area * self.cp(wind_speeds) * wind_speeds**3).reshape((1,-1))

    @classmethod
    def from_characteristics(cls,
                             cut_in:float,
                             cut_out:float,
                             rated_power:float,
                             swept_area:float,
                             hub_height:float,
                             name:str|None=None,
                             location:Location|None=None,
                             cp_curve:np.ndarray[tuple[int,int], np.dtype[np.number]]|None=None,
                             power_curve:np.ndarray[tuple[int,int], np.dtype[np.number]]|None=None
                             ) -> WindTurbineElecGenerator:
        o = cls()

        o.cut_in = cut_in
        o.cut_out = cut_out
        o.rated_power = rated_power
        o.swept_area = swept_area
        o.hub_height = hub_height
        if name is None:
            o_name = cls._default_name
        else:
            o.name = name

        if not location is None:
            o.location = location

        if not (cp_curve is None):
            o.set_cp_curve(cp_curve)
        elif not (power_curve is None):
            o.set_power_curve(power_curve)
        else:
            raise ValueError("Either cp_curve or power_curve must be specified")

        return o

    def to_dict(self) -> dict:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'cut_in': self._cut_in,
            'cut_out': self._cut_out,
            'rated_power': self._rated_power,
            'swept_area': self._swept_area,
            'hub_height': self._hub_height,
            'location': self._location.to_dict(),
            'cp_curve': self._cp_curve
        }

        return odict
    
    @classmethod
    def from_dict(cls, input:dict) -> WindTurbineElecGenerator:
        if input.get('location', None) is not None:
            input['location'] = location_from_dict(input['location'])
        return cls.from_characteristics(**input)

class PowerPlantHomogeneousWind(ABCElecGenerator):
    """
    A power plant consisting of a (possibly non-integer) number of identical wind turbines at a nominal location
    """
    _default_name = "Wind Farm"

    def __init__(self,
                 other:PowerPlantHomogeneousWind|WindTurbineElecGenerator|None=None):
        if other is None:
            self._model = None
            self._name = self._default_name
            self._turbine = WindTurbineElecGenerator()
            self._location = self._turbine.location
            self._n_turbines = 1.0
        elif isinstance(other, PowerPlantHomogenousWind):
            self._model = other.model
            self._name = other.name
            self._turbine = other.turbine
            self._location = other.location
            self._n_turbines = other.n_turbines
        elif isinstance(other, WindTurbineElecGenerator):
            self._name = self._default_name
            self._turbine = other
            self._model = self._turbine.model
            self._location = self._turbine.location
            self._n_turbines = 1.0
        else:
            raise ValueError("`other` should be a `PowerPlantHomogeneousWind` or `WindTurbineElecGenerator`")
        
    @property
    def model(self):# -> NewsegsModel|None:
        return self._model
    
    @model.setter
    def model(self, model) -> None:
        self._model = model
        self._turbine.model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name
    
    @property
    def location(self) -> RaisedLocation:
        return self._location

    @location.setter
    def location(self, loc:Location) -> None:
        if (isinstance(loc, RaisedLocation) and loc.height_agl != self._turbine.hub_height):
            raise UserWarning("Provided location includes a height unequal to hub, which will be ignored")
        self._location = RaisedLocation(loc)
        self._location.height_agl = self._turbine.hub_height
        self._turbine.location = self._location

    @property
    def turbine(self) -> WindTurbineElecGenerator:
        return self._turbine

    @turbine.setter
    def turbine(self, turbine:WindTurbineElecGenerator) -> None:
        self._turbine = copy(turbine)
        self._turbine.hub_height = self._location.height_agl
        self._turbine.location = self._location
        if self._turbine.model is None:
            self._turbine.model = self.model
        elif self.model is None and self._turbine.model is not None:
            self._model = self._turbine.model

    @property
    def n_turbines(self) -> float:
        return self._n_turbines

    @n_turbines.setter
    def n_turbines(self, n:float|int) -> None:
        assert n >= 0.0, "Number of turbines must be positive"
        self._n_turbines = float(n)

    @property
    def nameplate_capacity(self):
        return self._turbine.rated_power * self._n_turbines

    @property
    def swept_area(self):
        return self._turbine.swept_area * self._n_turbines
    
    def run(self, timespan:Timespan) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        return self.n_turbines * self.turbine.run(timespan)

    @classmethod
    def from_characteristics(cls,
                             turbine:WindTurbineElecGenerator,
                             location:RaisedLocation,
                             n_turbines:float,
                             name:str
                             ) -> PowerPlantHomogeneousWind:
        o = cls()

        o.turbine = turbine
        o.location = location
        o.n_turbines = n_turbines
        o.name = name

        return o

    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'turbine': self._turbine.to_dict(),
            "location": self._location.to_dict(),
            "n_turbines": self._n_turbines
        }
        return odict
    
    @classmethod
    def from_dict(cls, input:Mapping) -> PowerPlantHomogeneousWind:
        if input.get('turbine', None) is not None:
            input['turbine'] = generator_from_dict(input['turbine'])
        if input.get('location', None) is not None:
            input['location'] = location_from_dict(input['location'])
        return cls.from_characteristics(**input)

class ABCPVElecGenerator(ABCElecGenerator):
    """
    Abstract base class for all PV generation models
    """
    _default_name = "PV array"

    def __init__(self,
                 other:ABCPVElecGenerator|None = None
                 ) -> None:
        if other is None:
            self._model = None
            self._name = self._default_name
            self._peak_power = 1.0
            self._total_area = self._peak_power / 0.435
            self._collector_area = self._total_area * 1.0
            self._frame_factor = None
            self._location = AspectLocation()
        elif isinstance(other, SprakePVElecGenerator):
            self._model = other.model
            self._name = other.name
            self._peak_power = other.peak_power
            self._total_area = other.total_area
            self._collector_area = other.collector_area
            self._frame_factor = other._frame_factor # NB - must get this internal, as we don't want the computed value
            self._location = other.location
        else:
            raise ValueError("`other` must be an `ABCPVElecGenerator`")

    @property
    def model(self):# -> NewsegsModel|None:
        return self._model
    
    @model.setter
    def model(self, model) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def peak_power(self) -> float:
        return self._peak_power
    
    @peak_power.setter
    def peak_power(self, power:int|float) -> None:
        assert power >= 0, "`peak_power` should be positive"
        self._peak_power = float(power)

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
    def total_area(self, area:int|float) -> None:
        assert area >= 0.0, "'area' should be positive"
        self._total_area = float(area)
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
    def collector_area(self, area:int|float) -> None:
        assert area >= 0.0, "'area' should be positive"
        self._collector_area = float(area)
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
            assert factor >= 0.0 and factor <= 1.0, "`factor` must be in range [0,1] (or `None`)"
        self._frame_factor = factor
        # Reset total area to force recalculation of collector area
        self.total_area = self._total_area

    @property
    def location(self) -> AspectLocation:
        return self._location

    @location.setter
    def location(self, loc:Location) -> None:
        self._location = AspectLocation(loc)

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             peak_power:float,
                             total_area:float,
                             collector_area:float,
                             frame_factor:float|None,
                             location:AspectLocation
                             ) -> ABCPVElecGenerator:
        o = cls()

        o.name = name
        o.peak_power = peak_power
        o.total_area = total_area
        o.collector_area = collector_area
        o.frame_factor = frame_factor
        o.location = location
        
        return o
    
    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'peak_power': self._peak_power,
            'total_area': self._total_area,
            'collector_area': self._collector_area,
            'frame_factor': self._frame_factor,
            'location': self._location.to_dict()
        }

        return odict

    @classmethod
    def from_dict(cls, input:Mapping) -> ABCPVElecGenerator:
        if input.get('location', None) is not None:
            input['location'] = location_from_dict(input['location'])
        return cls.from_characteristics(**input)

class SprakePVElecGenerator(ABCPVElecGenerator):
    _default_name = "Simple PV Panel"

    def __init__(self,
                 other:SprakePVElecGenerator|None = None
                 ) -> None:
        super().__init__(other)
        if other is None:
            self._self_consumption = 0.04
            self._aspect_factor = 0.7
        elif isinstance(other, SprakePVElecGenerator):
            self._self_consumption = other.self_consumption
            self._aspect_factor = other.aspect_factor
        else:
            raise ValueError("'other' must be a SprakePVElecGenerator")

    @property
    def self_consumption(self) -> float:
        """
        The maximum self-consumption of the module or array in kW. 

        In the Sprake model, this is taken from mean production rate over the timestep. If the result is < 0, then it is clipped to 0
        """
        return self._self_consumption

    @self_consumption.setter
    def self_consumption(self, self_consumption_kw:int|float) -> None:
        if self_consumption_kw < 0:
            raise UserWarning("Self consumption is defined positive - negative implies baseline generation without solar resource")
        if self_consumption_kw > self._peak_power:
            raise UserWarning("Self-consumption greater than peak power under STC. Have you checked units?")
        self._self_consumption = self_consumption_kw
    
    @property
    def aspect_factor(self) -> float:
        """
        The Sprake model reduces production at all times by a factor reflecting the reduction from total horizontal radiation received by collectors due to pitch and azimuth of collectors.

        This simple model does not vary this loss by the actual solar position and the azimuth and pitch of the array
        """
        return self._aspect_factor

    @aspect_factor.setter
    def aspect_factor(self, factor:float) -> None:
        assert factor >= 0.0, "`factor` should be positive."
        if factor > 1.0:
            raise UserWarning("Setting `factor` > 1 implies some form of concentrating technology is in use.")
        self._aspect_factor = factor

    def run(self, timespan:TimeSpan) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        if self.model is None:
            raise ValueError("Electrical generator requires a model to serve environmental data")
        global_horizontal_flux = self.model.local_env.get_horizontal_solar_flux(self.location, timespan)
        # Scale flux to collector area
        # NB - in Sprake model, the aspect factor does not get applied until after the removal of
        # self-consumption. This is counter-intuitive, and we have reversed it here
        collector_flux = global_horizontal_flux * self.collector_area * self.aspect_factor - self.self_consumption
        
        # Apply assumption of no consumption when under low irradiation
        collector_flux[collector_flux<0.0] = 0.0

        return collector_flux.reshape((1,-1))

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             peak_power:float,
                             total_area:float,
                             collector_area:float,
                             frame_factor:float|None,
                             location:AspectLocation,
                             self_consumption:float,
                             aspect_factor:float
                             ) -> ABCPVElecGenerator:

        a = locals()
        del a['self_consumption']
        del a['aspect_factor']
        del a['cls']
        del a['__class__']
        o = super(SprakePVElecGenerator, cls).from_characteristics(**a)

        o.self_consumption = self_consumption
        o.aspect_factor = aspect_factor

        return o
    
    def to_dict(self) -> Mapping:
        odict = super().to_dict()
        odict['self_consumption'] = self._self_consumption
        odict['aspect_factor'] = self._aspect_factor

        return odict

class PowerPlantHomogeneousPV(ABCElecGenerator):
    """
    A power plant consisting of a (possibly non-integer) number of identical PV modules or arrays at a nominal location, with identical aspect and pitch, without self-shadowing
    """
    _default_name = "Solar PV Array"
    
    def __init__(self,
                 other:PowerPlantHomogeneousPV|ABCPVElecGenerator|None=None
                ) -> None:
        if other is None:
            self._model = None
            self._name = self._default_name
            self._pv_array = SprakePVElecGenerator()
            self._location = self._pv_array.location
            self._n_arrays = 1.0
        elif isinstance(other, PowerPlantHomogeneousPV):
            self._model = other.model
            self._name = other.name
            self._pv_array = other.pv_array
            self._location = other.location
            self._n_arrays = other.n_arrays
        elif isinstance(other, ABCPVElecGenerator):
            self._name = self._default_name
            self._pv_array = other
            self._model = other.model
            self._location = other.location
            self._n_arrays = 1.0
        else:
            raise ValueError("`other` should be a `PowerPlantHomogeneousPV` or `ABCPVElecGenerator`")
    
    @property
    def name(self):
        return self._name
    
    @name.setter
    def name(self, name):
        self._name = name

    @property
    def model(self):# -> NewsegsModel|None:
        return self._model
    
    @model.setter
    def model(self, model) -> None:
        self._model = model
        self._pv_array.model = model

    @property
    def location(self) -> AspectLocation:
        return self._location
    
    @location.setter
    def location(self, loc:Location) -> None:
        if (isinstance(loc, AspectLocation) and (
            loc.azimuth != self.pv_array.location.azimuth or  loc.pitch != self.pv_array.location.pitch)):
            raise UserWarning("Provided location includes and azimuth and pitch unequal to pv array. These will be ignored")
        self._location = AspectLocation(loc)
        self._location.azimuth = self.pv_array.location.azimuth
        self._location.pitch = self.pv_array.location.pitch
        self._pv_array.location = self._location
    
    @property
    def pv_array(self) -> ABCPVElecGenerator:
        return self._pv_array
    
    @pv_array.setter
    def pv_array(self, pv_generator:ABCPVElecGenerator) -> None:
        self._location.az = pv_generator.location.azimuth
        self._location.pitch = pv_generator.location.pitch
        pv_generator.location = self._location
        self._pv_array = pv_generator

    @property
    def n_arrays(self) -> float:
        return self._n_arrays

    @n_arrays.setter
    def n_arrays(self, n:float|int) -> None:
        assert n >= 0.0, "Number of PV arrays must be positive"
        self._n_arrays = float(n)

    @property
    def nameplate_capacity(self):
        return self._pv_array.nameplate_capacity * self._n_arrays
    
    @property
    def total_area(self):
        return self._pv_array.total_area * self._n_arrays
    
    @property
    def collector_area(self):
        return self._pv_array.collector_area * self._n_arrays

    def run(self, timespan:Timespan) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        return self.n_arrays * self.pv_array.run(timespan)

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             pv_array:ABCPVElecGenerator,
                             location:Location,
                             n_arrays:float
                             ) -> PowerPlantHomogeneousPV:
        o = cls()
        o.name = name
        o.pv_array = pv_array
        o.location = location
        o.n_arrays = n_arrays

        return o

    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'pv_array': self._pv_array.to_dict(),
            'location': self._location.to_dict(),
            'n_arrays': self._n_arrays
        }

        return odict

    @classmethod
    def from_dict(cls, input:Mapping) -> PowerPlantHomogeneousPV:
        if input.get('pv_array', None) is not None:
            input['pv_array'] = generator_from_dict(input['pv_array'])
        if input.get('location', None) is not None:
            input['location'] = location_from_dict(input['location'])
        return cls.from_characteristics(**input)

class PowerPlantHeterogeneousGenerators(ABCElecGenerator):
    """
    A power plant consisting of a number of different generator types, locations, aspects etc
    """
    _default_name = "Site power plant"
    
    def __init__(self,
                 other:PowerPlantHeterogeneousGenerators|None=None
                 ) -> None:
        if other is None:
            self._model = None
            self._name = self._default_name
            self._generator_list = []
        elif isinstance(other, PowerPlantHeterogeneousGenerators):
            self._model = other.model
            self._name = other.name
            self._generator_list = other.generators
        else:
            raise ValueError("`other` should be a `PowerPlantHeterogeneousGenerators")
        
    @property
    def model(self):# -> NewsegsModel|None:
        return self._model

    @model.setter
    def model(self, model) -> None:
        self._model = model
        for generator in self.generators:
            generator.model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def generators(self) -> list[ABCElecGenerator]:
        return self._generator_list
    
    def append(self, generator:ABCElecGenerator) -> None:
        if generator.model is None:
            generator.model = self.model
        self._generator_list.append(generator)
    
    def clear(self) -> None:
        self._generator_list.clear()

    def extend(self, other:PowerPlantHeterogeneousGenerators) -> None:
        for gen in other.generators:
            self.append(gen)
    
    def insert(self, index:int, generator:ABCElecGenerator) -> None:
        if generator.model is None:
            generator.model = self.model
        self._generator_list.insert(index, generator)
    
    def pop(self, index:int=-1) -> ABCElecGenerator:
        return self._generator_list.pop(index)

    def __len__(self):
        return len(self._generator_list)

    def set_n(self, n:npt.ArrayLike):
        n = np.asarray(n).flatten()
        if len(n) != len(self):
            raise ValueError("`n` should be same length as `.generators`")
        for i,n_value in enumerate(n):
            self._generator_list[i].n = n_value
    
    def run(self, timespan:TimeSpan) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        olist = [x.run(timespan) for x in self._generator_list]
        return np.array(olist).reshape((len(self._generator_list),-1))

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             generators:list[ABCElecGenerator]
                             ) -> PowerPlantHeterogeneousGenerators:
        o = cls()
        o.name = name
        o.extend(generators)

        return o

    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'generators': [x.to_dict for x in self.generators]
        }
        return odict

    @classmethod
    def from_dict(cls, input:Mapping) -> PowerPlantHeterogeneousGenerators:
        if input.get('generators', None) is not None:
            input['generators'] = [generator_from_dict(x) for x in input['generators']]
        return cls.from_characteristics(**input)

    @property
    def location(self):
        return self._generator_list[0].location
    
    @location.setter
    def location(self, newloc):
        self._generator_list[0].location=newloc

    @property
    def nameplate_capacity(self):
        cap = 0
        for gen in self._generator_list:
            cap += gen.nameplate_capacity
        return cap

generator_constructors = {
    'WindTurbineElecGenerator': WindTurbineElecGenerator,
    'PowerPlantHomogeneousWind': PowerPlantHomogeneousWind,
    'SprakePVElecGenerator': SprakePVElecGenerator,
    'PowerPlantHomogeneousPV': PowerPlantHomogeneousPV
}

def generator_from_dict(input:Mapping):
    classname = input.pop('class')
    constructor = generator_constructors.get(classname, None)
    if constructor is None:
        return constructor
    return constructor.from_dict(input)
