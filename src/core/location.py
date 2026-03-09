from __future__ import annotations

# -----------------------------------------------------------------------------
# Ways of storing location information

class Location:
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
        
        self._crs = 

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
    def latlon(self):
        return (self._lat, self._lon)
    
    @latlon.setter
    def latlon(self, latlon):
        self._lat = latlon[0]
        self._lon = latlon[1]
    
    def set_coord(self, lat, lon):
        self._lat = lat
        self._lon = lon

