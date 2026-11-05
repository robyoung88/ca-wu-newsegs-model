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
from functools import singledispatchmethod, lru_cache
from pyproj import Transformer

from pvlib.location import Location as _PVLibLocation
from pvlib.pvsystem import PVSystem as _PVSystem

from newsegsmodelframework.core import serialisation
from newsegsmodelframework.util import classfuncs

T = TypeVar('T')
Real = SupportsFloat

class Location(serialisation.StateSerialiseToDictMixin):
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
    _name = ''
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
        """Initialise a Location instance.

        This method uses singledispatch and so requires an unnamed first
        argument which is not `None`. Concrete overloads are:

        - __init__(self, lat: Real, lon: Real, name: str | None = None)
            Construct from explicit latitude and longitude real numeric values.
        
        - __init__(self, other: Location)
            Construct as a copy from an existing Location instance.

        A TypeError is raised if an unsupported first argument is provided.

        For initiation without a first argument, use `Location.from_none()`

        Args:
            lat (float | int): Latitude in decimal degrees.
            lon (float | int): Longitude in decimal degrees.
            name (str): Optional name for location

            other (Location): Reference Location

        Raises:
            TypeError: If first argument is not a Real numeric value or a 
                        Location

        """
        raise TypeError('`lat` must be a latitude or location, is %s', lat)
    
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
        """float: Latitude of Location (decimal degrees)."""
        return self._lat
    
    @lat.setter
    def lat(self, lat: Real):
        self._lat = float(lat)

    @property
    def lon(self) -> float:
        """float: Longitude of Location (decimal degrees)."""
        return self._lon
    
    @lon.setter
    def lon(self, lon: Real):
        self._lon = float(lon)

    @property
    def latlon(self) -> tuple[float, float]:
        """tuple[float, float]: (latitude, longitude) of Location."""
        return (self._lat, self._lon)
    
    def get_latlon(self) -> tuple[float, float]:
        """The (latitude, longitude) co-ordinates of the Location

        Returns:
            tuple[float, float]: (latitude, longitude) in decimal degrees.
        """
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
        """Set the latitude and longitude of the site.

        If the first argument is a tuple, then it will be assumed to contain 
        the latitude at index 0 and longitude at index 1. Otherwise, `lon` must
        not be `None`.
        Args:
            lat (Real | tuple[Real, Real]): Latitude or tuple of (latitude, longitude) (decimal degrees).
            lon (Real | None, optional): Longitude (decimal degrees), if first argument not a tuple. Defaults to None.

        Raises:
            TypeError: If `lon` is `None` but `lat` is not a tuple.
        """
        if isinstance(lat, tuple):
            self._lat = float(lat[0])
            self._lon = float(lat[1])
        else:
            if lon is None:
                raise TypeError('If not setting latlon via a tuple, `lon` must be provided')
            self._lat = float(lat)
            self._lon = float(lon)

    @property
    def crs(self) -> str:
        """str: The coordinate reference system in use."""
        return self._crs

    @property
    def name(self) -> str:
        """str: The name of the Location; empty until the user names it."""
        return self._name

    @name.setter
    def name(self, name: str) -> None:
        self._name = name    

    @property
    def display_name(self) -> str:
        """str: The name to show the user: the name, or, while it has none, its co-ordinates (`Site at <lat>, <lon>`)."""
        if self._name:
            return self._name
        return f'Site at {self._lat:.3f}, {self._lon:.3f}'

    def get_osgb(self) -> tuple[float, float]:
        """Location as OSGB36 co-ordinates

        Returns:
            tuple[float, float]: (eastings, northings) of OSGB co-ordinates (m).
        """
        trans_togb = Transformer.from_crs(self.crs, "EPSG:27700")
        return trans_togb.transform(self.lat, self.lon)

    @classmethod
    def from_lat_lon(cls, lat: Real, lon: Real) -> Location:
        """Construct Location from latitude and longitude pair.

        Args:
            lat (Real): Latitude of Location (decimal degrees)
            lon (Real): Longitude of Location (decimal degrees)

        Returns:
            Location: Instance storing location information with default name.
        """
        o = cls.from_none()
        o.lat = lat
        o.lon = lon
        return o
    
    @classmethod
    def from_tuple(cls, inputs: tuple[Real, Real]) -> Location:
        """Construct Location from (latitude, longitude) tuple.


        Args:
            inputs (tuple[Real, Real]): (latitude, longitude) (decimal degrees)

        Returns:
            Location: Instance storing location information with default name.
        """
        o = cls.from_none()
        o.lat, o.lon = inputs
        return o

    @classmethod
    def from_osgb(
        cls, 
        easting: Real, 
        northing: Real
    ) -> Location:
        """Construct Location from easting and northing OSGB36 pair.

        Args:
            easting (Real): OSGB36 easting (m)
            northing (Real): OSGB36 northing (m)

        Returns:
            Location: Instance storing location information with default name.
        """
        trans_tolatlon = Transformer.from_crs("EPSG:27700", cls._crs)
        coord = trans_tolatlon.transform(easting, northing)
        return cls.from_lat_lon(coord[0], coord[1])

    @classmethod
    def from_characteristics(
        cls: Type[T],
        lat: Real,
        lon: Real,
        crs: str = 'EPSG:4326',
        name: str | None = None,
    ) -> T:
        """Construct a Location from explicit characteristics.

        Args:
            lat: Latitude of the location (decimal degrees).
            lon: Longitude of the location (decimal degrees).
            crs: Coordinate reference system of the latitude and longitude.
            name: Name of the location.

        Returns:
            The location.
        """

        o = cls.from_none() # pyright: ignore[reportAttributeAccessIssue]
        
        o._crs = crs
        o.lat = lat
        o.lon = lon

        if name:
            o.name = name

        return o
    
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
    """A geographic location with an above-ground level height component.
    
    Extends Location to include height_agl (height above ground level).
    Useful for representing locations with elevation data, such as wind turbines
    or sensor mounting heights.
    """
    
    _height = 0.

    @singledispatchmethod
    def __init__(
        self,
        lat: Real | Location,
        lon: Real | None = None,
        height_agl: Real | None = None,
        name: str | None = None
    ) -> None:
        """Initialise a RaisedLocation instance.
        
        This method uses singledispatch and so requires an unnamed first
        argument which is not `None`. Concrete overloads are:

        - __init__(self, lat: Real, lon: Real, height_agl: Real = 0., name: str | None = None)
            Construct from explicit latitude, longitude and height values.
        
        - __init__(self, other: Location)
            Construct from an existing Location instance.

        A ValueError is raised if an unsupported first argument is provided.

        Args:
            lat (Real | Location): Latitude in decimal degrees or a Location instance.
            lon (Real | None): Longitude in decimal degrees.
            height_agl (Real | None): Height above ground level in meters.
            name (str | None): Optional name for location.

        Raises:
            ValueError: If first argument is not a Real numeric value or a Location.
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
        """Construct from explicit latitude, longitude and height values.
        
        Args:
            lat (Real): Latitude in decimal degrees.
            lon (Real): Longitude in decimal degrees.
            height_agl (Real): Height above ground level in meters. Defaults to 0.
            name (str | None): Optional name for location.
        """
        super().__init__(lat, lon, name = name)
        self._height = float(height_agl)
    
    @property
    def height_agl(self) -> float:
        """Height above ground level (m).
        """
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
    ) -> RaisedLocation:
        """Construct RaisedLocation from latitude, longitude and height.
        
        Args:
            lat (Real): Latitude in decimal degrees.
            lon (Real): Longitude in decimal degrees.
            height_agl (Real): Height above ground level in meters.

        Returns:
            RaisedLocation: Instance with specified coordinates and height.
        """
        o = cls(lat, lon, height_agl)
        return o

    @classmethod
    def from_tuple(
        cls, 
        inputs: tuple[Real, Real] | tuple[Real, Real, Real]
    ) -> RaisedLocation:
        """Construct RaisedLocation from tuple of coordinates.
        
        Args:
            inputs (tuple[Real, Real] | tuple[Real, Real, Real]): 
                Either (latitude, longitude) or (latitude, longitude, height_agl).

        Returns:
            RaisedLocation: Instance with coordinates from tuple.
        """
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
        """Construct RaisedLocation from detailed characteristics.
        
        Args:
            *args: Positional arguments passed to parent Location.from_characteristics.
            height_agl (Real): Height above ground level in meters.
            **kwargs: Keyword arguments passed to parent Location.from_characteristics.

        Returns:
            T: RaisedLocation instance with specified characteristics.
        """
        o = super().from_characteristics(*args, **kwargs)
        o.height_agl = height_agl
        
        return o

    # def to_dict(self) -> dict:
    #     odict = super().to_dict()
    #     odict['height_agl'] = self._height
    #     return odict

# RaisedLocation copy constructor
@RaisedLocation.__init__.register(Location) # pyright: ignore[reportFunctionMemberAccess]
def RaiseLocation_from_other(
    self,
    other: Location
) -> None:
    """Initialise a RaisedLocation from another Location.
    
    If the source Location is a RaisedLocation, its height_agl is copied.
    Otherwise, height_agl defaults to 0.
    
    Args:
        other (Location): Source Location to copy from.
    """
    latlon = other.latlon
    self.set_latlon(latlon)
    if isinstance(other, RaisedLocation):
        self.height_agl = other.height_agl
    self._name = other.name

class AspectLocation(RaisedLocation):
    """A geographic location with height, azimuth and pitch components.
    
    Extends RaisedLocation to include azimuth (compass direction) and pitch
    (tilt angle) properties. Useful for representing oriented objects like
    solar panels, wind turbines, or antennas.
    """
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
        """Initialise an AspectLocation instance.
        
        This method uses singledispatch and so requires an unnamed first
        argument which is not `None`. Concrete overloads are:

        - __init__(self, lat: Real, lon: Real, height_agl: Real = 0., azimuth: Real = 180., pitch: Real = 90., name: str | None = None)
            Construct from explicit latitude, longitude, height, azimuth and pitch.
        
        - __init__(self, other: Location)
            Construct from an existing Location instance.

        A ValueError is raised if an unsupported first argument is provided.

        Args:
            lat (Real | Location): Latitude in decimal degrees or a Location instance.
            lon (Real | None): Longitude in decimal degrees.
            height_agl (Real | None): Height above ground level in meters.
            azimuth (Real | None): Azimuth angle in degrees (0-360).
            pitch (Real | None): Pitch angle in degrees.
            name (str | None): Optional name for location.

        Raises:
            ValueError: If first argument is not a Real numeric value or a Location.
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
        """Construct from explicit latitude, longitude, height, azimuth and pitch.
        
        Args:
            lat (Real): Latitude in decimal degrees.
            lon (Real): Longitude in decimal degrees.
            height_agl (Real): Height above ground level in meters. Defaults to 0.
            azimuth (Real): Azimuth angle in degrees (0-360). Defaults to 180.
            pitch (Real): Pitch angle in degrees. Defaults to 90.
            name (str | None): Optional name for location.
        """
        super().__init__(lat, lon, height_agl = height_agl, name = name)
        self.azimuth = float(azimuth)
        self.pitch = float(pitch)
    
    @property
    def azimuth(self) -> float:
        """Compass direction that the surface faces (degrees).
        """
        return self._azimuth
    
    @azimuth.setter
    def azimuth(self, azimuth: Real):
        self._azimuth = float(azimuth) % 360.0
    
    @property
    def pitch(self) -> float:
        """Tilt of the surface from horizontal (degrees).
        """
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
        """Construct AspectLocation from latitude, longitude, height, azimuth and pitch.
        
        Args:
            lat (Real): Latitude in decimal degrees.
            lon (Real): Longitude in decimal degrees.
            height_agl (Real): Height above ground level in meters.
            azimuth (Real): Azimuth angle in degrees (0-360).
            pitch (Real): Pitch angle in degrees.

        Returns:
            AspectLocation: Instance with specified location and orientation.
        """
        o = cls(lat, lon, height_agl, azimuth, pitch)
        return o

    @classmethod
    def from_tuple(
        cls, 
        inputs: tuple[Real, Real] | tuple[Real, Real, Real] | tuple[Real, Real, Real, Real, Real]
    ) -> AspectLocation:
        """Construct AspectLocation from tuple of values.
        
        Args:
            inputs (tuple[Real, Real] | tuple[Real, Real, Real] | tuple[Real, Real, Real, Real, Real]):
                Tuple consisting of:
                - latitude
                - longitude
                - height_agl (optional)
                - azimuth (optional)
                - pitch (optional)

        Returns:
            AspectLocation: Instance with values from tuple.
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
        """Construct AspectLocation from detailed characteristics.
        
        Args:
            *args: Positional arguments passed to parent RaisedLocation.from_characteristics.
            azimuth (Real): Azimuth angle in degrees (0-360).
            pitch (Real): Pitch angle in degrees.
            **kwargs: Keyword arguments passed to parent RaisedLocation.from_characteristics.

        Returns:
            T: AspectLocation instance with specified characteristics.
        """
        o = super().from_characteristics(*args, **kwargs)
        o.azimuth = azimuth
        o.pitch = pitch

        return o

    # def to_dict(self) -> dict:
    #     odict = super().to_dict()
    #     odict['azimuth'] = self._azimuth
    #     odict['pitch'] = self._pitch
    #     return odict

# AspectLocation copy constructor
@AspectLocation.__init__.register(Location) # pyright: ignore[reportFunctionMemberAccess]
def AspectLocation_from_other(
    self,
    other: Location
) -> None:
    """Initialise an AspectLocation from another Location.
    
    If the source Location is a RaisedLocation, its height_agl is copied.
    If the source Location is an AspectLocation, its azimuth and pitch are copied.
    Otherwise, height_agl defaults to 0 and azimuth/pitch use class defaults.
    
    Args:
        other (Location): Source Location to copy from.
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

