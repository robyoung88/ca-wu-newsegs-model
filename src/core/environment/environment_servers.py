from abc import ABCMeta, abstractmethod
from typing import Any, Literal, Union, Sequence, SupportsFloat, overload
import re

import numpy as np
import numpy.typing as npt
import pandas as pd

from core import serialisation
from core import Location,RaisedLocation,AspectLocation
from core import TimeSpan
from util import classfuncs

RealArrayLike = Union[
    int, 
    float, 
    np.integer[Any], 
    np.floating[Any], 
    np.ndarray[tuple[Any, ...], np.dtype[np.integer[Any]]],
    np.ndarray[tuple[Any, ...], np.dtype[np.floating[Any]]]
]

LOCAL_ENVIRONMENT_MEASURE = Literal[
    'wind_speeds',
    'air_density',
    'horizontal_solar_flux',
    'external_temperature',
    'solar_flux_on_plane'
]

WIDER_ENVIRONMENT_MEASURE = Literal[
    'temperature',
    'horizontal_solar_flux'
]

class NewsegsLocalEnvironment(
    serialisation.SerialiseToDictMixin,
    metaclass = ABCMeta
):
    """Abstract base class for site-specific environmental data providers.

    This class defines the interface for local environmental data services that
    provide wind speeds, air density, solar flux, and temperature information
    for NewSEGS models.
    """
    _version = '0.0.1'
    _name = 'Local environment'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'Environment'

    @property
    def name(self) -> str:
        """Provider name."""
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        """Set the provider name.

        Args:
            name: New name for this environment data provider.
        """
        self._name = name

    @abstractmethod
    def get_wind_speeds(
        self, 
        location: RaisedLocation | Sequence[RaisedLocation], 
        timespan: TimeSpan,
    ) -> RealArrayLike:
        """Wind speed (m/s) for one or more locations.

        Args:
            location: Raised location or sequence of raised locations.
            timespan: Time span for the requested data.

        Returns:
            RealArrayLike: Wind speeds for the requested locations and times.
        """
        ...

    @abstractmethod
    def get_wind_timestep(self) -> pd.Timedelta:
        """Timestep for wind speed data."""
        ...

    @abstractmethod
    def get_air_density(
        self,
        location: RaisedLocation | Sequence[RaisedLocation], 
        timespan:TimeSpan
    ) -> RealArrayLike:
        """Air density (kg/m³) for one or more raised locations.

        Args:
            location: Raised location or sequence of raised locations.
            timespan: Time span for the requested data.

        Returns:
            RealArrayLike: Air density for the requested locations and times.
        """
        ...

    @abstractmethod
    def get_air_density_timestep(self) -> pd.Timedelta:
        """Timestep for air density data."""
        ...

    @abstractmethod
    def get_horizontal_solar_flux(
        self,
        location: Location | Sequence[Location],
        timespan: TimeSpan
    ) -> RealArrayLike:
        """Horizontal solar flux (W/m²) for one or more locations.

        Args:
            location: Location or sequence of locations.
            timespan: Time span for the requested data.

        Returns:
            RealArrayLike: Horizontal solar flux values.
        """
        ...

    @abstractmethod
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        """Timestep for horizontal solar flux data."""
        ...

    @abstractmethod
    def get_external_temperature(
        self,
        location: Location | Sequence[Location],
        timespan:TimeSpan
    ) -> RealArrayLike:
        """External temperature (°C) for one or more locations.

        Args:
            location: Location or sequence of locations.
            timespan: Time span for the requested data.

        Returns:
            RealArrayLike: External temperature values.
        """
        ...

    @abstractmethod
    def get_external_temperature_timestep(self) -> pd.Timedelta:
        """Timestep for external temperature data."""
        ...

    @abstractmethod
    def get_solar_flux_on_plane(
        self,
        location: AspectLocation | Sequence[AspectLocation],
        timespan: TimeSpan
    ) -> RealArrayLike:
        """Solar flux (W/m²) on a specified plane for one or more locations.

        Args:
            location: Aspect location or sequence of aspect locations.
            timespan: Time span for the requested data.

        Returns:
            RealArrayLike: Solar flux on plane values.
        """
        ...

    @abstractmethod
    def get_solar_flux_on_plane_timestep(self) -> pd.Timedelta:
        """Timestep for solar flux on plane data."""
        ...

    @overload
    def get_true_datetimes(
        self,
        measure: LOCAL_ENVIRONMENT_MEASURE,
        location: Location,
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        ...
    
    @overload
    def get_true_datetimes(
        self,
        measure: LOCAL_ENVIRONMENT_MEASURE,
        location: Sequence[Location],
        timespan: TimeSpan
    ) -> list[pd.DatetimeIndex]:
        ...
    
    @abstractmethod
    def get_true_datetimes(
        self,
        measure: LOCAL_ENVIRONMENT_MEASURE,
        location: Location | Sequence[Location],
        timespan: TimeSpan
    ) -> pd.DatetimeIndex | list[pd.DatetimeIndex]:
        """True datetimes associated with a local measure.

        Args:
            measure: Local environment measure identifier.
            location: Location or sequence of locations.
            timespan: Time span for the requested data.

        Returns:
            pd.DatetimeIndex | list[pd.DatetimeIndex]: 
                Datetimes for the requested measure and times;
                as list if location provided as a `Sequence`.
        """
        ...

    def __str__(self) -> str:
        """String representation of this instance."""
        return self.__class__.__name__ + ' v' + str(self._version)

class NewsegsWiderEnvironment(
    serialisation.SerialiseToDictMixin,
    metaclass = ABCMeta
):
    """Abstract base class for grid-wide environmental data providers.

    This class defines the interface for wider-environment data services that
    provide wider environment temperature and solar flux information for 
    NewSEGS models.
    """
    
    _version = '0.0.1'
    _name = 'Wider environment'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'Environment'

    @property
    def name(self) -> str:
        """Provider name."""
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        """Set the provider name.

        Args:
            name: New name for this environment provider.
        """
        self._name = name

    @abstractmethod
    def get_temperature(self, timespan: TimeSpan) -> RealArrayLike:
        """Temperatures (°C) for the requested time span.

        Args:
            timespan: Time span for the requested data.

        Returns:
            Data for the requested temperature measure. May include multiple series.
        """
        ...
        
    @abstractmethod
    def get_temperature_timestep(self) -> pd.Timedelta:
        """Timestep for temperature data."""
        ...

    @abstractmethod
    def get_horizontal_solar_flux(self, timespan: TimeSpan) -> RealArrayLike:
        """Horizontal solar flux for the requested time span.

        Args:
            timespan: Time span for the requested data.

        Returns:
            Data for the requested horizontal solar flux measure.
        """
        ...

    @abstractmethod
    def get_horizontal_solar_flux_timestep(self) -> pd.Timedelta:
        """Timestep for horizontal solar flux data."""
        ...

    @abstractmethod
    def get_true_datetimes(
        self,
        measure: WIDER_ENVIRONMENT_MEASURE,
        timespan: TimeSpan
    ) -> pd.DatetimeIndex:
        """True datetimes associated with a wider environment measure.

        Args:
            measure: Wider environment measure identifier.
            timespan: Time span for the requested data.

        Returns:
            pd.DatetimeIndex: Datetimes for the requested measure and times.
        """
        ...

    def __str__(self) -> str:
        """String representation of this instance."""
        return self.__class__.__name__ + ' v' + str(self._version)
