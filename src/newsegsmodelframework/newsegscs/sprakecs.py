"""Provides implementation of NewsegsCS for Sprake Model."""
from __future__ import annotations
from dataclasses import asdict
import datetime
import os
import copy
from typing import Union, cast, override
from functools import lru_cache, singledispatchmethod

import numpy as np
import pandas as pd

from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.core.trackeddata import revision_dataclass
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.newsegscs import NewsegsCS, NewsegsCSConfig

from newsegsmodelframework import STATICDATA
from config import environment
from newsegsmodelframework.newsegscs.sprake_thermal_model import TIMESERIES_DEGREE_DAYS
from newsegsmodelframework.newsegsvariable.variable import ScalarNumParam
AnyNumber = Union[ScalarNumParam]#, Number]

class SprakeCSResult(NewsegsModuleResult):
    """Constainer for results of SprakeCS Module."""
    def __init__(
        self,
        *args,
        timespan: modtimespan.RegTimeSpan,
        domestic_consumption:np.ndarray[tuple[int,int], np.dtype[np.number]],
        storage_import:np.ndarray[tuple[int], np.dtype[np.number]],
        storage_export:np.ndarray[tuple[int], np.dtype[np.number]],
        storage_loss:np.ndarray[tuple[int], np.dtype[np.number]],
        grid_import:np.ndarray[tuple[int], np.dtype[np.number]],
        grid_export:np.ndarray[tuple[int], np.dtype[np.number]],
        storage_soc:np.ndarray[tuple[int], np.dtype[np.number]],
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        
        # Meter values - i.e. import/export
        self._timespan = copy.copy(timespan)
        self.set_domestic_consumption(domestic_consumption)
        self.set_storage_import(storage_import)
        self.set_storage_export(storage_export)
        self.set_storage_loss(storage_loss)
        self.set_grid_import(grid_import)
        self.set_grid_export(grid_export)

        # DSM values - i.e. system state values
        self.set_storage_soc(storage_soc)

    def get_timespan(self) -> modtimespan.RegTimeSpan:
        """The time span of the result.

        Returns:
            The time span.
        """
        return self._timespan

    @property
    def meters(self) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        """
        Metered electricity:
        domestic imports by
            - appliances
            - DHW
            - Space heating
            - EV Charging
        
        kWh to storage (pre-losses)
        kWh from storage (after losses)
        kWh lost in storage (computed at time of storage)

        kWh to grid
        kWh from grid

        As Sprake model calculates net flow over its timestep, it is not possible to have both
        a > 0 charge to storage and > 0 charge from storage in the same timestep.

        As Sprake model calculates net flow over its timestep, it is not possible to have both
        a >0 energy to grid and >0 energy from grid in the same timestep.

        Storage is assumed capable of charge at infinite rate regardless of SoC.

        All metered values are delta over previous timestep; i.e. all index-0 values are expected to be 0
        """

        minlength = np.min((
            self._domestic_consumption.shape[1],
            len(self._storage_import),
            len(self._storage_export),
            len(self._storage_loss),
            len(self._grid_import),
            len(self._grid_export)
        ))

        n_domestic_vectors = self._domestic_consumption.shape[0]
        n_vectors = n_domestic_vectors + 5
        o_arr = np.empty((n_vectors, minlength), dtype=np.float64)

        o_arr[0:n_domestic_vectors, :] = self._domestic_consumption[:,0:minlength]
        o_arr[n_domestic_vectors, :] = self._storage_import[0:minlength]
        o_arr[n_domestic_vectors + 1, :] = self._storage_export[0:minlength]
        o_arr[n_domestic_vectors + 2, :] = self._storage_loss[0:minlength]
        o_arr[n_domestic_vectors + 3, :] = self._grid_import[0:minlength]
        o_arr[n_domestic_vectors + 4, :] = self._grid_export[0:minlength]

        return o_arr

    @property
    def dsm(self) -> np.ndarray[tuple[int,int], np.dtype[np.number]]:
        """
        DSM signal.

        For this module, the signal only encodes the current state of charge of the storage system in kWh
        """
        minlength = len(self._storage_soc)

        o_arr = np.empty((1, minlength), dtype = np.float64)
        o_arr[0, :] = self._storage_soc

        return o_arr

    def get_meter_names(self):
        """Names of the meters: the import of each load, and the storage and grid flows.

        Returns:
            The names.
        """
        return ('appliance_import', 'dhw_import', 'spaceheat_import', 'evcharge_import',
                'storage_import', 'storage_export', 'storage_loss',
                'grid_import', 'grid_export')
    
    def get_meter_types(self):
        """Types of the meters: load, storage import and export, loss, and grid import and export.

        Returns:
            The types.
        """
        return ('load', 'load', 'load', 'load',
                'import_storage', 'export_storage', 'loss',
                'import', 'export')

    def get_dsm_names(self):
        """Names of the DSM values: the storage state of charge.

        Returns:
            The names.
        """
        return ('storage_soc',)

    # REVIEW (unreferenced): nothing calls `get_dsm_types` (it implements the abstract `NewsegsModuleResult.get_dsm_types`).
    def get_dsm_types(self):
        """Types of the DSM values; the state of charge is a system state.

        Returns:
            The types.
        """
        return ('system_state',)

    def set_domestic_consumption(self, domestic_consumption:np.ndarray[tuple[int,int], np.dtype[np.number]]):
        """Set the consumption of each load.

        Args:
            domestic_consumption: Array of the consumption of each load (appliances, hot water, space heating, EV charging) at each timestep.
        """
        self._domestic_consumption = domestic_consumption

    def set_storage_import(self, storage_import:np.ndarray[tuple[int], np.dtype[np.number]]):
        """Set the energy imported to storage.

        Args:
            storage_import: Energy imported to storage at each timestep.
        """
        self._storage_import = storage_import

    def set_storage_export(self, storage_export:np.ndarray[tuple[int], np.dtype[np.number]]):
        """Set the energy exported from storage.

        Args:
            storage_export: Energy exported from storage at each timestep.
        """
        self._storage_export = storage_export

    def set_storage_loss(self, storage_loss:np.ndarray[tuple[int], np.dtype[np.number]]):
        """Set the energy lost by storage.

        Args:
            storage_loss: Energy lost by storage at each timestep.
        """
        self._storage_loss = storage_loss

    def set_grid_import(self, grid_import:np.ndarray[tuple[int], np.dtype[np.number]]):
        """Set the energy imported from the grid.

        Args:
            grid_import: Energy imported from the grid at each timestep.
        """
        self._grid_import = grid_import

    def set_grid_export(self, grid_export:np.ndarray[tuple[int], np.dtype[np.number]]):
        """Set the energy exported to the grid.

        Args:
            grid_export: Energy exported to the grid at each timestep.
        """
        self._grid_export = grid_export

    def set_storage_soc(self, storage_soc:np.ndarray[tuple[int], np.dtype[np.number]]):
        """Set the state of charge of storage.

        Args:
            storage_soc: State of charge of storage at each timestep.
        """
        self._storage_soc = storage_soc

# Function wrappers for consumption models
# Todo: Consider how to re-wrap these, as DatetimeIndex[es] and Series are unhashable
# so we can't get a cache working.

@lru_cache
def _get_sprake_appliance_consumption_reference_data():
    return (
        pd.read_parquet(os.path.join(STATICDATA, 'elexon_consumption_sprake.parquet'))
        .set_index('datetime')
    )

@lru_cache
def _get_sprake_appliance_consumption_reference_timeseries(start, periods, freq):
    datetimes = pd.date_range(start, periods=periods, freq=freq)
    return (
        _get_sprake_appliance_consumption_reference_data()
        .loc[datetimes, :]
        .reset_index()
    )

def sprake_appliance_consumption(datetimes, efficiency_reduction=0.1, n_households=1000):
    #from newsegscs.elexon_profiles import get_elexon_consumption
    #cons = get_elexon_consumption(datetimes)
    """Electricity consumption of the appliances of the households at each timestep.

    The reference profile reduced by `efficiency_reduction`, scaled by the number of households.

    Args:
        datetimes: Datetimes at the start of each timestep.
        efficiency_reduction: Fractional reduction in appliance consumption from the reference.
        n_households: Number of households.

    Returns:
        Array of consumption.
    """
    start = datetimes[0]
    periods = len(datetimes)
    freq = datetimes[1] - datetimes[0]
    cons = _get_sprake_appliance_consumption_reference_timeseries(start, periods, freq)
    return cast(np.ndarray, pd.Series(cons['consumption']).array) * (1.0 - efficiency_reduction) * n_households

@lru_cache
def _get_sprake_ev_consumption_reference_data():
    return(
        pd.read_parquet(os.path.join(STATICDATA, 'ev_consumption_sprake.parquet'))
        .set_index('datetime')
    )

@lru_cache
def _get_sprake_ev_consumption_reference_timeseries(start, periods, freq):
    datetimes = pd.date_range(start, periods=periods, freq=freq)
    return (
        _get_sprake_ev_consumption_reference_data()
        .loc[datetimes, :]
        .reset_index()
    )

def sprake_ev_consumption(datetimes, annual_residential_consumption_per_ev=1760.0, n_evs=1000):
    """Electricity consumption of EV charging at each timestep.

    The reference profile scaled by the annual consumption per EV and the number of EVs.

    Args:
        datetimes: Datetimes at the start of each timestep.
        annual_residential_consumption_per_ev: Annual energy consumption of an EV from residential charging (kWh).
        n_evs: Number of electric vehicles.

    Returns:
        Array of consumption.
    """
    start = datetimes[0]
    periods = len(datetimes)
    freq = datetimes[1] - datetimes[0]
    cons = _get_sprake_ev_consumption_reference_timeseries(start, periods, freq)
    return cons['consumption'] * n_evs * annual_residential_consumption_per_ev

@lru_cache
def _get_sprake_dhw_energy_consumption_reference_timeseries(start, periods, freq, ref_daily_consumption=4.5, seasonal_variance=0.2,):
    from newsegsmodelframework.newsegscs.dhw_profiles import get_dhw_energy_consumption
    datetimes = pd.date_range(start, periods=periods, freq=freq)
    cons = get_dhw_energy_consumption(
        datetimes,
        ref_daily_consumption,
        seasonal_variance
    )
    return cons

def sprake_dhw_consumption(datetimes, ref_daily_consumption=4.5, seasonal_variance=0.2, n_households=1000):
    """Electricity consumption for domestic hot water at each timestep.

    The reference profile, varying seasonally about the reference daily consumption, scaled by the number of households.

    Args:
        datetimes: Datetimes at the start of each timestep.
        ref_daily_consumption: Reference daily hot water energy consumption of a household (kWh).
        seasonal_variance: Fractional seasonal variation of the hot water consumption about the reference.
        n_households: Number of households.

    Returns:
        Array of consumption.
    """
    start = datetimes[0]
    periods = len(datetimes)
    freq = datetimes[1] - datetimes[0]
    cons = _get_sprake_dhw_energy_consumption_reference_timeseries(start, periods, freq, ref_daily_consumption, seasonal_variance)
    return cons['consumption'] * n_households

@lru_cache
def _get_sprake_spaceheat_consumption_timeseries(start, periods, freq, hlp=1.1, gfa=105.):
    from newsegsmodelframework.newsegscs.sprake_thermal_model import get_spaceheat_energy_consumption
    datetimes = pd.date_range(start, periods=periods, freq=freq)
    cons = get_spaceheat_energy_consumption(datetimes,hlp,gfa)
    return cons

def sprake_spaceheat_consumption(datetimes, hlp:float=1.1, gfa:float=105.0, n_households=1000):
    """Electricity consumption for space heating at each timestep.

    Derived from heating degree days, the heat loss parameter and the floor area, scaled by the number of households.

    Args:
        datetimes: Datetimes at the start of each timestep.
        hlp: Heat loss parameter.
        gfa: Gross floor area of a dwelling (m^2).
        n_households: Number of households.

    Returns:
        Array of consumption.
    """
    start = datetimes[0]
    periods = len(datetimes)
    freq = datetimes[1] - datetimes[0]
    cons = _get_sprake_spaceheat_consumption_timeseries(start, periods, freq, hlp, gfa)
    return cons['consumption'] * n_households                        


@revision_dataclass
class SprakeCSConfig(NewsegsCSConfig):
    """Configuration of the Sprake consumption and storage module.

    Attributes:
        n_units: Number of households.
        ev_per_unit: Number of EVs per household.
        efficiency_reduction: Fractional reduction in appliance consumption from the reference.
        annual_residential_consumption_per_ev: Annual energy consumption of an EV from residential charging (kWh).
        ref_daily_consumption: Reference daily hot water energy consumption of a household (kWh).
        seasonal_variance: Fractional seasonal variation of the hot water consumption about the reference.
        hlp: Heat loss parameter of the dwellings.
        gfa: Gross floor area of a dwelling (m^2).
        timeseries_hdd_start: Start of the heating degree day series.
        timeseries_model_start: The time in the model corresponding to the start of the degree day series.
        storage_capacity: Capacity of storage (kWh).
        storage_rte: Round trip efficiency of storage.
    """
    n_units: float = 100.0
    ev_per_unit: float = 1.2
    # Appliance parameters
    efficiency_reduction: float = 0.1
    # ev_parameters
    annual_residential_consumption_per_ev: float = 1760.0*0.747
    # dhw parameters
    ref_daily_consumption: float = 4.5
    seasonal_variance: float = 0.2
    # spaceheat parameters
    hlp: float = 1.1
    gfa: float = 105.0
    timeseries_hdd_start: pd.Timestamp = TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0]
    timeseries_model_start: pd.Timestamp = TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0]
    # Storage parameters
    storage_capacity: float = 1000.0
    storage_rte: float = 0.88