def location_from_dict(input: dict[str, Any]) -> Location:
    """Create a Location instance from its dictionary representation.
    
    Args:
        input (dict[str, Any]): Dictionary with 'class' key and location properties.
                               Expected from Location.to_dict() method.

    Returns:
        Location: Appropriate Location subclass instance.

    Raises:
        ValueError: If 'class' key specifies an unknown location class.
    """
    input = copy.copy(input)
    classname = input.pop('class')
    constructor = _LOCATION_CONSTRUCTORS.get(classname, None)
    if constructor is None:
        raise ValueError('No location class found for ', classname)
    return constructor.from_dict(input)

class PVLibLocation(
    serialisation.StateSerialiseToDictMixin,
    _PVLibLocation
):
    """Extends `pvlib.location.Location` with `SerialiseToDictMixin`"""
    _constructor_class = 'PVLib'

    @override
    def get_solarposition(self, times, pressure=None, temperature=12, **kwargs):
        #method = kwargs.get('method', 'nrel_numba')
        method = 'nrel_numba'
        t0 = times[0]
        periods = len(times)
        freq = (times[1] - times[0])

        return cached_get_solarposition(t0, periods, freq, self.latitude, self.longitude, method)

class PVLibPVSystem(
    serialisation.StateSerialiseToDictMixin,
    _PVSystem
):
    """Extends `pvlib.pvsystem.PVSystem` with `SerialiseToDictMixin`"""
    _constructor_class = 'PVLib'

@lru_cache
def cached_get_solarposition(t0, periods, freq, lat, lon, method: str = 'nrel_numba'):
    """Solar position (cached) at times given by a start, number of periods and frequency.

    Uses `pvlib.solarposition.get_solarposition`; results are cached because they are requested repeatedly for the same site and period.

    Args:
        t0: Start time.
        periods: Number of periods.
        freq: Frequency of the periods (a pandas offset alias).
        lat: Latitude (degrees).
        lon: Longitude (degrees).
        method: The solar position algorithm of pvlib.

    Returns:
        Dataframe of solar position.
    """
    from pvlib.solarposition import get_solarposition
    import pandas as pd
    times = pd.date_range(start = t0, periods = periods, freq = freq)
    return get_solarposition(times, lat, lon, method = method)
