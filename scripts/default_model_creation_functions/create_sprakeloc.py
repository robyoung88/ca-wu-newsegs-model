"""
Set up a Sprake Location-Aware Model, Finance and Variables, then save out    
"""

from collections import OrderedDict
import json
import pickle

from newsegsmodelframework.newsegsfinance.sprakefinance import SprakeFinance
from newsegsmodelframework.newsegsvariable.variable import Variable

from config import settings
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.newsegsmodel.sprakelocmodel import SprakeLocModel

_DEFAULT_LOCATION = Location(
    settings.get('SprakeValidationLat'),
    settings.get('SprakeValidationLon')
)

def create_energy_model():
    mdl = SprakeLocModel.from_none()
    mdl.generation.wind_capacity = 200.
    mdl.generation.pv_capacity = 200.
    mdl.consumption_storage.storage_capacity = 4000.
    mdl.consumption_storage.hlp = 0.3
    mdl.consumption_storage.ev_per_unit = 0.2

    # Set the location of the generators appropriately
    mdl.generation.location = _DEFAULT_LOCATION

    # The hub of the wind generator is modelled at 15 m agl, and the PV is modelled at 6 m, 180 degrees az, 35 degrees pitch
    mdl.generation.generator.generators[0].location.height_agl = 15
    mdl.generation.generator.generators[1].location.height_agl = 6
    mdl.generation.generator.generators[1].location.pitch = 35.0
    mdl.generation.generator.generators[1].location.azimuth = 180.0

    # Set the location of the consumers
    mdl.consumption_storage.location = _DEFAULT_LOCATION

    return mdl

def create_finance_model():
    fnc = SprakeFinance.from_none()

    # Apply resident discount
    fnc.resident_var_per_unit = 0.35 * (1 - 0.15)

    # Apply discount factors
    fnc.benefit_discount_rate = 0.035
    fnc.cost_discount_rate = 0.035

    return fnc

def create_variable_list(mdl, fnc):
    with open('data/sprake-variable-config-novalues.json', 'r') as f:
        var_conf_list = json.load(f)
    variables = [Variable(**x) for x in var_conf_list]

    # Synchronise the variable deterministic values with the model and finance we created
    for var in variables:
        if var.is_model_type(mdl):
            var.synchronise_from_model(mdl)
            var.replace_default_parameters()
        elif var.is_model_type(fnc):
            var.synchronise_from_model(fnc)
            var.replace_default_parameters()

    # Update variances etc here
    # It will be easier to work with an ordered dictionary
    vd = OrderedDict()
    for var in variables:
        vd[var.model_parameter] = var

    vd['storage_capacity'].dsa_bounds_type = 'relative'
    vd['storage_capacity'].dsa_lower = 0.9
    vd['storage_capacity'].dsa_upper = 1.1

    # Assume standard deviation of round trip efficiency is 2% - beware that this is Beta sampled
    vd['storage_rte'].set_parameters(vd['storage_rte'].deterministic_value, 0.02)

    # For the sensitivity of the site size, += 10%
    vd['n_units'].dsa_lower = round(0.9*vd['n_units'].deterministic_value)
    vd['n_units'].dsa_upper = round(1.1*vd['n_units'].deterministic_value)

    # Assumption of 20% standard deviation on our other unknowns
    for vn in [
        'hlp',
        'gfa',
        'ref_daily_consumption',
        'seasonal_variance',
        'efficiency_reduction',
        'annual_residential_consumption_per_ev',
        'ev_per_unit',
        'wind_capex_per_kw',
        'wind_om_per_kw_year',
        'pv_capex_per_kw',
        'pv_om_per_kw_year',
        'bess_capex_per_kwh',
        'bess_om_per_kwh_year',
        'resident_sc_per_unit_day',
        'resident_var_per_unit',
        'grid_export_var_per_unit',
        'grid_import_sc_per_day',
        'grid_import_var_per_unit'
    ]:
        vd[vn].dsa_bounds_type = 'interval'
        vd[vn].set_parameters(vd[vn].deterministic_value, 0.2 * vd[vn].deterministic_value)

    return variables

model_file_name =  'sprakeloc-model-default-config'
finance_file_name = 'sprakeloc-finance-default-config'
variable_file_name = 'sprakeloc-variable-default-config'

if __name__ == '__main__':
    mdl = create_energy_model()
    fnc = create_finance_model()
    variables = create_variable_list(mdl, fnc)

    with open(f'data/{model_file_name}.pickle', 'wb') as f:
        mdl.set_state_exclusion_policy('excluded')
        pickle.dump(mdl, f)
        mdl.set_state_exclusion_policy('excluded_and_components')

    with open(f'data/{finance_file_name}.pickle', 'wb') as f:
        fnc.set_state_exclusion_policy('excluded')
        pickle.dump(fnc, f)
        fnc.set_state_exclusion_policy('excluded_and_components')

    variables_ser = [var.to_dict() for var in variables]
    with open(f'data/{variable_file_name}.json', 'w') as f:
        json.dump(variables_ser, f, sort_keys = False, indent = 4)
    
    print('ok')
