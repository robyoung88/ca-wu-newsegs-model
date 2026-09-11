from typing import cast

from newsegsmodelapp.components import energy_balance_estimation
from newsegsmodelapp.newsegsbrowser.callbacks import model_creation_sprake
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsvariable import variable

def _get_val(mm, key) -> int | float:
    return cast(variable.NumericScalarVariable, mm.variables.get(key)).deterministic_value

def update_estimated_energy_balance(
    mm: NewsegsMetaModel,
    energy_balance: energy_balance_estimation.EstimatedEnergyBalance
) -> energy_balance_estimation.EstimatedEnergyBalance:
    # Generation
    wind_capacity = _get_val(mm, 'gen_input.wind_capacity.0')
    pv_capacity = _get_val(mm, 'gen_input.pv_capacity.0')
    energy_balance.set_wind_generation(wind_capacity)
    energy_balance.set_pv_generation(pv_capacity)

    # Consumption
    n_units = _get_val(mm, 'bc_input.n_units.0')
    
    hlp = _get_val(mm, 'bc_input.hlp.0')
    gfa = _get_val(mm, 'bc_input.gfa.0')
    # Could use this, but default is more than ok
    # ann_hdd = model_creation_sprake.MODEL_CONSTANTS['sprake_model']['sprake_ref_hdd_per_year']
    energy_balance.set_spaceheat_consumption(n_units, hlp, gfa)

    ref_daily_consumption = _get_val(mm, 'bc_input.ref_daily_consumption.0')
    # Assume conversion efficiency of 1
    energy_balance.set_dhw_consumption(n_units, ref_daily_consumption)

    efficiency_reduction = _get_val(mm, 'dc_input.efficiency_reduction.0')
    energy_balance.set_direct_consumption(
        n_units,
        (1 - efficiency_reduction) * model_creation_sprake.MODEL_CONSTANTS['sprake_model']['sprake_ref_appliance_consumption_annual']
    )

    n_evs_per_household = _get_val(mm, 'dc_input.n_evs_per_household.0')
    ev_consumption_per_year = _get_val(mm, 'dc_input.annual_residential_consumption_per_ev.0')
    energy_balance.set_ev_consumption(n_units, ev_consumption_per_year, n_evs_per_household)

    stor_cap = _get_val(mm, 'stor_input.storage_capacity.0')
    energy_balance.set_storage_capacity(stor_cap)

    return energy_balance
