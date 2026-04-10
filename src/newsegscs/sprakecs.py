from __future__ import annotations
from collections.abc import Mapping
import os, re, copy
import numpy as np
import pandas as pd
import numpy.typing as npt

#from src.newsegsmodel import NewsegsModel
from src.newsegscs import NewsegsCS
from src.core import ABCNewsegsModuleResult

from src.core.timespan import OffsetRegTimeSpan, RegTimeSpan
from src.newsegscs.sprake_thermal_model import TIMESERIES_DEGREE_DAYS

class SprakeCSResult(ABCNewsegsModuleResult):
    def __init__(self,
                 timespan: RegTimeSpan,
                 domestic_consumption:np.ndarray[tuple[int,int], np.dtype[np.number]],
                 storage_import:np.ndarray[tuple[int], np.dtype[np.number]],
                 storage_export:np.ndarray[tuple[int], np.dtype[np.number]],
                 storage_loss:np.ndarray[tuple[int], np.dtype[np.number]],
                 grid_import:np.ndarray[tuple[int], np.dtype[np.number]],
                 grid_export:np.ndarray[tuple[int], np.dtype[np.number]],
                 storage_soc:np.ndarray[tuple[int], np.dtype[np.number]]
                 ) -> None:
        
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

    def get_timespan(self) -> RegTimeSpan:
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

def sprake_appliance_consumption(datetimes, efficiency_reduction=0.1, n_households=1000):
    from src.newsegscs.elexon_profiles import get_elexon_consumption
    cons = get_elexon_consumption(datetimes)
    return cons['consumption'].values * (1.0 - efficiency_reduction) * n_households

def sprake_ev_consumption(datetimes, annual_residential_consumption_per_ev=1760.0, n_evs=1000):
    from src.newsegscs.ev_profiles import get_ev_consumption
    cons = get_ev_consumption(datetimes,
                              annual_consumption=annual_residential_consumption_per_ev)
    return cons['consumption'] * n_evs

def sprake_dhw_consumption(datetimes, ref_daily_consumption=4.5, seasonal_variance=0.2, n_households=1000):
    from src.newsegscs.dhw_profiles import get_dhw_energy_consumption
    cons = get_dhw_energy_consumption(datetimes,
                                      ref_daily_consumption,
                                      seasonal_variance)
    return cons['consumption'] * n_households

def sprake_spaceheat_consumption(datetimes, hlp:float=1.1, gfa:float=105.0, n_households=1000):
    from src.newsegscs.sprake_thermal_model import get_spaceheat_energy_consumption
    cons = get_spaceheat_energy_consumption(datetimes,
                                            hlp,gfa)
    return cons['consumption'] * n_households                        

