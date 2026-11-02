"""Rough estimates of the annual energy balance of a site, used to give feedback while inputs are edited.
"""

from typing import cast

import pandas as pd

class EstimatedEnergyBalance:
    """A rough estimate of the annual energy balance, and the maximum daily balance, of a site.

    Generation and consumption are estimated from capacities, capacity factors and the number of households with simple formulae, so that the interface
    can give feedback as inputs are changed without running a NewSEGS Energy Model. Each `set_...` method updates one line of the estimate.
    """
    def __init__(self):
        self.estimated_annual_energy_balance = pd.DataFrame([
            {'type': 'Generation', 'label': 'Wind', 'value': 1.},
            {'type': 'Generation', 'label': 'PV', 'value': 1.},
            {'type': 'Consumption', 'label': 'Space heat', 'value': 1.},
            {'type': 'Consumption', 'label': 'Hot water', 'value': 1.},
            {'type': 'Consumption', 'label': 'Direct consumption', 'value': 1.},
            {'type': 'Consumption', 'label': 'EV charging', 'value': 1.}
        ]).set_index('label', drop = False)

        self.estimated_maximum_daily_balance = pd.DataFrame([
            {'label': 'Wind', 'value': 1.},
            {'label': 'PV', 'value': 1.},
            {'label': 'All generation', 'value': 1.},
            {'label': 'Consumption', 'value': 1.},
            {'label': 'Storage size', 'value': 1.},
        ]).set_index('label', drop = False)
    
    def _set_max_gen(self):
        max_wind = self.estimated_maximum_daily_balance.at['Wind', 'value']
        max_wind = cast(float, max_wind)

        max_pv = self.estimated_maximum_daily_balance.at['PV', 'value']
        max_pv = cast(float, max_pv)

        PV_CF_ON_MAX_WIND = 0.19
        PV_CF_ON_MAX_DAY = 0.33
        pv_contribution_max_wind = PV_CF_ON_MAX_WIND * max_pv / PV_CF_ON_MAX_DAY

        WIND_CF_ON_MAX_PV = 0.12
        WIND_CF_ON_MAX_DAY = 1.0
        wind_contribution_max_pv = WIND_CF_ON_MAX_PV * max_wind / WIND_CF_ON_MAX_DAY


        if (max_wind + pv_contribution_max_wind) > max_pv:
            # Assume that greatest day is combination of wind and pv
            self.estimated_maximum_daily_balance.at['All generation', 'value'] = max_wind + pv_contribution_max_wind
        else:
            # Assume that greatest day is coincident with PV peak
            self.estimated_maximum_daily_balance.at['All generation', 'value'] = max_pv + wind_contribution_max_pv
        
    def _set_max_consumption(self):
        MEAN_DAILY_MULTIPLIERS = {
            'Space heat': 4.04,
            'Hot water': 1.12,
            'Direct consumption': 1.13,
            'EV charging': 1.16
        }
        tot = 0.
        for k,v in MEAN_DAILY_MULTIPLIERS.items():
            tot += v * self.estimated_annual_energy_balance.at[k,'value'] / 365 
        self.estimated_maximum_daily_balance.at['Consumption', 'value'] = tot

    def set_wind_generation(
        self, 
        cap,
        ann_cf: float = 0.25,
        max_day_cf: float = 1.0
    ):
        """Estimate the generation from wind.

        Annually, `8760 * ann_cf * cap`; on the maximum day, `24 * cap * max_day_cf`.

        Args:
            cap: Capacity (kW).
            ann_cf: Annual capacity factor.
            max_day_cf: Capacity factor on the day of the maximum.
        """
        self.estimated_annual_energy_balance.at['Wind', 'value'] = 8760 * ann_cf * cap

        self.estimated_maximum_daily_balance.at['Wind', 'value'] = 24 * cap * max_day_cf
        self._set_max_gen()
    
    def set_pv_generation(
        self, 
        cap, 
        ann_cf: float = 0.125,
        max_day_cf: float = 0.33
    ):
        """Estimate the generation from PV.

        Annually, `8760 * ann_cf * cap`; on the maximum day, `24 * cap * max_day_cf`.

        Args:
            cap: Capacity (kW).
            ann_cf: Annual capacity factor.
            max_day_cf: Capacity factor on the day of the maximum.
        """
        self.estimated_annual_energy_balance.at['PV', 'value'] = 8760 * ann_cf * cap

        self.estimated_maximum_daily_balance.at['PV', 'value'] = 24 * cap * max_day_cf
        self._set_max_gen()
    
    def set_spaceheat_consumption(
        self,
        n_units,
        hlp,
        gfa,
        ann_hdd: float = 2000.0
    ):
        """Estimate the consumption for space heating.

        Households times heat loss parameter times floor area times annual heating degree days, converted to kWh.

        Args:
            n_units: Number of households.
            hlp: Heat loss parameter.
            gfa: Gross floor area of a dwelling (m^2).
            ann_hdd: Annual heating degree days.
        """
        self.estimated_annual_energy_balance.at['Space heat', 'value'] = n_units * hlp * gfa * ann_hdd * 24 / 1000.
        
        self._set_max_consumption()
    
    def set_dhw_consumption(
        self, 
        n_units, 
        ref_daily_consumption, 
        conversion_efficiency: float = 1.0
    ):
        """Estimate the consumption for domestic hot water.

        Households times the reference daily consumption times 365, divided by the conversion efficiency.

        Args:
            n_units: Number of households.
            ref_daily_consumption: Reference daily hot water consumption of a household (kWh).
            conversion_efficiency: Efficiency of conversion to hot water.
        """
        self.estimated_annual_energy_balance.at['Hot water', 'value'] = 365. * n_units * ref_daily_consumption / conversion_efficiency
        self._set_max_consumption()
    
    def set_direct_consumption(self, n_units, ann_demand_per_unit):
        """Estimate the direct (appliance) consumption.

        Households times the annual demand per household.

        Args:
            n_units: Number of households.
            ann_demand_per_unit: Annual demand per household (kWh).
        """
        self.estimated_annual_energy_balance.at['Direct consumption', 'value'] = n_units * ann_demand_per_unit
        self._set_max_consumption()
    
    def set_ev_consumption(
        self,
        n_units, 
        annual_residential_consumption_per_ev, 
        n_evs_per_household
    ):
        """Estimate the consumption for EV charging.

        Households times the annual residential consumption per EV times the number of EVs per household.

        Args:
            n_units: Number of households.
            annual_residential_consumption_per_ev: Annual residential charging consumption of an EV (kWh).
            n_evs_per_household: Number of EVs per household.
        """
        self.estimated_annual_energy_balance.at['EV charging', 'value'] = n_units * annual_residential_consumption_per_ev * n_evs_per_household
        self._set_max_consumption()
    
    def set_storage_capacity(
        self,
        storage_capacity
    ):
        """Set the storage capacity of the estimate.

        Args:
            storage_capacity: Storage capacity (kWh).
        """
        self.estimated_maximum_daily_balance.at['Storage size', 'value'] = storage_capacity
