"""Provides implementation of NewsegsFinance for Sprake Model."""
from __future__ import annotations
import copy
from typing import override, Mapping
from numbers import Number
from functools import singledispatchmethod
from functools import lru_cache

import numpy as np
import pandas as pd

from core.newsegsmodelinterface import NewsegsModelInterface
from util import classfuncs
from core.timespan import delta_days
from core.newsegsmoduleresult import filter_meter_indices
from newsegsfinance import newsegsfinance
from newsegsfinance import common as common_finance
from newsegsmodel import newsegsmodel
from newsegsmodel import SprakeModel

from newsegsfinance import apply_discount_factor, sum_all_to_horizon
#from newsegsmodel import NewsegsModel
from newsegsstats import core as stats_core

# Not strictly true, but good enough for finance.
HOURS_IN_YEAR = 8760.0

class SprakeFinance(newsegsfinance.NewsegsFinance):
    """Implementation of NewsegsFinance for Sprake Model."""
    _name = 'Sprake Finance Module'

    _default_unit_costs = {
        'wind_capex_per_kw': 1500.0,
        'wind_om_per_kw_year': 46.0,

        'pv_capex_per_kw': 1000.0,
        'pv_om_per_kw_year': 10.5,

        'bess_capex_per_kwh': 191.772,
        'bess_om_per_kwh_year': 16.719,

        'resident_sc_per_unit_day': 0.0,
        'resident_var_per_unit': 0.35,

        'grid_export_var_per_unit': 0.1,
        
        'grid_import_sc_per_day': 0.0,
        'grid_import_var_per_unit': 0.35
    }

    _meter_names = {
        'resident_consumption': ('appliance_import', 'dhw_import', 'spaceheat_import'),
        'ev_consumption': ('evcharge_import'),
        'grid_export': ('grid_export'),
        
        'grid_import': ('grid_import')
    }

    _model: SprakeModel # pyright: ignore[reportIncompatibleVariableOverride]

    @singledispatchmethod
    def __init__(
        self,
        unit_costs: Mapping | float|int | SprakeFinance,
        benefit_discount_rate: float|int | None = None,
        cost_discount_rate: float|int | None = None,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None
    ) -> None:
        raise ValueError('First argument must be a Mapping, a Number, or a SprakeFinance, is %s', type(unit_costs))
    
    # Copy constructor is registered underneath class definition for late-bind

    @__init__.register(float|int)
    def _from_number(
        self,
        benefit_discount_rate: float|int,
        cost_discount_rate: float|int = 0.0,
        horizon: int = -1,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None,
    ) -> None:
        super().__init__()
        self._unit_costs = type(self)._default_unit_costs.copy()

        self.benefit_discount_rate = benefit_discount_rate
        self.cost_discount_rate = cost_discount_rate

        self.horizon = horizon

        if name is not None:
            self.name = name
        
        if model is not None:
            self.set_model(model)

        self.dirty = True
    
    @__init__.register(dict)
    def _from_dict(
        self,
        unit_costs: Mapping,
        benefit_discount_rate: float|int = 0.0,
        cost_discount_rate: float|int = 0.0,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None,
    ) -> None:
        a = locals()
        del a['self']
        del a['unit_costs']
        del a['benefit_discount_rate']

        self.__init__(benefit_discount_rate, **a)
        self.set_unit_costs_from_dict(unit_costs)
    
    @classmethod
    def from_none(cls):
        return cls(0.0)

    def set_unit_costs_from_dict(self, input_dict: Mapping) -> None:
        """
        Update all unit costs using a dictionary.

        Check `SprakeFinance.get_default_unit_costs()` for expected values
        """
        v0 = copy.copy(self._unit_costs)
        self._unit_costs.update(input_dict)
        self.dirty = self.dirty or (v0 != self._unit_costs)
    
    @override
    def set_model(
        self, 
        mdl: NewsegsModelInterface,
        dirty: bool = True
    ) -> None:
        if not isinstance(mdl, SprakeModel):
            raise TypeError(f'SprakeFinance only compatible with SprakeModel, {type(mdl)} provided')
        self._model: SprakeModel = mdl # pyright: ignore[reportIncompatibleVariableOverride]
        self.dirty = self.dirty or dirty
    
    @property
    def model(self) -> SprakeModel:
        if not hasattr(self, '_model'):
            raise AttributeError('model has not yet been set')
        return self._model
    
    @model.setter
    def model(self, mdl: NewsegsModelInterface) -> None:
        self.set_model(mdl)

    @classmethod
    def get_default_unit_costs(cls) -> dict:
        """
        Return the default unit cost dictionary
        """
        return cls._default_unit_costs.copy()

    @property
    def unit_costs(self) -> dict:
        """
        Get a copy of the current unit cost dictionary
        """
        return self._unit_costs.copy()

    def _get_empty_df(self) -> pd.DataFrame:
        return _deferred_get_empty_df(self).copy()

    def _get_consumption(self, meter_names) -> pd.DataFrame:
        """
        Summarise consumption meters to a simple dataframe
        """
        return _deferred_get_consumption(self, meter_names).copy()

    def _get_resident_consumption(self) -> pd.DataFrame:
        return self._get_consumption(self._meter_names['resident_consumption'])

    def _get_ev_consumption(self) -> pd.DataFrame:
        return self._get_consumption(self._meter_names['ev_consumption'])
    
    def _get_grid_export(self) -> pd.DataFrame:
        return self._get_consumption(self._meter_names['grid_export'])

    def _get_grid_import(self) -> pd.DataFrame:
        return self._get_consumption(self._meter_names['grid_import'])

    # Benefits
    @property
    def resident_receipts_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_resident_receipts_undiscounted(self).copy()

    @property
    def resident_receipts_discounted(self) -> pd.DataFrame:
        return _deferred_get_resident_receipts_discounted(self).copy()
        
    @property
    def ev_receipts_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_ev_receipts_undiscounted(self).copy()
        
    @property
    def ev_receipts_discounted(self) -> pd.DataFrame:
        return _deferred_get_ev_receipts_discounted(self).copy()

    @property
    def export_receipts_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_export_receipts_undiscounted(self).copy()

    @property
    def export_receipts_discounted(self) -> pd.DataFrame:
        return _deferred_get_export_receipts_discounted(self).copy()

    @property
    def all_receipts_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_all_receipts_undiscounted(self).copy()
        
    @property
    def all_receipts_discounted(self) -> pd.DataFrame:
        return _deferred_get_all_receipts_discounted(self).copy()

    def get_total_present_benefits_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_total_present_benefits_undiscounted(
            self,
            horizon
        )
    
    def get_total_present_benefits_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_total_present_benefits_discounted(self, horizon)
        
    # Costs
    
    @property
    def import_costs_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_import_costs_undiscounted(self).copy()

    @property
    def import_costs_discounted(self) -> pd.DataFrame:
        return _deferred_get_import_costs_discounted(self).copy()
    
    @property
    def om_costs_generation_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of generators.

        Broken down into `wind_costs`, `pv_costs` and `costs` (i.e. total).
        O&M costs are accrued in single monthly payments.
        """
        return _deferred_get_om_costs_generation_undiscounted(self).copy()

    @property
    def om_costs_generation_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of generators (cost discount applied).

        Broken down into `wind_costs`, `pv_costs` and `costs` (i.e. total).
        O&M costs are accrued in single monthly payments.
        """
        return _deferred_get_om_costs_generation_discounted(self).copy()

    @property
    def om_costs_storage_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of storage technologies.

        Broken down into `bess_costs` and `costs` (i.e. total).
        O&M costs are accrued in single monthly payments.
        """
        return _deferred_get_om_costs_storage_undiscounted(self).copy()

    @property
    def om_costs_storage_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of storage technologies (cost discount applied).

        Broken down into `bess_costs` and `costs` (i.e. total).
        O&M costs are accrued in single monthly payments.
        """
        return _deferred_get_om_costs_storage_discounted(self).copy()

    @property
    def om_costs_billing_undiscounted(self) -> pd.DataFrame:
        """
        This is uncosted in Sprake model - return zeros
        """
        return _deferred_get_om_costs_billing_undiscounted(self).copy()
        
    @property
    def om_costs_billing_discounted(self) -> pd.DataFrame:
        return _deferred_get_om_costs_billing_discounted(self).copy()
    
    @property
    def om_costs_other_undiscounted(self) -> pd.DataFrame:
        """
        There are no other costs in Sprake model - return zeros
        """
        return _deferred_get_om_costs_other_undiscounted(self).copy()

    @property
    def om_costs_other_discounted(self) -> pd.DataFrame:
        return _deferred_get_om_costs_other_discounted(self).copy()

    @property
    def all_recurrent_costs_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_all_recurrent_costs_undiscounted(self).copy()

    @property
    def all_recurrent_costs_discounted(self) -> pd.DataFrame:
        return _deferred_get_all_recurrent_costs_discounted(self).copy()

    @property
    def capex_costs_generation_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, all capex is incurred at start of first timestep
        """
        return _deferred_get_capex_costs_generation_undiscounted(self).copy()
        
    @property
    def capex_costs_generation_discounted(self) -> pd.DataFrame:
        return _deferred_get_capex_costs_generation_discounted(self).copy()

    @property
    def capex_costs_storage_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_capex_costs_storage_undiscounted(self).copy()
        
    @property
    def capex_costs_storage_discounted(self) -> pd.DataFrame:
        return _deferred_get_capex_costs_storage_discounted(self).copy()

    @property
    def capex_costs_distribution_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, no distribution costs are accounted for
        """
        return _deferred_get_capex_costs_distribution_undiscounted(self).copy()
        
    @property
    def capex_costs_distribution_discounted(self) -> pd.DataFrame:
        return _deferred_get_capex_costs_distribution_discounted(self).copy()

    @property
    def capex_costs_metering_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, no metering costs are accounted for
        """
        return _deferred_get_capex_costs_metering_undiscounted(self).copy()
        
    @property
    def capex_costs_metering_discounted(self) -> pd.DataFrame:
        return _deferred_get_capex_costs_metering_discounted(self).copy()

    @property
    def capex_costs_other_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, no other costs are accounted for
        """
        return _deferred_get_capex_costs_other_undiscounted(self).copy()
    
    @property
    def capex_costs_other_discounted(self) -> pd.DataFrame:
        return _deferred_get_capex_costs_other_discounted(self).copy()

    @property
    def all_capex_costs_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_all_capex_costs_undiscounted(self).copy()

    @property
    def all_capex_costs_discounted(self) -> pd.DataFrame:
        return _deferred_get_all_capex_costs_discounted(self).copy()

    @property
    def all_costs_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_all_costs_undiscounted(self).copy()
        
    @property
    def all_costs_discounted(self) -> pd.DataFrame:
        return _deferred_get_all_costs_discounted(self).copy()
        
    def get_total_present_costs_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_total_present_costs_undiscounted(self)
        
    def get_total_present_costs_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_total_present_costs_discounted(self)
        
    # Summary vectors
    def get_benefits_series_undiscounted(self) -> pd.Series:
        return _deferred_get_benefits_series_undiscounted(self).copy()

    def get_benefits_series_discounted(self) -> pd.Series:
        return _deferred_get_benefits_series_discounted(self).copy()
            
    def get_costs_series_undiscounted(self) -> pd.Series:
        return _deferred_get_costs_series_undiscounted(self).copy()

    def get_costs_series_discounted(self) -> pd.Series:
        return _deferred_get_costs_series_discounted(self).copy()

    def get_benefits_costs_undiscounted(self) -> pd.DataFrame:
        return _deferred_get_benefits_costs_undiscounted(self).copy()
    
    def get_benefits_costs_discounted(self) -> pd.DataFrame:
        return _deferred_get_benefits_costs_discounted(self).copy()

    # Derived values
    def get_benefit_cost_ratio_undiscounted(self,  horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_benefit_cost_ratio_undiscounted(self)
        
    def get_benefit_cost_ratio_discounted(self,  horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_benefit_cost_ratio_discounted(self)

    def get_simple_payback_time_days(self) -> float:
        return _deferred_get_simple_payback_time_days(self)
        
    def get_net_present_value_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_net_present_value_undiscounted(self, horizon)

    def get_net_present_value_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return _deferred_get_net_present_value_discounted(self, horizon)
    
    # @override
    # def to_dict(self) -> dict:
    #     return {
    #         'class': classfuncs.get_class(self),
    #         'name': self._name,
    #         'unit_costs': self._unit_costs,
    #         'benefit_discount_rate': self._benefit_discount_rate,
    #         'cost_discount_rate': self._cost_discount_rate
    #     }
    
    # def sync_with_dict(self, config: Mapping) -> None:
    #     """
    #     Synchronise configuration with a config dictionary.
    #     """
        
    #     config = copy.copy(config)

    #     unit_costs = config.get('unit_costs', None)
    #     if unit_costs:
    #         self.set_unit_costs_from_dict(unit_costs)
        
    #     # This looks risky, but practically may only result in
    #     # some redundant attributes if the config is bad.
    #     conf_keys = config.keys()
    #     for k in conf_keys:
    #         if hasattr(self, k):
    #             v = config.get(k)

    #             # If the attribute is a read-write property, its class attribute 
    #             # will have an fset
    #             try:
    #                 prop = getattr(type(self), k)
    #                 if hasattr(prop, 'fset'):
    #                     if getattr(prop, 'fset') is not None:
    #                         getattr(prop, 'fset')(self, v)
    #                     else:
    #                         # Property is read-only; do nothing
    #                         ...
    #                 else:
    #                     # Otherwise, we assume it is a simple attribute that may be overwritten
    #                     setattr(self, k, v)
    #             except AttributeError:
    #                 setattr(self, k, v)
    
    # @classmethod
    # def from_dict(cls, config: Mapping) -> SprakeFinance:
    #     o = cls.from_none()
    #     o.sync_with_dict(config)

    #     return o

# SprakeFinance copy constructor
@SprakeFinance.__init__.register(SprakeFinance) # pyright: ignore[reportFunctionMemberAccess]
def _SprakeFinance_from_other(
    self,
    other: SprakeFinance
) -> None:
    super(SprakeFinance, self).__init__()

    self._unit_costs = copy.copy(other.unit_costs)
    self.benefit_discount_rate = other.benefit_discount_rate
    self.cost_discount_rate = other.cost_discount_rate
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass

def _make_unit_cost_property(key: str):
    def getter(self) -> float:
        return self._unit_costs.get(key)

    def setter(self, value: float) -> None:
        self.dirty = self.dirty or self._unit_costs[key] != value
        self._unit_costs[key] = value

    return property(getter, setter, doc=f"Unit cost for {key}")

for _key in SprakeFinance._default_unit_costs.keys():
    setattr(SprakeFinance, _key, _make_unit_cost_property(_key))

@lru_cache
def _deferred_get_empty_df(fnc: SprakeFinance):
    if fnc._model is None:
        return pd.DataFrame()
    #
    csr = fnc._model.get_consumption_storage_result()
    if csr is None:
        return pd.DataFrame()
    
    return pd.DataFrame({
        'datetime': csr.get_timespan().to_pandas(),
    }).set_index('datetime')

@lru_cache
def _deferred_get_consumption(fnc: SprakeFinance, meter_names) -> pd.DataFrame:
    """
    Summarise consumption meters to a simple dataframe
    """
    if fnc.model is None:
        return pd.DataFrame()
    
    csr = fnc.model.get_consumption_storage_result()
    if csr is None:
        return pd.DataFrame()

    meter_indices = filter_meter_indices(csr, meter_name = meter_names)

    return pd.DataFrame({
        'datetime': csr.get_timespan().to_pandas(),
        'consumption': csr.meters[meter_indices,:].sum(axis=0),
    })

@lru_cache
def _deferred_get_resident_receipts_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    consumption = fnc._get_resident_consumption()
    if len(consumption) == 0:
        return consumption

    if fnc.model is None:
        raise TypeError('NewsegsFinance instance does not have an attached NewsegsModel')
    
    odf = (
        consumption
        .assign(
            resident_units = fnc.model.consumption_storage.n_units, # In Sprake model, the number of occupied units is constant over time
            deltaday = lambda df: delta_days(df['datetime']),
            fixed_receipts = lambda df: df['resident_units'] * df['deltaday'] * fnc.resident_sc_per_unit_day, # pyright: ignore[reportAttributeAccessIssue]
            var_receipts = lambda df: df['consumption'] * fnc.resident_var_per_unit, # pyright: ignore[reportAttributeAccessIssue]
            receipts = lambda df: df['fixed_receipts'] + df['var_receipts']
        )
        .loc[:, ['datetime', 'fixed_receipts', 'var_receipts', 'receipts']]
        .set_index('datetime')
    )

    return odf

@lru_cache
def _deferred_get_resident_receipts_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.resident_receipts_undiscounted,
        fnc.benefit_discount_rate, 
        shift=1
    )

@lru_cache
def _deferred_get_ev_receipts_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    consumption = fnc._get_ev_consumption()
    if len(consumption) == 0:
        return consumption
    
    odf = (
        consumption
        .assign(
            fixed_receipts = 0.0,
            var_receipts = lambda df: df['consumption'] * fnc.resident_var_per_unit, # No separate tariff for EV charging in Sprake model # pyright: ignore[reportAttributeAccessIssue]
            receipts = lambda df: df['fixed_receipts'] + df['var_receipts']
        )
        .loc[:, ['datetime', 'fixed_receipts', 'var_receipts', 'receipts']]
        .set_index('datetime')
    )

    return odf

@lru_cache
def _deferred_get_ev_receipts_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.ev_receipts_undiscounted, 
        fnc.benefit_discount_rate, 
        shift=1
    )

