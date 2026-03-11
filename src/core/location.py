from __future__ import annotations

import re
from pyproj import Transformer

# -----------------------------------------------------------------------------
# Ways of storing location information

class Location:
    _default_name = "Site 1"
    def __init__(self, other:Location|None=None) -> None:
        """
            Initialise a Location using another Location
        """
        if not(other is None):
            if not (isinstance(other, Location)):
                raise ValueError("location " + str(other) + " is not a Location object")

            latlon = other.latlon
            self._lat = latlon[0]
            self._lon = latlon[1]
            self._name = other.name
        else:
            self._lat = 53.46
            self._lon = -3.80
            self._name = self._default_name
        
        self._crs = "EPSG:4326"

    @property
    def lat(self):
        return self._lat
    
    @lat.setter
    def lat(self, lat):
        self._lat = lat

    @property
    def lon(self):
        return self._lon
    
    @lon.setter
    def lon(self, lon):
        self._lon = lon

    @property
    def latlon(self) :
        return (self._lat, self._lon)
    
    def get_latlon(self) -> tuple:
        return (self._lat, self._lon)

    @latlon.setter
    def latlon(self, latlon):
        self._lat = latlon[0]
        self._lon = latlon[1]
    
    def set_lat_lon(self, lat, lon):
        self._lat = lat
        self._lon = lon

    @property
    def crs(self):
        return self._crs

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name    

    def get_osgb(self) -> tuple:
        trans_togb = Transformer.from_crs(self.crs, "EPSG:27700")
        return trans_togb.transform(self.lat, self.lon)

    @classmethod
    def from_lat_lon(cls, lat:int|float, lon:int|float) -> Location:
        o = cls()
        o.lat = lat
        o.lon = lon
        return o
    
    @classmethod
    def from_tuple(cls, inputs:tuple[int|float, int|float]):
        o = cls()
        o.lat, o.lon = inputs
        return o

    @classmethod
    def from_osgb(cls, easting:int|float, northing:int|float) -> Location:
        trans_tolatlon = Transformer.from_crs("EPSG:27700", "EPSG:4326")
        coord = trans_tolatlon.transform(easting, northing)
        return cls.from_lat_lon(coord[0], coord[1])

    def __str__(self):
        return "(" + str(self.lat) + ", " + str(self.lon) + ")"
    
    def __eq__(self, other:Location) -> bool:
        return (self.lat == other.lat) and (self.lon == other.lon) and (self.crs == other.crs)

    def __neq__(self, other:Location) -> bool:
        return not(self == other)

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

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             lat:float,
                             lon:float,
                             crs:str) -> Location:
        o = cls()
        
        o.name = name
        o.lat = lat
        o.lon = lon
        o._crs = crs
        
        return o

    def to_dict(self) -> dict:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'lat': self._lat,
            'lon': self._lon,
            'crs': self._crs
        }
        return odict

    @classmethod
    def from_dict(cls, input:dict) -> Location:
        return cls.from_characteristics(**input)

class RaisedLocation(Location):
    def __init__(self, other:Location|RaisedLocation|None=None) -> None:
        super().__init__(other)
        if not (other is None):
            if isinstance(other, RaisedLocation):
                self._height = other.height_agl
            else:
                self._height = 0.0
    
    @property
    def height_agl(self):
        return self._height
    
    @height_agl.setter
    def height_agl(self, height:int|float):
        self._height = height

    @classmethod
    def from_lat_lon_height(cls, lat:int|float, lon:int|float, height:int|float):
        o = cls()
        o.lat = lat
        o.lon = lon
        o.height_agl = height
        return o

    @classmethod
    def from_tuple(cls, inputs:tuple[int|float,int|float,int|float]):
        o = cls()
        o.lat, o.lon, o.height_agl = inputs
        return o

    def __str__(self):
        return "(" + str(self.lat) + ", " + str(self.lon) + "), height: " + str(self.height_agl) + " m AGL"
    
    def __eq__(self, other:Location) -> bool:
        if isinstance(other, RaisedLocation):
            return super().__eq__(other) and (self.height_agl == other.height_agl)
        else:
            return super().__eq__(other)

    def __neq__(self, other:Location) -> bool:
        if isinstance(other, RaisedLocation):
            return super().__neq__(other) or (self.height_agl != other.height_agl)
        else:
            return super().__neq__(other)

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             lat:float,
                             lon:float,
                             crs:str,
                             height_agl:float) -> Location:
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

class AspectLocation(RaisedLocation):
    def __init__(self, other:Location|None=None) -> None:
        super().__init__(other)
        if not (other is None):
            if isinstance(other, AspectLocation):
                self._azimuth = other.azimuth
                self._pitch = other.pitch
            else:
                self._azimuth = 180.0
                self._pitch = 90.0
    
    @property
    def azimuth(self):
        return self._azimuth
    
    @azimuth.setter
    def azimuth(self, az:int|float):
        self._azimuth = az % 360.0
    
    @property
    def pitch(self):
        return self._pitch
    
    @pitch.setter
    def pitch(self, pitch:int|float):
        self._pitch = pitch

    @classmethod
    def from_llhap(cls, lat:int|float, lon:int|float, height:int|float, azimuth:int|float, pitch:int|float):
        o = cls()
        o.lat = lat
        o.lon = lon
        o.height_agl = height
        o.azimuth = azimuth
        o.pitch = pitch
        return o

    @classmethod
    def from_tuple(cls, inputs:tuple[int|float,int|float,int|float,int|float,int|float]):
        """
            Tuple should consist of

            - latitude
            - longitude
            - height agl
            - azimuth
            - pitch
        """
        o = cls()
        o.lat, o.lon, o.height_agl, o.azimuth, o.pitch = inputs
        return o
    
    def __str__(self):
        return "(" + str(self.lat) + ", " + str(self.lon) + "), height: " + str(self.height_agl) + " m AGL, azimuth: " + str(self.azimuth) + "°, pitch: " + str(self.pitch) + "°"
    
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

location_constructors = {
    'Location': Location,
    'RaisedLocation': RaisedLocation,
    'AspectLocation': AspectLocation
}

def location_from_dict(input:dict):
    classname = input.pop('class')
    constructor = location_constructors.get(classname, None)
    if constructor is None:
        return constructor
    return constructor.from_dict(input)