class SprakeCS(NewsegsCS):
    """Implementation of NewsegsCS for Sprake Model."""

    _name = "Sprake Consumption and Storage Module"

    @override
    def _generate_config(self, *args, **kwargs) -> SprakeCSConfig:
        return SprakeCSConfig(*args, **kwargs)
    _config: SprakeCSConfig # pyright: ignore[reportIncompatibleVariableOverride]

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: AnyNumber | SprakeCS,
        *args,
        **kwargs
    ) -> None:
        raise ValueError('First argument must be a number or a SprakeCS, is %s', type(dispatch_arg))
    
    # Copy constructor is registered underneath class definition for late-bind.

    @__init__.register(AnyNumber) # pyright: ignore[reportCallIssue]
    def _from_AnyNumber(
        self,
        n_units: AnyNumber,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(*args, n_units = n_units, **kwargs)
    
    @classmethod
    def from_none(cls):
        """Create a Sprake consumption and storage module with default values.

        Returns:
            The module.
        """
        if environment.is_spraketest():
            spaceheat_params = {
                'hlp': 0.3,
                'gfa': 105.0,
                'timeseries_hdd_start': pd.Timestamp('2018-01-01T00:00:00', tz='utc'),
                'timeseries_model_start': pd.Timestamp('2002-01-01T00:00:00', tz='utc'),
            }
        else:
            spaceheat_params = {
                'hlp': 1.1,
                'gfa': 105.0,
                'timeseries_hdd_start': TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0],
                'timeseries_model_start': TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0],
            }
        
        return cls(100, **spaceheat_params)

    @property
    def n_households(self) -> float:
        """Number of households.
        """
        return self.n_units

    @property
    def n_evs(self) -> float:
        """Number of EVs.
        """
        return self.n_units * self.ev_per_unit

    def get_appliance_params(self):
        """The parameters of the appliance consumption.

        Returns:
            Dictionary of the parameters.
        """
        atts = ['efficiency_reduction', 'n_households']
        return {k: getattr(self, k) for k in atts}

    def get_ev_params(self):
        """The parameters of the EV charging consumption.

        Returns:
            Dictionary of the parameters.
        """
        atts = ['annual_residential_consumption_per_ev', 'n_evs']
        return {k: getattr(self, k) for k in atts}

    def get_dhw_params(self):
        """The parameters of the domestic hot water consumption.

        Returns:
            Dictionary of the parameters.
        """
        atts = ['ref_daily_consumption', 'seasonal_variance', 'n_households']
        return {k: getattr(self, k) for k in atts}

    def get_sh_params(self):
        """The parameters of the space heating consumption.

        Returns:
            Dictionary of the parameters.
        """
        atts = ['hlp', 'gfa', 'n_households']
        return {k: getattr(self, k) for k in atts}

    def get_storage_params(self):
        """The parameters of the storage.

        Returns:
            Dictionary of the parameters.
        """
        atts = ['storage_capacity', 'storage_rte']
        return {k: getattr(self, k) for k in atts}

    def get_spaceheat_consumption(self, timespan: modtimespan.RegTimeSpan) -> np.ndarray:
        """Electricity consumption for space heating at each timestep.

        From the heating degree day series of the Sprake model, offset so that
        `timeseries_hdd_start` falls at `timeseries_model_start`, and repeated as necessary.

        Args:
            timespan: The period of time, with the timestep of the model.

        Returns:
            Array of consumption.
        """
        spaceheat_timespan = modtimespan.OffsetRegTimeSpan(
            TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0],
            TIMESERIES_DEGREE_DAYS['timestamp'].iloc[-1],
            timestep = timespan.timestep
        )

        # In this context, 'local' is the heating degree day ts, and remote is the model ts
        spaceheat_timespan.set_offset(
            local_start = self.timeseries_hdd_start,
            remote_start = self.timeseries_model_start
        )

        spaceheat_datetimes = spaceheat_timespan.to_pandas()[spaceheat_timespan.get_local_index(timespan)]

        return np.asarray(sprake_spaceheat_consumption(spaceheat_datetimes, **self.get_sh_params()))

    def run(
        self,
        timespan: modtimespan.TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> SprakeCSResult:
        """Run the consumption and storage module over a time span.

        The loads - appliances, hot water, space heating and EV charging - are calculated from their profiles. Storage is
        charged only by over-generation (the generation of the NewSEGS Energy Model less the loads) and discharged
        by under-generation, applying the round trip efficiency on discharge. Any remainder is exported to or
        imported from the grid. With no storage capacity all the over- or under-generation goes to the grid.

        Args:
            timespan: The period of time to run.
            run_start: Time at which the run started; defaults to now.

        Returns:
            The result, with the meters of the loads, storage and grid, and the state of charge of storage.
        """
        super().run(timespan, run_start)
        if not isinstance(timespan, modtimespan.RegTimeSpan):
            if self.model is None:
                raise ValueError("CS module requires a model to serve timestep")
            timespan = modtimespan.RegTimeSpan(timespan)
            timespan.timestep = self.model.get_default_timestep()
        
        datetimes = timespan.to_pandas()

        cons_arr = np.empty((4, len(datetimes)), dtype=np.float64)
        cons_arr[0,:] = sprake_appliance_consumption(datetimes, **self.get_appliance_params())
        cons_arr[3,:] = sprake_ev_consumption(datetimes, **self.get_ev_params())
        cons_arr[1,:] = sprake_dhw_consumption(datetimes, **self.get_dhw_params())
        cons_arr[2,:] = self.get_spaceheat_consumption(timespan)

        stor_arr = np.empty(len(datetimes), dtype=np.float64)
        # Generation
        if self.model is None:
            raise ValueError("Storage requires a model to serve generation")
        
        gen_res = self.model.get_generation_result().meters.sum(axis=0)

        assert len(gen_res) == len(stor_arr), 'Generation is returning a different length time series to CS'

        # Under the Sprake model, Storage is only charged by overgeneration, and is discharged by undergeneration
        overproduction = gen_res - np.sum(cons_arr, axis=0)

        storage_params = self.get_storage_params()

        storage_cap = storage_params.get('storage_capacity', 0.0)
        if storage_cap > 0.0:
            storage_rte = storage_params.get('storage_rte', 1.0)

            stor_imp = np.zeros_like(stor_arr)
            stor_exp = np.zeros_like(stor_arr)
            stor_loss = np.zeros_like(stor_arr)
            grid_imp = np.zeros_like(stor_arr)
            grid_exp = np.zeros_like(stor_arr)

            # Initial storage is half capacity
            stor_arr[0] = storage_cap / 2

            # No real option but to iterate this; for performance, this could be compiled
            for i in np.arange(1,len(gen_res)):
                stor_soc = stor_arr[i-1]
                # Assuming 100% Depth of charge/discharge
                headroom = storage_cap - stor_soc
                floorroom = stor_soc
                op = overproduction[i]
                if op > 0:
                    to_stor = min(headroom, op)
                    to_grid = op - to_stor
                    stor_arr[i] = stor_soc + to_stor
                    stor_imp[i] = to_stor
                    grid_exp[i] = to_grid
                    stor_exp[i] = 0.0
                    stor_loss[i] = 0.0
                    grid_imp[i] = 0.0
                else:
                    stor_dis = min(floorroom, -op/storage_rte) # The RTE is applied at discharge only in Sprake model
                    from_grid = -op - (storage_rte * stor_dis)
                    stor_arr[i] = stor_soc - stor_dis
                    stor_imp[i] = 0.0
                    stor_exp[i] = stor_dis * storage_rte
                    stor_loss[i] = stor_dis * (1.0 - storage_rte)
                    grid_imp[i] = from_grid
                    grid_exp[i] = 0.0
        else:
            stor_arr = np.zeros(len(datetimes), dtype=np.float64)
            stor_imp = np.zeros_like(stor_arr)
            stor_exp = np.zeros_like(stor_arr)
            stor_loss = np.zeros_like(stor_arr)
            
            grid_imp = -1. * np.clip(overproduction,a_min = None, a_max = 0)
            grid_exp = np.clip(overproduction, a_min = 0, a_max = None)

        res = SprakeCSResult(
            self.id,
            datetime.datetime.now(),
            timespan = timespan,
            domestic_consumption = cons_arr,
            storage_import=stor_imp,
            storage_export=stor_exp,
            storage_loss = stor_loss,
            grid_import = grid_imp,
            grid_export = grid_exp,
            storage_soc = stor_arr
        )

        return res

#SprakeCS copy constructor
@SprakeCS.__init__.register(SprakeCS) # pyright: ignore[reportFunctionMemberAccess]
def _SprakeCS_from_other(
    self,
    other: SprakeCS
) -> None:
    super(SprakeCS, self).__init__()
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

    for k in asdict(other._config).keys(): # pyright: ignore[reportArgumentType]
        setattr(self, k, copy.copy(getattr(other, k)))
    