#@lru_cache
def _deferred_get_export_receipts_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    consumption = fnc._get_grid_export()
    if len(consumption) == 0:
        return consumption
    
    odf = (
        consumption
        .assign(
            fixed_receipts = 0.0,
            var_receipts = lambda df: df['consumption'] * fnc.grid_export_var_per_unit, # pyright: ignore[reportAttributeAccessIssue]
            receipts = lambda df: df['fixed_receipts'] + df['var_receipts']
        )
        .loc[:, ['datetime', 'fixed_receipts', 'var_receipts', 'receipts']]
        .set_index('datetime')
    )
    return odf

@lru_cache
def _deferred_get_export_receipts_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.export_receipts_undiscounted,
        fnc._benefit_discount_rate, 
        shift=1
    )

@lru_cache
def _deferred_get_all_receipts_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    mi_names = ['customer', 'receipt']
    resident = fnc.resident_receipts_undiscounted
    
    if len(resident) == 0:
        return resident

    resident.columns = pd.MultiIndex.from_product([['resident'], resident.columns], names=mi_names)
    
    ev = fnc.ev_receipts_undiscounted
    ev.columns = pd.MultiIndex.from_product([['ev'], ev.columns], names=mi_names)
    
    export = fnc.export_receipts_undiscounted
    export.columns = pd.MultiIndex.from_product([['export'], export.columns], names=mi_names)

    return (
        resident
        .join(ev)
        .join(export)
    )