class SprakeCS(NewsegsCS):

    _default_name = "Sprake Consumption and Storage Module"

    def __init__(self):
        self._name = self._default_name
        self._n_units = 1000.0
        self._ev_per_unit = 1.2
        self._model = None
        self._appliance_params = {
            'efficiency_reduction': 0.1,
            'n_households': self._n_units
        }
        self._ev_params = {
            'annual_residential_consumption_per_ev': 1313.65683,
            'n_evs': self._ev_per_unit * self._n_units
        }
        self._dhw_params = {
            'ref_daily_consumption': 4.5,
            'seasonal_variance': 0.2,
            'n_households': self._n_units
        }
        if (os.environ.get('ENV_FOR_DYNACONF',None) == 'spraketest'):
            self._spaceheat_params = {
                'hlp': 0.3,
                'gfa': 105.0,
                'timeseries_hdd_start': pd.Timestamp('2018-01-01T00:00:00', tz='utc'),
                'timeseries_model_start': pd.Timestamp('2002-01-01T00:00:00', tz='utc'),
                'n_households': self._n_units
            }
        else:
            self._spaceheat_params = {
                'hlp': 1.1,
                'gfa': 105.0,
                'timeseries_hdd_start': TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0],
                'timeseries_model_start': TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0],
                'n_households': self._n_units
            }
        self._storage_params = {
            'storage_capacity': 4000.0,
            'storage_rte': 0.88
        }
        
    @property
    def model(self) -> NewsegsModel|None:
        return self._model
    
    @model.setter
    def model(self, model:NewsegsModel) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def n_units(self) -> float:
        return self._n_units

    @n_units.setter
    def n_units(self, n_units:float) -> None:
        self._n_units = n_units
        self._appliance_params['n_households'] = n_units
        self._ev_params['n_evs'] = n_unit * self._ev_per_unit
        self._dhw_params['n_households'] = n_units
        self._spaceheat_params['n_households'] = n_units
    
    @property
    def appliance_params(self) -> dict:
        return self._appliance_params
    
    # Keep property as read-only, use explicit setter as dict is mutable anyway
    def set_appliance_params(self, params:dict) -> None:
        self._appliance_params = params

    @property
    def ev_params(self) -> dict:
        return self._ev_params

    def set_ev_params(self, params:dict) -> None:
        self._ev_params = params

    @property
    def dhw_params(self) -> dict:
        return self._dhw_params

    def set_dhw_params(self, params:dict) -> None:
        self._dhw_params = params

    @property
    def spaceheat_params(self) -> dict:
        return self._spaceheat_params

    def set_spaceheat_params(self, params:dict) -> None:
        self._spaceheat_params = params

    @property
    def storage_params(self) -> dict:
        return self._storage_params
    
    def set_storage_params(self, params:dict) -> None:
        self._storage_params = params

    def run(self, timespan:TimeSpan) -> SprakeCSResult:
        if not isinstance(timespan, RegTimeSpan):
            if self.model is None:
                raise ValueError("CS module requires a model to serve timestep")
            timespan = RegTimeSpan(timespan)
            timespan.timestep = self.model.get_default_timestep()
        
        datetimes = timespan.to_pandas()

        cons_arr = np.empty((4, len(datetimes)), dtype=np.float64)
        cons_arr[0,:] = sprake_appliance_consumption(datetimes, **self._appliance_params)
        cons_arr[1,:] = sprake_ev_consumption(datetimes, **self._ev_params)
        cons_arr[2,:] = sprake_dhw_consumption(datetimes, **self._dhw_params)

        # The space heating requires a little more finess, simply because the time series may require repetition
        shp = self._spaceheat_params.copy()
        
        spaceheat_timespan = OffsetRegTimeSpan(
            TIMESERIES_DEGREE_DAYS['timestamp'].iloc[0],
            TIMESERIES_DEGREE_DAYS['timestamp'].iloc[-1],
            timestep = timespan.timestep
        )

        # In this context, 'local' is the heating degree day ts, and remote is the model ts
        spaceheat_timespan.set_offset(local_start=shp.pop('timeseries_hdd_start'),
                                      remote_start=shp.pop('timeseries_model_start'))

        spaceheat_datetimes = spaceheat_timespan.to_pandas()[spaceheat_timespan.get_local_index(timespan)]
        
        cons_arr[3,:] = sprake_spaceheat_consumption(spaceheat_datetimes, **shp)

        storage_cap = self._storage_params.get('storage_capacity', 0.0)
        if storage_cap > 0.0:
            storage_rte = self._storage_params.get('storage_rte', 1.0)

            stor_arr = np.empty(len(datetimes), dtype=np.float64)
            
            stor_imp = np.zeros_like(stor_arr)
            stor_exp = np.zeros_like(stor_arr)
            stor_loss = np.zeros_like(stor_arr)
            grid_imp = np.zeros_like(stor_arr)
            grid_exp = np.zeros_like(stor_arr)

            # Initial storage is half capacity
            stor_arr[0] = storage_cap / 2

            # Generation
            if self.model is None:
                raise ValueError("Storage requires a model to serve generation")
            
            gen_res = self.model.get_generation_result().meters.sum(axis=0)

            assert len(gen_res) == len(stor_arr), 'Generation is returning a different length time series to CS'

            # Under the Sprake model, Storage is only charged by overgeneration, and is discharged by undergeneration
            overproduction = gen_res - np.sum(cons_arr, axis=0)

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
            grid_imp = np.zeros_like(stor_arr)
            grid_exp = np.zeros_like(stor_arr)
        
        res = SprakeCSResult(
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

    @classmethod
    def from_characteristics(cls,
                             name:str,
                             n_units:float,
                             appliance_params:dict,
                             ev_params:dict,
                             dhw_params:dict,
                             spaceheat_params:dict,
                             storage_params:dict
                             ) -> SprakeCS:
        o = cls()
        o.name = name
        o.n_units = n_units
        o.set_appliance_params(appliance_params)
        o.set_ev_params(ev_params)
        o.set_dhw_params(dhw_params)
        o.set_spaceheat_params(spaceheat_params)
        o.set_storage_params(storage_params)

        return o

    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'n_units': self._n_units,
            'appliance_params': self._appliance_params,
            'ev_params': self._ev_params,
            'dhw_params': self._ev_params,
            'spaceheat_params': self._spaceheat_params,
            'storage_params': self._storage_params
        }

        return odict
    
    @classmethod
    def from_dict(cls, input:Mapping) -> SprakeCS:
        return cls.from_characteristics(**input)
