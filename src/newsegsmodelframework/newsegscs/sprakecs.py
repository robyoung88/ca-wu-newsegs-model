"""Provides implementation of NewsegsCS for Sprake Model."""
from __future__ import annotations
from dataclasses import asdict
import datetime
import os
import copy
from collections.abc import MutableMapping
from typing import Optional, Union, cast, override
from numbers import Number
from functools import singledispatchmethod

import numpy as np
import pandas as pd
import numpy.typing as npt

from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.core.trackeddata import revision_dataclass
from newsegsmodelframework.newsegscs.newsegscs import NewsegsCS, NewsegsCSConfig
from newsegsmodelframework.core import newsegsmodule
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.core import location as modlocation
from newsegsmodelframework.newsegsmodel import newsegsmodel

from newsegsmodelapp.newsegsbrowser import STATICDATA
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
        return ('appliance_import', 'dhw_import', 'spaceheat_import', 'evcharge_import',
                'storage_import', 'storage_export', 'storage_loss',
                'grid_import', 'grid_export')
    
    def get_meter_types(self):
        return ('load', 'load', 'load', 'load',
                'import_storage', 'export_storage', 'loss',
                'import', 'export')

    def get_dsm_names(self):
        return ('storage_soc',)

    def get_dsm_types(self):
        return ('system_state',)

    def set_domestic_consumption(self, domestic_consumption:np.ndarray[tuple[int,int], np.dtype[np.number]]):
        self._domestic_consumption = domestic_consumption

    def set_storage_import(self, storage_import:np.ndarray[tuple[int], np.dtype[np.number]]):
        self._storage_import = storage_import

    def set_storage_export(self, storage_export:np.ndarray[tuple[int], np.dtype[np.number]]):
        self._storage_export = storage_export

    def set_storage_loss(self, storage_loss:np.ndarray[tuple[int], np.dtype[np.number]]):
        self._storage_loss = storage_loss

    def set_grid_import(self, grid_import:np.ndarray[tuple[int], np.dtype[np.number]]):
        self._grid_import = grid_import

    def set_grid_export(self, grid_export:np.ndarray[tuple[int], np.dtype[np.number]]):
        self._grid_export = grid_export

    def set_storage_soc(self, storage_soc:np.ndarray[tuple[int], np.dtype[np.number]]):
        self._storage_soc = storage_soc

# Function wrappers for consumption models
# Todo: Consider how to re-wrap these, as DatetimeIndex[es] and Series are unhashable
# so we can't get a cache working.

def sprake_appliance_consumption(datetimes, efficiency_reduction=0.1, n_households=1000):
    #from newsegscs.elexon_profiles import get_elexon_consumption
    #cons = get_elexon_consumption(datetimes)
    cons = (
        pd.read_parquet(os.path.join(STATICDATA, 'elexon_consumption_sprake.parquet'))
        .set_index('datetime')
        .loc[datetimes, :]
        .reset_index()
    )
    return cast(np.ndarray, pd.Series(cons['consumption']).array) * (1.0 - efficiency_reduction) * n_households

def sprake_ev_consumption(datetimes, annual_residential_consumption_per_ev=1760.0, n_evs=1000):
    # from newsegscs.ev_profiles import get_ev_consumption
    # cons = get_ev_consumption(datetimes,
    #                           annual_consumption=annual_residential_consumption_per_ev)
    #                           .set_index('datetime')
    # return cons['consumption'] * n_evs
    cons = (
        pd.read_parquet(os.path.join(STATICDATA, 'ev_consumption_sprake.parquet'))
        .set_index('datetime')
        .loc[datetimes, :]
        .reset_index()
    )
    return cons['consumption'] * n_evs * annual_residential_consumption_per_ev

def sprake_dhw_consumption(datetimes, ref_daily_consumption=4.5, seasonal_variance=0.2, n_households=1000):
    from newsegsmodelframework.newsegscs.dhw_profiles import get_dhw_energy_consumption
    cons = get_dhw_energy_consumption(datetimes,
                                      ref_daily_consumption,
                                      seasonal_variance)
    return cons['consumption'] * n_households

def sprake_spaceheat_consumption(datetimes, hlp:float=1.1, gfa:float=105.0, n_households=1000):
    from newsegsmodelframework.newsegscs.sprake_thermal_model import get_spaceheat_energy_consumption
    cons = get_spaceheat_energy_consumption(datetimes,
                                            hlp,gfa)
    return cons['consumption'] * n_households                        


@revision_dataclass
class SprakeCSConfig(NewsegsCSConfig):
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
        if (os.environ.get('ENV_FOR_DYNACONF',None) == 'spraketest'):
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
        return self.n_units

    @property
    def n_evs(self) -> float:
        return self.n_units * self.ev_per_unit

    def get_appliance_params(self):
        atts = ['efficiency_reduction', 'n_households']
        return {k: getattr(self, k) for k in atts}

    def get_ev_params(self):
        atts = ['annual_residential_consumption_per_ev', 'n_evs']
        return {k: getattr(self, k) for k in atts}

    def get_dhw_params(self):
        atts = ['ref_daily_consumption', 'seasonal_variance', 'n_households']
        return {k: getattr(self, k) for k in atts}

    def get_sh_params(self):
        atts = ['hlp', 'gfa', 'n_households']
        return {k: getattr(self, k) for k in atts}

    def get_storage_params(self):
        atts = ['storage_capacity', 'storage_rte']
        return {k: getattr(self, k) for k in atts}

    def run(
        self, 
        timespan: modtimespan.TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> SprakeCSResult:
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

        # The space heating requires a little more finess, simply because the time series may require repetition
        shp = self.get_sh_params()
        
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
        
        cons_arr[2,:] = sprake_spaceheat_consumption(spaceheat_datetimes, **shp)

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
    
