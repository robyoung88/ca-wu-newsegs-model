from abc import ABCMeta, abstractmethod

import numpy.typing as npt
import pandas as pd

from src.core import Location,RaisedLocation,AspectLocation
from src.core import TimeSpan

class NewsegsLocalEnvironment(metaclass=ABCMeta):
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

class NewsegsWiderEnvironment(metaclass=ABCMeta):
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
