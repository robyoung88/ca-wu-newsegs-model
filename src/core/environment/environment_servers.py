from abc import ABCMeta, abstractmethod
from typing import Literal
import re

import numpy.typing as npt
import pandas as pd

from src.core import Location,RaisedLocation,AspectLocation
from src.core import TimeSpan
from src.util import classfuncs

class NewsegsLocalEnvironment(metaclass=ABCMeta):
    """
    Serves site-specific environmental data to a NewSEGS model.
    """
    _version = '0.0.1'
    _name = 'Local environment'

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @abstractmethod
    def get_wind_speeds(self, 
                        location:RaisedLocation|tuple[RaisedLocation, ...]|list[RaisedLocation], 
                        timespan:TimeSpan
                        ) -> npt.ArrayLike:
        ...

    @abstractmethod

    def get_wind_timestep(self) -> pd.Timedelta|None:
        ...

    @abstractmethod
    def get_air_density(self,
                        location:RaisedLocation|tuple[RaisedLocation, ...]|list[RaisedLocation], 
                        timespan:TimeSpan
                        ) -> npt.ArrayLike:
        ...

    @abstractmethod
    def get_air_density_timestep(self) -> pd.Timedelta|None:
        ...

    @abstractmethod
    def get_horizontal_solar_flux(self,
                                  location:Location|tuple[Location, ...]|list[Location],
                                  timespan:TimeSpan
                                  ) -> npt.ArrayLike:
        ...

    @abstractmethod
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta|None:
        ...

    @abstractmethod
    def get_external_temperature(self,
                                 location:Location|tuple[Location, ...]|list[Location],
                                 timespan:TimeSpan
                                 ) -> npt.ArrayLike:
        ...

    @abstractmethod
    def get_external_temperature_timestep(self) -> pd.Timedelta|None:
        ...

    @abstractmethod
    def get_solar_flux_on_plane(self,
                                location:AspectLocation|tuple[AspectLocation, ...]|list[AspectLocation],
                                timespan:TimeSpan
                                ) -> npt.ArrayLike:
        ...

    @abstractmethod
    def get_solar_flux_on_plane_timestep(self) -> pd.Timedelta:
        ...
    
    @abstractmethod
    def get_true_datetimes(
        self,
        measure: Literal[
            'wind_speeds',
            'air_density',
            'horizontal_solar_flux',
            'external_temperature',
            'solar_flux_on_plane'
        ],
        location: Location|tuple[Location, ...]|list[Location],
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        ...
    
    #def __getstate__(self):
    #    """
    #    Return the state for pickling.
    #    
    #    May be overwritten to provide state as other than a dict; for now, it
    #    makes sense to.
    #    """
    #    odict = {
    #        'name': self._name
    #    }
    #    return odict

    def __str__(self) -> str:
        return classfuncs.get_class(self) + ' v' + str(self._version)

class NewsegsWiderEnvironment(metaclass=ABCMeta):
    """
    Serves grid-wide environmental data to a NewSEGS model.
    """
    
    _version = '0.0.1'
    _name = 'Wider environment'

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @abstractmethod
    def get_temperature(self, timespan:TimeSpan):
        ...
    @abstractmethod
    def get_temperature_timestep(self) -> pd.Timedelta|None:
        ...

    @abstractmethod
    def get_horizontal_solar_flux(self, timespan:TimeSpan):
        ...
    @abstractmethod
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta|None:
        ...

    @abstractmethod
    def get_true_datetimes(
        self,
        measure: Literal[
            'temperature',
            'horizontal_solar_flux'
        ],
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        ...

    def __str__(self) -> str:
        return re.search(r"\.(\w+)\'>$", str(type(self))).group(1) + ' v' + str(self._version)
