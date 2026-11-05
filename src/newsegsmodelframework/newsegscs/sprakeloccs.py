"""Provides implementation of NewsegsCS for the Sprake Location-Aware Model.

As `SprakeCS`, except that the space heating demand follows the air temperature at the location
of the module, served by the local environment server of the model, rather than the heating
degree day series of the Sprake model.

Deriving the space heating profile (see `sprake_thermal_model`) is slow, so, where the local
environment server allows it (`NewsegsLocalEnvironment.cache_identity`), the heating degree days
and the profile are kept in the persistent environment cache (see `environment_cache`). The
profile is cached per unit heat loss parameter, floor area and household, and scaled on use, so
that changing those parameters needs neither the temperatures nor the degree days.
"""
from typing import Callable, TypeVar, override

import numpy as np
import pandas as pd

from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.core.environment import environment_cache
from newsegsmodelframework.core.environment.environment_servers import NewsegsLocalEnvironment
from newsegsmodelframework.newsegscs.sprake_thermal_model import (
    HDD_BASE_TEMPERATURE,
    get_spaceheat_energy_consumption,
    heating_degree_days_from_temperature,
)
from newsegsmodelframework.newsegscs.sprakecs import SprakeCS

T = TypeVar('T')

# Part of the cache keys of the degree days and profiles; change it when their derivation
# changes, so that entries derived the old way are not used.
_DERIVATION_VERSION = '0.0.1'


class SprakeLocCS(SprakeCS):
    """Implementation of NewsegsCS for the Sprake Location-Aware Model.

    The configuration is that of `SprakeCS`; `timeseries_hdd_start` and `timeseries_model_start`
    are not used.
    """

    _name = 'Sprake Location-Aware Consumption and Storage Module'

    def _local_env(self) -> NewsegsLocalEnvironment:
        if self.model is None:
            raise ValueError('Space heating requires a model to serve the local environment')
        return self.model.local_env

    def _cached(
        self,
        local_env: NewsegsLocalEnvironment,
        measure: str,
        timespan: modtimespan.TimeSpan,
        compute: Callable[[], T],
        **params,
    ) -> T:
        identity = local_env.cache_identity
        if identity is None:
            return compute()
        key = environment_cache.environment_cache_key(
            identity, measure, self.location, timespan, version = _DERIVATION_VERSION, **params
        )
        lat, lon = environment_cache.round_location(self.location)
        return environment_cache.get_or_set(
            key, compute, description = f'{measure.replace("_", " ")} for ({lat}, {lon})'
        )

    def get_heating_degree_days(self, timespan: modtimespan.RegTimeSpan) -> pd.DataFrame:
        """Heating degree days of each day, from the air temperature at the location of the module.

        Args:
            timespan: The period of time.

        Returns:
            Dataframe of the `timestamp` of each day and its degree days, `hdd_15_5`.
        """
        local_env = self._local_env()

        def compute() -> pd.DataFrame:
            temperatures = np.asarray(local_env.get_external_temperature(self.location, timespan))
            datetimes = local_env.get_true_datetimes('external_temperature', self.location, timespan)
            if len(temperatures) != len(datetimes):
                raise ValueError(
                    f'The local environment served {len(temperatures)} temperatures at {len(datetimes)} datetimes'
                )
            return heating_degree_days_from_temperature(datetimes, temperatures)

        return self._cached(
            local_env, 'heating_degree_days', timespan, compute,
            base_temperature = HDD_BASE_TEMPERATURE
        )

    def get_unit_spaceheat_profile(self, timespan: modtimespan.RegTimeSpan) -> np.ndarray:
        """Space heating consumption at each timestep, per unit heat loss parameter, floor area and household.

        Args:
            timespan: The period of time, with the timestep of the model.

        Returns:
            Array of consumption.
        """
        def compute() -> np.ndarray:
            datetimes = timespan.to_pandas()
            # Each consumption is over the timestep ending at its datetime, so the first falls in
            # the day before the time span. Its consumption is zero, but the day must have degree days.
            days = pd.date_range(
                (datetimes[0] - pd.Timedelta(1, 'm')).floor('D'),
                (datetimes[-1] - pd.Timedelta(1, 'm')).floor('D'),
                freq = 'D'
            )
            hdd = (
                self.get_heating_degree_days(timespan)
                .set_index('timestamp')
                .reindex(days)
                .bfill()
                .ffill()
                .rename_axis('timestamp')
                .reset_index()
            )
            cons = get_spaceheat_energy_consumption(datetimes, hlp = 1., gfa = 1., hdd = hdd)
            return cons['consumption'].to_numpy()

        return self._cached(
            self._local_env(), 'unit_spaceheat_profile', timespan, compute,
            timestep = str(timespan.timestep)
        )

    @override
    def get_spaceheat_consumption(self, timespan: modtimespan.RegTimeSpan) -> np.ndarray:
        """Electricity consumption for space heating at each timestep.

        The unit profile, from the air temperature at the location of the module, scaled by the
        heat loss parameter, the floor area and the number of households.

        Args:
            timespan: The period of time, with the timestep of the model.

        Returns:
            Array of consumption.
        """
        return self.get_unit_spaceheat_profile(timespan) * self.hlp * self.gfa * self.n_households