@lru_cache
def _deferred_get_all_receipts_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    ar = fnc.all_receipts_undiscounted
    if len(ar) == 0:
        return ar
    return apply_discount_factor(
        ar, 
        fnc.benefit_discount_rate, 
        shift=1
    )

@lru_cache
def _deferred_get_total_present_benefits_undiscounted(
    fnc: SprakeFinance,
    horizon: pd.Timestamp|pd.Timedelta|None = None,
) -> float:
    return (
        fnc.all_receipts_undiscounted
        .loc[:, (slice(None), 'receipts')]
        .pipe(sum_all_to_horizon, horizon=horizon)
    )

@lru_cache
def _deferred_get_total_present_benefits_discounted(
    fnc: SprakeFinance,
    horizon: pd.Timestamp|pd.Timedelta|None = None,
) -> float:
    return (
        fnc.all_receipts_discounted
        .loc[:, (slice(None), 'receipts')]
        .pipe(sum_all_to_horizon, horizon=horizon)
    )

@lru_cache
def _deferred_get_import_costs_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    consumption = fnc._get_grid_import()
    if len(consumption) == 0:
        return consumption
    
    odf = (
        consumption
        .assign(
            deltaday = lambda df: delta_days(df['datetime']),
            fixed_costs = lambda df: df['deltaday'] * fnc.grid_import_sc_per_day, # Assume only single standing charge in Sprake model. This may be scaled by capacity in other models # pyright: ignore[reportAttributeAccessIssue]
            var_costs = lambda df: df['consumption'] * fnc.grid_import_var_per_unit, # pyright: ignore[reportAttributeAccessIssue]
            costs = lambda df: df['fixed_costs'] + df['var_costs']
        )
        .loc[:, ['datetime', 'fixed_costs', 'var_costs', 'costs']]
        .set_index('datetime')
    )

    return odf

