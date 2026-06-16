"""
Representations of location for use in NewSEGS models.

A collection of classes used for representation of geographic point locations
with or without elevation and aspect properties.

Exports:
    Location: Base class for all locations.
    RaisedLocation: Extends Location with height_agl.
    AspectLocation: Extends RaisedLocation with pitch and azimuth.

    location_from_dict: Returns a location when provided its dictionary
                        representation (from .to_dict() method).
"""
from __future__ import annotations

import copy
from typing import Any, override, Type, TypeVar, SupportsFloat
from functools import singledispatchmethod
from pyproj import Transformer

from core import serialisation
from util import classfuncs

T = TypeVar('T')
Real = SupportsFloat

class Location(serialisation.SerialiseToDictMixin):
    """
    A point geographic location with valid latitude and longitude.

    In support of NewSEGS, provides convenience functions for using OSGB
    coordinates, though the default crs is EPSG:4326. These functions include
    applying coordinate offsets in m. However, this is currently lossy and exact
    equality after transformation cannot be guaranteed.

    A future update may hold the location in OSGB to mm precision, limiting
    the utility of the classes to the British Isles.

    The CRS is not currently exposed for write-editing.
    """
    _name = 'Site'
    _crs = 'EPSG:4326'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'Location'

    @singledispatchmethod
    def __init__(
        self,
        lat: Real | Location,
        lon: Real | None,
        name: str| None = None,
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('`lat` must be a latitude or location, is %s', lat)
    
    # Copy constructor is registered underneath class definition for late-bind.

    @__init__.register(Real)
    def _from_Reals(
        self,
        lat: Real,
        lon: Real,
        name: str | None = None,
    ) -> None:
        self._lat = float(lat)
        self._lon = float(lon)

        if name:
            self.name = name

    @classmethod
    def from_none(cls: Type[T]) -> T:
        """
        Replaces a no-argument constructor.
        """
        return cls(53.255, -3.477, name = 'St Asaph V72') # pyright: ignore[reportCallIssue]

    @property
    def lat(self) -> float:
        return self._lat
    
    @lat.setter
    def lat(self, lat: Real):
        self._lat = float(lat)

    @property
    def lon(self) -> float:
        return self._lon
    
    @lon.setter
    def lon(self, lon: Real):
        self._lon = float(lon)

    @property
    def latlon(self) :
        return (self._lat, self._lon)
    
    def get_latlon(self) -> tuple[float, float]:
        return (self._lat, self._lon)

    @latlon.setter
    def latlon(self, latlon: tuple[Real, Real]):
        self._lat = float(latlon[0])
        self._lon = float(latlon[1])
    
    def set_latlon(
            self, 
            lat: Real | tuple[Real, Real], 
            lon: Real | None = None
        ):
        if isinstance(lat, tuple):
            self._lat = float(lat[0])
            self._lon = float(lat[1])
        else:
            if lon is None:
                raise ValueError('If not setting latlon via a tuple, `lon` must be provided')
            self._lat = float(lat)
            self._lon = float(lon)

    @property
    def crs(self) -> str:
        return self._crs

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name    

    def get_osgb(self) -> tuple:
        trans_togb = Transformer.from_crs(self.crs, "EPSG:27700")
        return trans_togb.transform(self.lat, self.lon)

    @classmethod
    def from_lat_lon(cls, lat: Real, lon: Real) -> Location:
        o = cls.from_none()
        o.lat = lat
        o.lon = lon
        return o
    
    @classmethod
    def from_tuple(cls, inputs: tuple[Real, Real]) -> Location:
        o = cls.from_none()
        o.lat, o.lon = inputs
        return o

    @classmethod
    def from_osgb(
        cls, 
        easting: Real, 
        northing: Real
    ) -> Location:
        trans_tolatlon = Transformer.from_crs("EPSG:27700", cls._crs)
        coord = trans_tolatlon.transform(easting, northing)
        return cls.from_lat_lon(coord[0], coord[1])
    
    def __add__(self, other: tuple[int|float, int|float]):
        """
        Add an offset (in m) to the current coordinate, as a 2-tuple
        """
        c_gb = self.get_osgb()
        new_gb = (c_gb[0] + other[0], c_gb[1] + other[1])
        return self.__class__.from_osgb(new_gb[0], new_gb[1])

    def __sub__(self, other:tuple[int|float, int|float]):
        """
        Subtract an offset (in m) from the current coordinate, as a 2-tuple
        """
        o2 = (-other[0], -other[1])
        return self + o2

    @override
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Location):
            raise ValueError('`other` must be a Location instance, is %s', type(other))

        return (
            (self.lat == other.lat) 
            and (self.lon == other.lon) 
            and (self.crs == other.crs)
        )

    def __neq__(self, other: Location) -> bool:
        return not(self == other)
    
    def __str__(self):
        return "(" + str(self.lat) + ", " + str(self.lon) + ")"
    
    def __repr__(self):
        return (
            "" + classfuncs.get_class(self)
            + "(" + repr(self.lat) 
            + ", " + repr(self.lon)
            +")"
        )

    @classmethod
    def from_characteristics(
        cls: Type[T],
        lat: Real,
        lon: Real,
        crs: str = 'EPSG:4326',
        name: str | None = None,
    ) -> T:

        o = cls.from_none() # pyright: ignore[reportAttributeAccessIssue]
        
        o._crs = crs
        o.lat = lat
        o.lon = lon

        if name:
            o.name = name

        return o

    def to_dict(self) -> dict:
        odict = {
            'class': classfuncs.get_class(self),
            'name': self._name,
            'lat': self._lat,
            'lon': self._lon,
            'crs': self._crs
        }
        return odict

    @classmethod
    def from_dict(cls, input: dict[str, Any]) -> Location:
        input.pop('class', None)
        return cls.from_characteristics(**input)

