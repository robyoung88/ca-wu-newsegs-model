from __future__ import annotations
import re
from collections.abc import Mapping

import numpy as np
import pandas as pd

from src.core.timespan import delta_days
from src.newsegsfinance import NewsegsFinance, apply_discount_factor, sum_all_to_horizon
from src.newsegsmodel import NewsegsModel

HOURS_IN_YEAR = 8760.0

class SprakeFinance(NewsegsFinance):
    _default_name = 'Sprake Finance Module'

    _default_unit_costs = {
        'wind_capex_per_kw': 1500.0,
        'wind_om_per_kw_year': 46.0,

        'pv_capex_per_kw': 1000.0,
        'pv_om_per_kw_year': 19.719,

        'bess_capex_per_kwh': 191.772,
        'bess_om_per_kwh_year': 19.719,

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

    def __init__(self):
        self._name = self._default_name

        self._unit_costs = self._default_unit_costs.copy()
        
        self._benefit_discount_rate = 0.0
        self._cost_discount_rate = 0.0
        
        self._model = None

    def set_unit_costs_from_dict(self, input_dict:Mapping) -> None:
        """
        Update all unit costs using a dictionary.

        Check `SprakeFinance.get_default_unit_costs()` for expected values
        """
        self._unit_costs.update(input_dict)
    
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

    def set_model(self, mdl:NewsegsModel) -> None:
        self._model = mdl
    
    @property
    def benefit_discount_rate(self) -> float:
        return self._benefit_discount_rate

    @benefit_discount_rate.setter
    def benefit_discount_rate(self, v:float) -> None:
        self._benefit_discount_rate = v

    @property
    def cost_discount_rate(self) -> float:
        return self._cost_discount_rate
    
    @cost_discount_rate.setter
    def cost_discount_rate(self, v:float) -> None:
        self._cost_discount_rate = v
    
    def set_discount_rates(self, *drs:float, **kwdrs:float) -> None:
        """
        Set the benefit and cost discount rates

        Note that if only one positional argument is given, both discount rates
        will be set to this value.

        If mixing positional and keyword arguments, note that `benefit_discount_rate`
        is always the first positional argument, and will be over-written by a
        subsequent keyword argument of that key.

        Args:
            benefit_discount_rate: Also first positional argument (float)
            cost_discount_rate: Also second positional argument (float)
        """
        if len(drs) == 1 and len(kwdrs) == 0:
            # Assume that user wants to set both discount rates to nominated value
            dr = drs[0]
            self._benefit_discount_rate = dr
            self._cost_discount_rate = dr
        else:
            argnames = ['benefit_discount_rate', 'cost_discount_rate']
            argdict = dict(zip(argnames, drs))
            argdict.update(kwdrs)
            self._benefit_discount_rate = argdict.get('benefit_discount_rate', self._benefit_discount_rate)
            self._cost_discount_rate = argdict.get('cost_discount_rate', self._cost_discount_rate)

    def _get_empty_df(self) -> pd.DataFrame:
        if self._model is None:
            return pd.DataFrame()
        
        csr = self._model.get_consumption_storage_result()
        if csr is None:
            return pd.DataFrame()
        return pd.DataFrame({
            'datetime': csr.get_timespan().to_pandas(),
        }).set_index('datetime')

    # TODO: Something is very wrong here. Update it to latest API and see if it works better
    def _get_consumption(self, meter_names) -> pd.DataFrame:
        if self._model is None:
            return pd.DataFrame()
        
        csr = self._model.get_consumption_storage_result()
        if csr is None:
            return pd.DataFrame()

        meter_names = csr.get_meter_names()

        meter_indices = [meter_names.index(x) for x in meter_names]
        return pd.DataFrame({
            'datetime': csr.get_timespan().to_pandas(),
            'consumption': csr.meters[meter_indices,:].sum(axis=0),
        })

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
        consumption = self._get_resident_consumption()
        if len(consumption) == 0:
            return consumption
        
        odf = (
            consumption
            .assign(
                resident_units = self._model.consumption_storage.n_units, # In Sprake model, the number of occupied units is constant over time
                deltaday = lambda df: delta_days(df['datetime']),
                fixed_receipts = lambda df: df['resident_units'] * df['deltaday'] * self.resident_sc_per_unit_day,
                var_receipts = lambda df: df['consumption'] * self.resident_var_per_unit,
                receipts = lambda df: df['fixed_receipts'] + df['var_receipts']
            )
            .loc[:, ['datetime', 'fixed_receipts', 'var_receipts', 'receipts']]
            .set_index('datetime')
        )

        return odf

    @property
    def resident_receipts_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.resident_receipts_undiscounted, self._benefit_discount_rate, shift=1)
        
    @property
    def ev_receipts_undiscounted(self) -> pd.DataFrame:
        consumption = self._get_ev_consumption()
        if len(consumption) == 0:
            return consumption
        
        odf = (
            consumption
            .assign(
                fixed_receipts = 0.0,
                var_receipts = lambda df: df['consumption'] * self.resident_var_per_unit, # No separate tariff for EV charging in Sprake model
                receipts = lambda df: df['fixed_receipts'] + df['var_receipts']
            )
            .loc[:, ['datetime', 'fixed_receipts', 'var_receipts', 'receipts']]
            .set_index('datetime')
        )

        return odf

    @property
    def ev_receipts_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.ev_receipts_undiscounted, self._benefit_discount_rate, shift=1)

    @property
    def export_receipts_undiscounted(self) -> pd.DataFrame:
        consumption = self._get_grid_export()
        if len(consumption) == 0:
            return consumption
        
        odf = (
            consumption
            .assign(
                fixed_receipts = 0.0,
                var_receipts = lambda df: df['consumption'] * self.grid_export_var_per_unit,
                receipts = lambda df: df['fixed_receipts'] + df['var_receipts']
            )
            .loc[:, ['datetime', 'fixed_receipts', 'var_receipts', 'receipts']]
            .set_index('datetime')
        )
        return odf

    @property
    def export_receipts_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.export_receipts_undiscounted, self._benefit_discount_rate, shift=1)

    @property
    def all_receipts_undiscounted(self) -> pd.DataFrame:
        mi_names = ['customer', 'receipt']
        resident = self.resident_receipts_undiscounted
        
        if len(resident) == 0:
            return resident

        resident.columns = pd.MultiIndex.from_product([['resident'], resident.columns], names=mi_names)
        ev = self.ev_receipts_undiscounted
        ev.columns = pd.MultiIndex.from_product([['ev'], ev.columns], names=mi_names)
        export = self.export_receipts_undiscounted
        export.columns = pd.MultiIndex.from_product([['export'], export.columns], names=mi_names)

        return resident \
            .join(ev) \
            .join(export)

    @property
    def all_receipts_discounted(self) -> pd.DataFrame:
        ar = self.all_receipts_undiscounted
        if len(ar) == 0:
            return ar
        return apply_discount_factor(ar, self._benefit_discount_rate, shift=1)

    def get_total_present_benefits_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return self.all_receipts_undiscounted \
            .loc[:, (slice(None), 'receipts')] \
            .pipe(sum_all_to_horizon, horizon=horizon)
    
    def get_total_present_benefits_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return self.all_receipts_discounted \
            .loc[:, (slice(None), 'receipts')] \
            .pipe(sum_all_to_horizon, horizon=horizon)
    
    # Costs
    
    @property
    def import_costs_undiscounted(self) -> pd.DataFrame:
        consumption = self._get_grid_import()
        if len(consumption) == 0:
            return consumption
        
        odf = (
            consumption
            .assign(
                deltaday = lambda df: delta_days(df['datetime']),
                fixed_costs = lambda df: df['deltaday'] * self.grid_import_sc_per_day, # Assume only single standing charge in Sprake model. This may be scaled by capacity in other models
                var_costs = lambda df: df['consumption'] * self.grid_import_var_per_unit,
                costs = lambda df: df['fixed_costs'] + df['var_costs']
            )
            .loc[:, ['datetime', 'fixed_costs', 'var_costs', 'costs']]
            .set_index('datetime')
        )

        return odf

    @property
    def import_costs_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.import_costs_undiscounted, self._cost_discount_rate, shift=1)
    
    @property
    def om_costs_generation_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, we will just accrue O&M costs at an hourly rate from first timestep

        It is acknowledged that leapyears will result in additional cost
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        wind_om_per_kw_hour = self.wind_om_per_kw_year / HOURS_IN_YEAR
        pv_om_per_kw_hour = self.pv_om_per_kw_year / HOURS_IN_YEAR
        
        # Capacity in Sprake model is constant, so this is fine:
        wind_om_per_hour = wind_om_per_kw_hour * self._model.generation.generator.generators[0].nameplate_capacity
        pv_om_per_hour = pv_om_per_kw_hour * self._model.generation.generator.generators[1].nameplate_capacity

        odf = (
            odf
            .reset_index()
            .assign(
                deltat = lambda df: (df['datetime'] -df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])).dt.seconds/3600.0,
                wind_costs = lambda df: df['deltat'] * wind_om_per_hour,
                pv_costs = lambda df: df['deltat'] * pv_om_per_hour,
                costs = lambda df: df['wind_costs'] + df['pv_costs']
            )
            .set_index('datetime')
            .loc[:,['wind_costs','pv_costs','costs']]
        )
        return odf
    
    @property
    def om_costs_generation_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.om_costs_generation_undiscounted, self._cost_discount_rate, shift=1)

    @property
    def om_costs_storage_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, we will just accrue O&M costs at an hourly rate from first timestep

        It is acknowledged that leapyears will result in additional cost
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        bess_om_per_kwh_hour = self.bess_om_per_kwh_year / HOURS_IN_YEAR

        # Capacity in Sprake model is constant
        bess_om_per_hour = bess_om_per_kwh_hour * self._model.consumption_storage.storage_params.get('storage_capacity')

        odf = (
            odf
            .reset_index()
            .assign(
                deltat = lambda df: (df['datetime'] -df['datetime'].shift(1, fill_value=df['datetime'].iloc[0])).dt.seconds/3600.0,
                bess_costs = lambda df: df['deltat'] * bess_om_per_hour,
                costs = lambda df: df['bess_costs']
            )
            .set_index('datetime')
            .loc[:,['bess_costs','costs']]
        )

        return odf

    @property
    def om_costs_storage_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.om_costs_storage_undiscounted, self._cost_discount_rate, shift=1)

    @property
    def om_costs_billing_undiscounted(self) -> pd.DataFrame:
        """
        This is uncosted in Sprake model - return zeros
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        odf = odf.assign(costs = 0.0)
        return odf
    
    @property
    def om_costs_billing_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.om_costs_billing_undiscounted, self._cost_discount_rate, shift=1)
    
    @property
    def om_costs_other_undiscounted(self) -> pd.DataFrame:
        """
        There are no other costs in Sprake model - return zeros
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        odf = odf.assign(costs = 0.0)
        return odf

    @property
    def om_costs_other_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.om_costs_other_undiscounted, self._cost_discount_rate, shift=1)

    @property
    def all_recurrent_costs_undiscounted(self) -> pd.DataFrame:
        mi_names = ['system','cost']

        generation = self.om_costs_generation_undiscounted
        if len(generation) == 0:
            return generation
        generation.columns = pd.MultiIndex.from_product([['generation'], generation.columns], names=mi_names)

        storage = self.om_costs_storage_undiscounted
        storage.columns = pd.MultiIndex.from_product([['storage'], storage.columns], names=mi_names)

        billing = self.om_costs_billing_undiscounted
        billing.columns = pd.MultiIndex.from_product([['billing'], billing.columns], names=mi_names)

        other = self.om_costs_other_undiscounted
        other.columns = pd.MultiIndex.from_product([['other'], other.columns], names=mi_names)

        return generation \
            .join(storage) \
            .join(billing) \
            .join(other)

    @property
    def all_recurrent_costs_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.all_recurrent_costs_undiscounted, self._cost_discount_rate, shift=1)

    @property
    def capex_costs_generation_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, all capex is incurred at start of first timestep
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        
        odf['wind_costs'] = 0.0
        odf.iloc[0,-1] = self.wind_capex_per_kw * self._model.generation.generator.generators[0].nameplate_capacity

        odf['pv_costs'] = 0.0
        odf.iloc[0,-1] = self.pv_capex_per_kw * self._model.generation.generator.generators[1].nameplate_capacity

        odf['costs'] = odf['wind_costs'] + odf['pv_costs']
        return odf
    
    @property
    def capex_costs_generation_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.capex_costs_generation_undiscounted, self._cost_discount_rate, shift=0)

    @property
    def capex_costs_storage_undiscounted(self) -> pd.DataFrame:
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        
        odf['bess_costs'] = 0.0
        odf.iloc[0,-1] = self.bess_capex_per_kwh * self._model.consumption_storage.storage_params.get('storage_capacity')

        odf['costs'] = odf['bess_costs']
        return odf

    @property
    def capex_costs_storage_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.capex_costs_storage_undiscounted, self._cost_discount_rate, shift=0)

    @property
    def capex_costs_distribution_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, no distribution costs are accounted for
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        odf['costs'] = 0.0
        return odf
    
    @property
    def capex_costs_distribution_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.capex_costs_distribution_undiscounted, self._cost_discount_rate, shift=0)

    @property
    def capex_costs_metering_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, no metering costs are accounted for
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        odf['costs'] = 0.0
        return odf
    
    @property
    def capex_costs_metering_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.capex_costs_metering_undiscounted, self._cost_discount_rate, shift=0)

    @property
    def capex_costs_other_undiscounted(self) -> pd.DataFrame:
        """
        In Sprake model, no other costs are accounted for
        """
        odf = self._get_empty_df()
        if len(odf) == 0:
            return odf
        odf['costs'] = 0.0
        return odf
    
    @property
    def capex_costs_other_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.capex_costs_other_undiscounted, self._cost_discount_rate, shift=0)

    @property
    def all_capex_costs_undiscounted(self) -> pd.DataFrame:
        mi_names = ['system','cost']

        generation = self.capex_costs_generation_undiscounted
        if len(generation) == 0:
            return generation
        generation.columns = pd.MultiIndex.from_product([['generation'], generation.columns], names=mi_names)

        storage = self.capex_costs_storage_undiscounted
        storage.columns = pd.MultiIndex.from_product([['storage'], storage.columns], names=mi_names)

        distribution = self.capex_costs_distribution_undiscounted
        distribution.columns = pd.MultiIndex.from_product([['distribution'], distribution.columns], names=mi_names)
        
        metering = self.capex_costs_metering_undiscounted
        metering.columns = pd.MultiIndex.from_product([['metering'], metering.columns], names=mi_names)

        other = self.capex_costs_other_undiscounted
        other.columns = pd.MultiIndex.from_product([['other'], other.columns], names=mi_names)

        return generation \
            .join(storage) \
            .join(distribution) \
            .join(metering) \
            .join(other)

    @property
    def all_capex_costs_discounted(self) -> pd.DataFrame:
        return apply_discount_factor(self.all_capex_costs_undiscounted, self._cost_discount_rate, shift=0)

    @property
    def all_costs_undiscounted(self) -> pd.DataFrame:
        recur = self.all_recurrent_costs_undiscounted
        if len(recur) == 0:
            return recur

        capex = self.all_capex_costs_undiscounted

        recur.columns = pd.MultiIndex.from_tuples(
            [(f"{system}_recurrent", cost) for system, cost in recur.columns],
            names=recur.columns.names
        )
        capex.columns = pd.MultiIndex.from_tuples(
            [(f"{system}_capex", cost) for system, cost in capex.columns],
            names=capex.columns.names
        )

        return recur.join(capex)
    
    @property
    def all_costs_discounted(self) -> pd.DataFrame:
        recur = self.all_recurrent_costs_discounted
        if len(recur) == 0:
            return recur

        capex = self.all_capex_costs_discounted
        
        recur.columns = pd.MultiIndex.from_tuples(
            [(f"{system}_recurrent", cost) for system, cost in recur.columns],
            names=recur.columns.names
        )
        capex.columns = pd.MultiIndex.from_tuples(
            [(f"{system}_capex", cost) for system, cost in capex.columns],
            names=capex.columns.names
        )
        
        return recur.join(capex)

    def get_total_present_costs_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return self.all_costs_undiscounted \
            .loc[:, (slice(None), 'costs')] \
            .pipe(sum_all_to_horizon, horizon=horizon)
    
    def get_total_present_costs_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return self.all_costs_discounted \
            .loc[:, (slice(None), 'costs')] \
            .pipe(sum_all_to_horizon, horizon=horizon)

    # Summary vectors
    def get_benefits_series_undiscounted(self) -> pd.Series:
        benefits = self.all_receipts_undiscounted
        srs = benefits.apply(sum, axis=1)
        srs.name = 'benefits'
        return srs

    def get_benefits_series_discounted(self) -> pd.Series:
        benefits = self.all_receipts_discounted
        srs = benefits.apply(sum, axis=1)
        srs.name = 'benefits'
        return srs
    
    def get_costs_series_undiscounted(self) -> pd.Series:
        costs = self.all_costs_undiscounted
        srs = costs.apply(sum, axis=1)
        srs.name = 'costs'
        return srs

    def get_costs_series_discounted(self) -> pd.Series:
        costs = self.all_costs_discounted
        srs = costs.apply(sum, axis=1)
        srs.name = 'costs'
        return srs

    def get_benefits_costs_undiscounted(self) -> pd.DataFrame:
        return pd.merge(
            self.get_benefits_series_undiscounted(),
            self.get_costs_series_undiscounted(),
            left_index=True,
            right_index=True
        )
    
    def get_benefits_costs_discounted(self) -> pd.DataFrame:
        return pd.merge(
            self.get_benefits_series_discounted(),
            self.get_costs_series_discounted(),
            left_index=True,
            right_index=True
        )

    # Derived values
    def get_benefit_cost_ratio_undiscounted(self,  horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        total_benefits = self.get_total_present_benefits_undiscounted(horizon)
        total_costs = self.get_total_present_costs_undiscounted(horizon)

        if total_costs == 0:
            return np.sign(total_benefits) * np.inf
        return total_benefits / total_costs

    def get_benefit_cost_ratio_discounted(self,  horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        total_benefits = self.get_total_present_benefits_discounted(horizon)
        total_costs = self.get_total_present_costs_discounted(horizon)

        if total_costs == 0:
            return np.sign(total_benefits) * np.inf
        return total_benefits / total_costs

    def get_simple_payback_time_days(self) -> float:
        capex = self.all_capex_costs_undiscounted.apply(sum, axis=1)
        net_revenue = self.all_receipts_undiscounted.apply(sum, axis=1) - self.all_recurrent_costs_undiscounted.apply(sum, axis=1)

        simple_debt = (net_revenue - capex).cumsum().values.flatten()

        payback = simple_debt >= 0
        # We may want to add a restriction that payback cannot occur within a certain timeframe in
        # more complex models where not all capex is spent day 0
        if np.any(payback):
            payback_index = np.flatnonzero(payback)[0]
            payback_date = net_revenue.index[payback_index]
            payback_delta = payback_date - net_revenue.index[0]
            return payback_delta.days + payback_delta.seconds / 3600.0 / 24.0
        
        max_debt_index = np.argmin(simple_debt)
        max_debt = simple_debt.iloc[max_debt_index]

        debt_reduction = simple_debt.iloc[-1] - simple_debt.iloc[max_debt_index]
        if debt_reduction <= 0:
            return np.inf
        
        dts = pd.Series(net_revenue.index)
        max_debt_deltatime = dts.iloc[max_debt_index] - dts.iloc[0]
        max_debt_days = max_debt_deltatime.days + max_debt_deltatime.seconds / 3600.0 / 24.0

        reduction_period = dts.iloc[-1] - dts.iloc[max_debt_index]
        reduction_days = reduction_period.days + reduction_period.seconds / 3600.0 / 24.0
        grad = debt_reduction / reduction_days

        return max_debt_days - max_debt / grad
    
    def get_net_present_value_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return self.get_benefits_costs_undiscounted() \
            .assign(costs = lambda df: -df['costs']) \
            .pipe(sum_all_to_horizon, horizon=horizon)

    def get_net_present_value_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        return self.get_benefits_costs_discounted() \
            .assign(costs = lambda df: -df['costs']) \
            .pipe(sum_all_to_horizon, horizon=horizon)
    
    def to_dict(self):
        return {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'unit_costs': self._unit_costs,
            'benefit_discount_rate': self._benefit_discount_rate,
            'cost_discount_rate': self._cost_discount_rate
        }

def _make_unit_cost_property(key: str):
    def getter(self) -> float:
        return self._unit_costs.get(key)

    def setter(self, value: float) -> None:
        self._unit_costs[key] = value

    return property(getter, setter, doc=f"Unit cost for {key}")

for _key in SprakeFinance._default_unit_costs.keys():
    setattr(SprakeFinance, _key, _make_unit_cost_property(_key))