@lru_cache
def _deferred_get_import_costs_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.import_costs_undiscounted,
        fnc.cost_discount_rate,
        shift=1
    )

@lru_cache
def _deferred_get_om_costs_generation_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    Frame of timeseries of o&m costs of generators.

    Broken down into `wind_costs`, `pv_costs` and `costs` (i.e. total).
    O&M costs are accrued in single monthly payments.
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    wind_om_per_kw_month = fnc.wind_om_per_kw_year / 12 # pyright: ignore[reportAttributeAccessIssue]
    pv_om_per_kw_month = fnc.pv_om_per_kw_year / 12 # pyright: ignore[reportAttributeAccessIssue]
    
    # Capacity in Sprake model is constant, so this is fine:
    wind_om_per_month = wind_om_per_kw_month * fnc.model.generation.generator.generators[0].nameplate_capacity
    pv_om_per_month = pv_om_per_kw_month * fnc.model.generation.generator.generators[1].nameplate_capacity

    # Shift the costs to the end of the first timestep in each month so that it can be
    # picked up in the meter summary statistics
    odf = (
        odf
        .pipe(stats_core.assign_month_index, shift=0)
        .assign(
            deltamonth = lambda df: (df['month_index'] - df['month_index'].shift(1, fill_value = df['month_index'].iloc[0]-1)),
            wind_costs = lambda df: (df['deltamonth'] * wind_om_per_month).shift(1, fill_value = 0.0),
            pv_costs = lambda df: (df['deltamonth'] * pv_om_per_month).shift(1, fill_value = 0.0),
            costs = lambda df: df['wind_costs'] + df['pv_costs']
        )
        .loc[:,['wind_costs','pv_costs','costs']]
    )
    
    return odf

