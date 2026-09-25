
from typing import cast

import pandas as pd

class EstimatedEnergyBalance:
    def __init__(self):
        self.estimated_annual_energy_balance = pd.DataFrame([
            {'type': 'Generation', 'label': 'Wind', 'value': 1.},
            {'type': 'Generation', 'label': 'PV', 'value': 1.},
            {'type': 'Consumption', 'label': 'Space heat', 'value': 1.},
            {'type': 'Consumption', 'label': 'Hot water', 'value': 1.},
            {'type': 'Consumption', 'label': 'Direct consumption', 'value': 1.},
            {'type': 'Consumption', 'label': 'EV charging', 'value': 1.}
        ])

        self.estimated_maximum_daily_balance = pd.DataFrame([
            {'label': 'Wind', 'value': 1.},
            {'label': 'PV', 'value': 1.},
            {'label': 'All generation', 'value': 1.},
            {'label': 'Consumption', 'value': 1.},
            {'label': 'Storage size', 'value': 1.},
        ])
    
    def _set_max_gen(self):
        max_wind = self.estimated_maximum_daily_balance.loc[
            self.estimated_maximum_daily_balance['label']=='Wind', 'value'
        ].values[0]
        max_wind = cast(float, max_wind)

        max_pv = self.estimated_maximum_daily_balance.loc[
            self.estimated_maximum_daily_balance['label']=='PV', 'value'
        ].values[0]
        max_pv = cast(float, max_pv)

        PV_CF_ON_MAX_WIND = 0.19
        PV_CF_ON_MAX_DAY = 0.33
        pv_contribution_max_wind = PV_CF_ON_MAX_WIND * max_pv / PV_CF_ON_MAX_DAY

        WIND_CF_ON_MAX_PV = 0.12
        WIND_CF_ON_MAX_DAY = 1.0
        wind_contribution_max_pv = WIND_CF_ON_MAX_PV * max_wind / WIND_CF_ON_MAX_DAY


        if (max_wind + pv_contribution_max_wind) > max_pv:
            # Assume that greatest day is combination of wind and pv
            self.estimated_maximum_daily_balance.loc[
                self.estimated_maximum_daily_balance['label']=='All generation', 'value'
            ] = max_wind + pv_contribution_max_wind
        else:
            # Assume that greatest day is coincident with PV peak
            self.estimated_maximum_daily_balance.loc[
                self.estimated_maximum_daily_balance['label']=='All generation', 'value'
            ] = max_pv + wind_contribution_max_pv
        
    def _set_max_consumption(self):
        MEAN_DAILY_MULTIPLIERS = {
            'Space heat': 4.04,
            'Hot water': 1.12,
            'Direct consumption': 1.13,
            'EV charging': 1.16
        }
        tot = 0.
        for k,v in MEAN_DAILY_MULTIPLIERS.items():
            tot += v * self.estimated_annual_energy_balance.loc[
                self.estimated_annual_energy_balance['label'] == k,
                'value'
            ].values[0] / 365 # pyright: ignore[reportOperatorIssue]
        self.estimated_maximum_daily_balance.loc[
            self.estimated_maximum_daily_balance['label']=='Consumption', 'value'
        ] = tot

    def set_wind_generation(
        self, 
        cap,
        ann_cf: float = 0.25,
        max_day_cf: float = 1.0
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Wind', 'value'
        ] = 8760 * ann_cf * cap

        self.estimated_maximum_daily_balance.loc[
            self.estimated_maximum_daily_balance['label']=='Wind', 'value'
        ] = 24 * cap * max_day_cf
        self._set_max_gen()
    
    def set_pv_generation(
        self, 
        cap, 
        ann_cf: float = 0.125,
        max_day_cf: float = 0.33
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='PV', 'value'
        ] = 8760 * ann_cf * cap

        self.estimated_maximum_daily_balance.loc[
            self.estimated_maximum_daily_balance['label']=='PV', 'value'
        ] = 24 * cap * max_day_cf
        self._set_max_gen()
    
    def set_spaceheat_consumption(
        self,
        n_units,
        hlp,
        gfa,
        ann_hdd: float = 2000.0
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Space heat', 'value'
        ] = n_units * hlp * gfa * ann_hdd * 24 / 1000.
        
        self._set_max_consumption()
    
    def set_dhw_consumption(
        self, 
        n_units, 
        ref_daily_consumption, 
        conversion_efficiency: float = 1.0
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Hot water', 'value'
        ] = 365. * n_units * ref_daily_consumption / conversion_efficiency
        self._set_max_consumption()
    
    def set_direct_consumption(self, n_units, ann_demand_per_unit):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Direct consumption', 'value'
        ] = n_units * ann_demand_per_unit
        self._set_max_consumption()
    
    def set_ev_consumption(
        self,
        n_units, 
        annual_residential_consumption_per_ev, 
        n_evs_per_household
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='EV charging', 'value'
        ] = n_units * annual_residential_consumption_per_ev * n_evs_per_household
        self._set_max_consumption()
    
    def set_storage_capacity(
        self,
        storage_capacity
    ):
        self.estimated_maximum_daily_balance.loc[
            self.estimated_maximum_daily_balance['label']=='Storage size', 'value'
        ] = storage_capacity
