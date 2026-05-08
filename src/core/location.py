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

from numbers import Number
from typing import override
import copy
from functools import singledispatchmethod
from pyproj import Transformer

from src.util import classfuncs

class Location:
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

    @singledispatchmethod
    def __init__(
        self,
        lat: Number | Location,
        lon: Number | None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('`lat` must be a latitude or location, is %s', lat)
    
    # Copy constructor is registered underneath class definition for late-bind.

    @__init__.register(Number)
    def _from_numbers(
        self,
        lat: Number,
        lon: Number
    ) -> None:
        self._lat = float(lat)
        self._lon = float(lon)

    @classmethod
    def from_none(cls) -> Location:
        """
        Replaces a no-argument constructor.
        """
        return cls(53.46, -3.80)

    @property
    def lat(self) -> float:
        return self._lat
    
    @lat.setter
    def lat(self, lat):
        self._lat = float(lat)

    @property
    def lon(self) -> float:
        return self._lon
    
    @lon.setter
    def lon(self, lon: Number):
        self._lon = float(lon)

    @property
    def latlon(self) :
        return (self._lat, self._lon)
    
    def get_latlon(self) -> tuple[Number, Number]:
        return (self._lat, self._lon)

    @latlon.setter
    def latlon(self, latlon: tuple[Number, Number]):
        self._lat = latlon[0]
        self._lon = latlon[1]
    
    def set_latlon(self, lat: Number|tuple[Number, Number], lon: Number|None = None):
        if isinstance(lat, tuple):
            self._lat = float(lat[0])
            self._lon = float(lat[1])
        else:
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
    def from_lat_lon(cls, lat: Number, lon: Number) -> Location:
        o = cls.from_none()
        o.lat = lat
        o.lon = lon
        return o
    
    @classmethod
    def from_tuple(cls, inputs:tuple[Number, Number]) -> Location:
        o = cls.from_none()
        o.lat, o.lon = inputs
        return o

    @classmethod
    def from_osgb(cls, easting:int|float, northing:int|float) -> Location:
        trans_tolatlon = Transformer.from_crs("EPSG:27700", cls._crs)
        coord = trans_tolatlon.transform(easting, northing)
        return cls.from_lat_lon(coord[0], coord[1])
    
    def __add__(self, other:tuple[int|float, int|float]):
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

    def __eq__(self, other: Location) -> bool:
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
        cls,
        lat: Number,
        lon: Number,
        crs: str,
        name: str
    ) -> Location:

        o = cls.from_none()
        
        o._crs = crs
        o.name = name
        o.lat = lat
        o.lon = lon

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
    def from_dict(cls, input: dict) -> Location:
        input.pop('class', None)
        return cls.from_characteristics(**input)

    # If we are using single dispatch, then we are unable
    # to use a "None" first argument for a default constructor
    # To get around this, we will use a class method
    @classmethod
    def from_none(cls):
        return cls(52., -3.5)

# Location copy constructor
@Location.__init__.register(Location)
def Location_from_other(self, other: Location):
    """
    Initialise a Location using another Location
    """
    latlon = other.latlon
    self._lat = latlon[0]
    self._lon = latlon[1]
    self._name = other.name

class RaisedLocation(Location):
    _height = 0.

    @singledispatchmethod
    def __init__(
        self,
        lat: Number | Location,
        lon: Number | None = None,
        height_agl: Number | None = None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('First value must be a latitude or location, is %s', lat)
    
    @override
    @__init__.register(Number)
    def _from_numbers(
        self,
        lat: Number,
        lon: Number,
        height_agl: Number = 0.
    ) -> None:
        self._lat = float(lat)
        self._lon = float(lon)
        self._height = float(height_agl)
    
    @property
    def height_agl(self) -> float:
        return self._height
    
    @height_agl.setter
    def height_agl(self, height: Number):
        self._height = float(height)

    @classmethod
    def from_lat_lon_height(
        cls,
        lat: Number, 
        lon: Number,
        height_agl: Number
    ):
        o = cls(lat, lon, height_agl)
        return o

    @classmethod
    def from_tuple(
        cls, 
        inputs: tuple[Number, Number, Number]):
        o = cls(*inputs)
        return o
    
    def __eq__(self, other: Location) -> bool:
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
        cls,
        lat: Number,
        lon: Number,
        crs: str,
        height_agl: Number,
        name: str
    ) -> RaisedLocation:

        a = locals()
        del a['height_agl']
        del a['cls']
        del a['__class__']

        o = super(RaisedLocation, cls).from_characteristics(**a)
        o.height_agl = height_agl
        
        return o

    def to_dict(self) -> dict:
        odict = super().to_dict()
        odict['height_agl'] = self._height
        return odict

# RaisedLocation copy constructor
@RaisedLocation.__init__.register(Location)
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
        lat: Number | Location,
        lon: Number | None = None,
        height_agl: Number | None = None,
        azimuth: Number | None = None,
        pitch: Number | None = None
    ) -> None:
        """
        Default assumes we have None
        """
        raise ValueError('First value must be a latitude or location, is %s', lat)
    
    @override
    @__init__.register(Number)
    def _from_numbers(
        self,
        lat: Number,
        lon: Number,
        height_agl: Number = 0.,
        azimuth: Number = 180.,
        pitch: Number = 90.
    ) -> None:
        self._lat = float(lat)
        self._lon = float(lon)
        self._height = float(height_agl)
        self.azimuth = float(azimuth)
        self.pitch = float(pitch)
    
    @property
    def azimuth(self) -> float:
        return self._azimuth
    
    @azimuth.setter
    def azimuth(self, azimuth: Number):
        self._azimuth = azimuth % 360.0
    
    @property
    def pitch(self) -> float:
        return self._pitch
    
    @pitch.setter
    def pitch(self, pitch: Number):
        self._pitch = pitch

    @classmethod
    def from_llhap(
        cls, 
        lat: Number,
        lon: Number,
        height_agl: Number,
        azimuth: Number,
        pitch: Number
    ) -> AspectLocation:
        o = cls(lat, lon, height_agl, azimuth, pitch)
        return o

    @classmethod
    def from_tuple(
        cls, 
        inputs: tuple[Number, Number, Number, Number, Number]):
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
    
    def __eq__(self, other:Location) -> bool:
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
    def from_characteristics(cls,
                             name:str,
                             lat:float,
                             lon:float,
                             crs:str,
                             height_agl:float,
                             azimuth:float,
                             pitch:float) -> Location:
        a = locals()
        del a['azimuth']
        del a['pitch']
        del a['cls']
        del a['__class__']
        o = super(AspectLocation, cls).from_characteristics(**a)
        o.azimuth = azimuth
        o.pitch = pitch

        return o

    def to_dict(self) -> dict:
        odict = super().to_dict()
        odict['azimuth'] = self._azimuth
        odict['pitch'] = self._pitch
        return odict

# AspectLocation copy constructor
@AspectLocation.__init__.register(Location)
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

def location_from_dict(input: dict):
    input = copy.copy(input)
    classname = input.pop('class')
    constructor = _LOCATION_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('No location class found for ', classname)
    return constructor.from_dict(input)