@lru_cache
def _deferred_get_om_costs_generation_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    Frame of timeseries of o&m costs of generators (cost discount applied).

    Broken down into `wind_costs`, `pv_costs` and `costs` (i.e. total).
    O&M costs are accrued in single monthly payments.
    """
    return apply_discount_factor(
        fnc.om_costs_generation_undiscounted,
        fnc.cost_discount_rate,
        shift=1
    )

@lru_cache
def _deferred_get_om_costs_storage_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    Frame of timeseries of o&m costs of storage technologies.

    Broken down into `bess_costs` and `costs` (i.e. total).
    O&M costs are accrued in single monthly payments.
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    bess_om_per_kwh_month = fnc.bess_om_per_kwh_year / 12 # pyright: ignore[reportAttributeAccessIssue]

    # Capacity in Sprake model is constant
    bess_om_per_month = bess_om_per_kwh_month * fnc.model.consumption_storage.storage_params.get('storage_capacity')

    # Shift the costs to the end of the first timestep in each month so that it can be
    # picked up in the meter summary statistics
    odf = (
        odf
        .pipe(stats_core.assign_month_index, shift=0)
        .assign(
            deltamonth = lambda df: (df['month_index'] - df['month_index'].shift(1, fill_value = df['month_index'].iloc[0]-1)),
            bess_costs = lambda df: (df['deltamonth'] * bess_om_per_month).shift(1, fill_value = 0.0),
            costs = lambda df: df['bess_costs']
        )
        .loc[:,['bess_costs','costs']]
    )

    return odf

@lru_cache
def _deferred_get_om_costs_storage_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    Frame of timeseries of o&m costs of storage technologies (cost discount applied).

    Broken down into `bess_costs` and `costs` (i.e. total).
    O&M costs are accrued in single monthly payments.
    """
    return apply_discount_factor(
        fnc.om_costs_storage_undiscounted,
        fnc.cost_discount_rate,
        shift=1
    )

