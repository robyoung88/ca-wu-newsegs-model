
import pandas as pd

class EstimatedEnergyBalance:
    def __init__(self):
        self.estimated_annual_energy_balance = pd.DataFrame([
            {'type': 'Generation', 'label': 'Wind', 'value': 1},
            {'type': 'Generation', 'label': 'PV', 'value': 1},
            {'type': 'Consumption', 'label': 'Space heat', 'value': 1},
            {'type': 'Consumption', 'label': 'Hot water', 'value': 1},
            {'type': 'Consumption', 'label': 'Direct consumption', 'value': 1},
            {'type': 'Consumption', 'label': 'EV charging', 'value': 1}
        ])
    
    def set_wind_generation(self, cap, ann_cf: float = 0.25):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Wind', 'value'
        ] = 8760 * ann_cf * cap
    
    def set_pv_generation(self, cap, ann_cf: float = 0.125):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='PV', 'value'
        ] = 8760 * ann_cf * cap
    
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
    
    def set_dhw_consumption(
        self, 
        n_units, 
        ref_daily_consumption, 
        conversion_efficiency: float = 1.0
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Hot water', 'value'
        ] = 365. * n_units * ref_daily_consumption / conversion_efficiency
    
    def set_direct_consumption(self, n_units, ann_demand_per_unit):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='Direct consumption', 'value'
        ] = n_units * ann_demand_per_unit
    
    def set_ev_consumption(
        self,
        n_units, 
        annual_residential_consumption_per_ev, 
        n_evs_per_household
    ):
        self.estimated_annual_energy_balance.loc[
            self.estimated_annual_energy_balance['label']=='EV charging', 'value'
        ] = n_units * annual_residential_consumption_per_ev * n_evs_per_household