# Location copy constructor
@Location.__init__.register(Location) # pyright: ignore[reportFunctionMemberAccess]
def Location_from_other(self, other: Location):
    """
    Initialise a Location using another Location
    """
    latlon = other.latlon
    self._lat = latlon[0]
    self._lon = latlon[1]
    self._name = other.name
    self._crs = other._crs

class RaisedLocation(Location):
    _height = 0.

    @singledispatchmethod
    def __init__(
        self,
        lat: Real | Location,
        lon: Real | None = None,
        height_agl: Real | None = None,
        name: str | None = None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('First value must be a latitude or location, is %s', lat)
    
    @override
    @__init__.register(Real)
    def _from_Reals(
        self,
        lat: Real,
        lon: Real,
        height_agl: Real = 0.,
        name: str | None = None
    ) -> None:
        super().__init__(lat, lon, name = name)
        self._height = float(height_agl)
    
    @property
    def height_agl(self) -> float:
        return self._height
    
    @height_agl.setter
    def height_agl(self, height: Real):
        self._height = float(height)

    @classmethod
    def from_lat_lon_height(
        cls,
        lat: Real, 
        lon: Real,
        height_agl: Real
    ):
        o = cls(lat, lon, height_agl)
        return o

    @classmethod
    def from_tuple(
        cls, 
        inputs: tuple[Real, Real] | tuple[Real, Real, Real]
    ):
        o = cls(*inputs)
        return o
    
    def __eq__(self, other: object) -> bool:
        ok = super().__eq__(other)

        if isinstance(other, RaisedLocation):
            ok =  ok and (self.height_agl == other.height_agl)
        
        return ok

    def __neq__(self, other: Location) -> bool:
        return not(self == other)
        
    def __str__(self):
        return (
            "(" + str(self.lat) 
            + ", " + str(self.lon) 
            + "), height: " 
            + str(self.height_agl) + " m AGL"
        )

    def __repr__(self):
        return (
            "" + classfuncs.get_class(self)
            + "(" + repr(self.lat) 
            + ", " + repr(self.lon)
            + ", " + repr(self.height_agl)
            +")"
        )

    @classmethod
    def from_characteristics(
        cls: Type[T],
        *args, 
        height_agl: Real,
        **kwargs
    ) -> T:

        o = super().from_characteristics(*args, **kwargs)
        o.height_agl = height_agl
        
        return o

    def to_dict(self) -> dict:
        odict = super().to_dict()
        odict['height_agl'] = self._height
        return odict

# RaisedLocation copy constructor
@RaisedLocation.__init__.register(Location) # pyright: ignore[reportFunctionMemberAccess]
def RaiseLocation_from_other(
    self,
    other: Location
) -> None:
    """
    Initialise a RaisedLocation using another Location
    """
    latlon = other.latlon
    self.set_latlon(latlon)
    if isinstance(other, RaisedLocation):
        self.height_agl = other.height_agl
    self._name = other.name

class AspectLocation(RaisedLocation):
    _azimuth = 180.
    _pitch = 90.
    
    @singledispatchmethod
    def __init__(
        self,
        lat: Real | Location,
        lon: Real | None = None,
        height_agl: Real | None = None,
        azimuth: Real | None = None,
        pitch: Real | None = None,
        name: str | None = None,
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('First value must be a latitude or location, is %s', lat)
    
    @override
    @__init__.register(Real)
    def _from_Reals(
        self,
        lat: Real,
        lon: Real,
        height_agl: Real = 0.,
        azimuth: Real = 180.,
        pitch: Real = 90.,
        name: str | None = None,
    ) -> None:
        super().__init__(lat, lon, height_agl = height_agl, name = name)
        self.azimuth = float(azimuth)
        self.pitch = float(pitch)
    
    @property
    def azimuth(self) -> float:
        return self._azimuth
    
    @azimuth.setter
    def azimuth(self, azimuth: Real):
        self._azimuth = float(azimuth) % 360.0
    
    @property
    def pitch(self) -> float:
        return self._pitch
    
    @pitch.setter
    def pitch(self, pitch: Real):
        self._pitch = float(pitch)

    @classmethod
    def from_llhap(
        cls, 
        lat: Real,
        lon: Real,
        height_agl: Real,
        azimuth: Real,
        pitch: Real
    ) -> AspectLocation:
        o = cls(lat, lon, height_agl, azimuth, pitch)
        return o

    @classmethod
    def from_tuple(
        cls, 
        inputs: tuple[Real, Real] | tuple[Real, Real, Real] | tuple[Real, Real, Real, Real, Real]):
        """
            Tuple should consist of

            - latitude
            - longitude
            - height agl
            - azimuth
            - pitch
        """
        o = cls(*inputs)
        return o
    
    def __eq__(self, other: object) -> bool:
        if isinstance(other, AspectLocation):
            return super().__eq__(other) and (self.azimuth == other.azimuth) and (self.pitch == other.pitch)
        else:
            return super().__eq__(other)

    def __neq__(self, other:Location) -> bool:
        if isinstance(other, AspectLocation):
            return super().__neq__(other) or (self.azimuth != other.azimuth) and (self.pitch != other.pitch)
        else:
            return super().__neq__(other)

    def __str__(self):
        return "(" + str(self.lat) + ", " + str(self.lon) + "), height: " + str(self.height_agl) + " m AGL, azimuth: " + str(self.azimuth) + "°, pitch: " + str(self.pitch) + "°"

    @classmethod
    def from_characteristics(
        cls: Type[T],
        *args,
        azimuth: Real,
        pitch: Real,
        **kwargs,
    ) -> T:
        
        o = super().from_characteristics(*args, **kwargs)
        o.azimuth = azimuth
        o.pitch = pitch

        return o

    def to_dict(self) -> dict:
        odict = super().to_dict()
        odict['azimuth'] = self._azimuth
        odict['pitch'] = self._pitch
        return odict

# AspectLocation copy constructor
@AspectLocation.__init__.register(Location) # pyright: ignore[reportFunctionMemberAccess]
def AspectLocation_from_other(
    self,
    other: Location
) -> None:
    """
    Initialise an AspectLocation using another Location
    """
    latlon = other.latlon
    self.set_latlon(latlon)
    if isinstance(other, RaisedLocation):
        self.height_agl = other.height_agl
    if isinstance(other, AspectLocation):
        self.azimuth = other.azimuth
        self.pitch = other.pitch
    self._name = other.name

_LOCATION_CONSTRUCTORS = {
    'Location': Location,
    'RaisedLocation': RaisedLocation,
    'AspectLocation': AspectLocation
}

def location_from_dict(input: dict[str, Any]):
    input = copy.copy(input)
    classname = input.pop('class')
    constructor = _LOCATION_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('No location class found for ', classname)
    return constructor.from_dict(input)