@lru_cache
def _deferred_get_om_costs_billing_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    This is uncosted in Sprake model - return zeros
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    odf = odf.assign(costs = 0.0)
    return odf

@lru_cache
def _deferred_get_om_costs_billing_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.om_costs_billing_undiscounted,
        fnc.cost_discount_rate,
        shift=1
    )

@lru_cache
def _deferred_get_om_costs_other_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    There are no other costs in Sprake model - return zeros
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    odf = odf.assign(costs = 0.0)
    return odf

@lru_cache
def _deferred_get_om_costs_other_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.om_costs_other_undiscounted,
        fnc.cost_discount_rate,
        shift=1
    )

@lru_cache
def _deferred_get_all_recurrent_costs_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    mi_names = ['system','cost']

    generation = fnc.om_costs_generation_undiscounted
    if len(generation) == 0:
        return generation
    generation.columns = pd.MultiIndex.from_product([['generation'], generation.columns], names=mi_names)

    storage = fnc.om_costs_storage_undiscounted
    storage.columns = pd.MultiIndex.from_product([['storage'], storage.columns], names=mi_names)

    billing = fnc.om_costs_billing_undiscounted
    billing.columns = pd.MultiIndex.from_product([['billing'], billing.columns], names=mi_names)

    other = fnc.om_costs_other_undiscounted
    other.columns = pd.MultiIndex.from_product([['other'], other.columns], names=mi_names)

    grid_import = fnc.import_costs_undiscounted
    grid_import.columns = pd.MultiIndex.from_product([['grid_import'], grid_import.columns], names=mi_names)

    return (
        generation 
        .join(storage) 
        .join(billing) 
        .join(other)
        .join(grid_import)
    )

@lru_cache
def _deferred_get_all_recurrent_costs_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.all_recurrent_costs_undiscounted,
        fnc.cost_discount_rate,
        shift=1
    )

@lru_cache
def _deferred_get_capex_costs_generation_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    In Sprake model, all capex is incurred at start of first timestep
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    
    odf['wind_costs'] = 0.0
    odf.iloc[0,-1] = fnc.wind_capex_per_kw * fnc.model.generation.generator.generators[0].nameplate_capacity # pyright: ignore[reportAttributeAccessIssue]

    odf['pv_costs'] = 0.0
    odf.iloc[0,-1] = fnc.pv_capex_per_kw * fnc.model.generation.generator.generators[1].nameplate_capacity # pyright: ignore[reportAttributeAccessIssue]

    odf['costs'] = odf['wind_costs'] + odf['pv_costs']
    return odf

@lru_cache
def _deferred_get_capex_costs_generation_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.capex_costs_generation_undiscounted,
        fnc.cost_discount_rate,
        shift=0
    )

@lru_cache
def _deferred_get_capex_costs_storage_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    
    odf['bess_costs'] = 0.0
    odf.iloc[0,-1] = fnc.bess_capex_per_kwh * fnc.model.consumption_storage.storage_params.get('storage_capacity') # pyright: ignore[reportAttributeAccessIssue]

    odf['costs'] = odf['bess_costs']
    return odf

@lru_cache
def _deferred_get_capex_costs_storage_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.capex_costs_storage_undiscounted,
        fnc.cost_discount_rate, 
        shift=0
    )

@lru_cache
def _deferred_get_capex_costs_distribution_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    In Sprake model, no distribution costs are accounted for
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    odf['costs'] = 0.0
    return odf

@lru_cache
def _deferred_get_capex_costs_distribution_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.capex_costs_distribution_undiscounted,
        fnc.cost_discount_rate,
        shift=0
    )

@lru_cache
def _deferred_get_capex_costs_metering_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    In Sprake model, no metering costs are accounted for
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    odf['costs'] = 0.0
    return odf

@lru_cache
def _deferred_get_capex_costs_metering_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.capex_costs_metering_undiscounted,
        fnc.cost_discount_rate, 
        shift=0
    )

@lru_cache
def _deferred_get_capex_costs_other_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    """
    In Sprake model, no other costs are accounted for
    """
    odf = fnc._get_empty_df()
    if len(odf) == 0:
        return odf
    odf['costs'] = 0.0
    return odf

@lru_cache
def _deferred_get_capex_costs_other_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.capex_costs_other_undiscounted,
        fnc.cost_discount_rate,
        shift=0
    )

@lru_cache
def _deferred_get_all_capex_costs_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    mi_names = ['system','cost']

    generation = fnc.capex_costs_generation_undiscounted
    if len(generation) == 0:
        return generation
    generation.columns = pd.MultiIndex.from_product([['generation'], generation.columns], names=mi_names)

    storage = fnc.capex_costs_storage_undiscounted
    storage.columns = pd.MultiIndex.from_product([['storage'], storage.columns], names=mi_names)

    distribution = fnc.capex_costs_distribution_undiscounted
    distribution.columns = pd.MultiIndex.from_product([['distribution'], distribution.columns], names=mi_names)
    
    metering = fnc.capex_costs_metering_undiscounted
    metering.columns = pd.MultiIndex.from_product([['metering'], metering.columns], names=mi_names)

    other = fnc.capex_costs_other_undiscounted
    other.columns = pd.MultiIndex.from_product([['other'], other.columns], names=mi_names)

    return (
        generation
        .join(storage)
        .join(distribution)
        .join(metering)
        .join(other)
    )

@lru_cache
def _deferred_get_all_capex_costs_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return apply_discount_factor(
        fnc.all_capex_costs_undiscounted,
        fnc.cost_discount_rate,
        shift=0
    )

@lru_cache
def _deferred_get_all_costs_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    recur = fnc.all_recurrent_costs_undiscounted
    if len(recur) == 0:
        return recur

    capex = fnc.all_capex_costs_undiscounted

    recur.columns = pd.MultiIndex.from_tuples(
        [(f"{system}_recurrent", cost) for system, cost in recur.columns],
        names=recur.columns.names
    )
    capex.columns = pd.MultiIndex.from_tuples(
        [(f"{system}_capex", cost) for system, cost in capex.columns],
        names=capex.columns.names
    )

    return recur.join(capex)

@lru_cache
def _deferred_get_all_costs_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    recur = fnc.all_recurrent_costs_discounted
    if len(recur) == 0:
        return recur

    capex = fnc.all_capex_costs_discounted
    
    recur.columns = pd.MultiIndex.from_tuples(
        [(f"{system}_recurrent", cost) for system, cost in recur.columns],
        names=recur.columns.names
    )
    capex.columns = pd.MultiIndex.from_tuples(
        [(f"{system}_capex", cost) for system, cost in capex.columns],
        names=capex.columns.names
    )
    
    return recur.join(capex)

@lru_cache
def _deferred_get_total_present_costs_undiscounted(
    fnc: SprakeFinance, 
    horizon: pd.Timestamp|pd.Timedelta|None = None
) -> float:
    return (
        fnc.all_costs_undiscounted
        .loc[:, (slice(None), 'costs')]
        .pipe(sum_all_to_horizon, horizon=horizon)
    )

@lru_cache
def _deferred_get_total_present_costs_discounted(
    fnc: SprakeFinance, 
    horizon: pd.Timestamp|pd.Timedelta|None = None
) -> float:
    return (
        fnc.all_costs_discounted
        .loc[:, (slice(None), 'costs')]
        .pipe(sum_all_to_horizon, horizon=horizon)
    )

@lru_cache
def _deferred_get_benefits_series_undiscounted(fnc: SprakeFinance) -> pd.Series:
    benefits = fnc.all_receipts_undiscounted.loc[:,(slice(None), 'receipts')]
    srs = benefits.sum(axis=1)
    srs.name = 'benefits'
    return srs

@lru_cache
def _deferred_get_benefits_series_discounted(fnc: SprakeFinance) -> pd.Series:
    benefits = fnc.all_receipts_discounted.loc[:,(slice(None), 'receipts')]
    srs = benefits.sum(axis=1)
    srs.name = 'benefits'
    return srs

@lru_cache
def _deferred_get_costs_series_undiscounted(fnc: SprakeFinance) -> pd.Series:
    benefits = fnc.all_costs_undiscounted.loc[:,(slice(None), 'costs')]
    srs = benefits.sum(axis=1)
    srs.name = 'costs'
    return srs

@lru_cache
def _deferred_get_costs_series_discounted(fnc: SprakeFinance) -> pd.Series:
    benefits = fnc.all_costs_discounted.loc[:,(slice(None), 'costs')]
    srs = benefits.sum(axis=1)
    srs.name = 'costs'
    return srs

@lru_cache
def _deferred_get_benefits_costs_undiscounted(fnc: SprakeFinance) -> pd.DataFrame:
    return pd.merge(
        fnc.get_benefits_series_undiscounted(),
        fnc.get_costs_series_undiscounted(),
        left_index=True,
        right_index=True
    )

@lru_cache
def _deferred_get_benefits_costs_discounted(fnc: SprakeFinance) -> pd.DataFrame:
    return pd.merge(
        fnc.get_benefits_series_discounted(),
        fnc.get_costs_series_discounted(),
        left_index=True,
        right_index=True
    )

@lru_cache
def _deferred_get_benefit_cost_ratio_undiscounted(
    fnc: SprakeFinance,
    horizon: pd.Timestamp|pd.Timedelta|None = None
) -> float:
    total_benefits = fnc.get_total_present_benefits_undiscounted(horizon)
    total_costs = fnc.get_total_present_costs_undiscounted(horizon)

    if total_costs == 0:
        return np.sign(total_benefits) * np.inf
    return total_benefits / total_costs

@lru_cache
def _deferred_get_benefit_cost_ratio_discounted(
    fnc: SprakeFinance,
    horizon: pd.Timestamp|pd.Timedelta|None = None
) -> float:
    total_benefits = fnc.get_total_present_benefits_discounted(horizon)
    total_costs = fnc.get_total_present_costs_discounted(horizon)

    if total_costs == 0:
        return np.sign(total_benefits) * np.inf
    return total_benefits / total_costs

@lru_cache
def _deferred_get_simple_payback_time_days(fnc: SprakeFinance) -> float:
    capex = fnc.all_capex_costs_undiscounted.sum(axis=1)
    net_revenue = fnc.all_receipts_undiscounted.sum(axis=1) - fnc.all_recurrent_costs_undiscounted.sum(axis=1)

    simple_debt = (net_revenue - capex).cumsum().to_numpy().flatten()

    payback = simple_debt >= 0
    # We may want to add a restriction that payback cannot occur within a certain timeframe in
    # more complex models where not all capex is spent day 0
    if np.any(payback):
        payback_index = np.flatnonzero(payback)[0]
        payback_date = net_revenue.index[payback_index]
        payback_delta = payback_date - net_revenue.index[0]
        return payback_delta.days + payback_delta.seconds / 3600.0 / 24.0
    
    max_debt_index = np.argmin(simple_debt)
    max_debt = simple_debt[max_debt_index]

    debt_reduction = simple_debt[-1] - simple_debt[max_debt_index]
    if debt_reduction <= 0:
        return np.inf
    
    dts = pd.Series(net_revenue.index)
    max_debt_deltatime = dts.iloc[max_debt_index] - dts.iloc[0]
    max_debt_days = max_debt_deltatime.days + max_debt_deltatime.seconds / 3600.0 / 24.0

    reduction_period = dts.iloc[-1] - dts.iloc[max_debt_index]
    reduction_days = reduction_period.days + reduction_period.seconds / 3600.0 / 24.0
    grad = debt_reduction / reduction_days

    return max_debt_days - max_debt / grad

@lru_cache
def _deferred_get_net_present_value_undiscounted(
    fnc: SprakeFinance,
    horizon: pd.Timestamp|pd.Timedelta|None = None
) -> float:
    return (
        fnc.get_benefits_costs_undiscounted()
        .assign(costs = lambda df: -df['costs'])
        .pipe(sum_all_to_horizon, horizon=horizon)
    )

@lru_cache
def _deferred_get_net_present_value_discounted(
    fnc: SprakeFinance,
    horizon: pd.Timestamp|pd.Timedelta|None = None
) -> float:
    return (
        fnc.get_benefits_costs_discounted()
        .assign(costs = lambda df: -df['costs'])
        .pipe(sum_all_to_horizon, horizon=horizon)
    )
