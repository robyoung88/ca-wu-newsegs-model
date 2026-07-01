"""
Update a blank variables list with values from default Sprake.
"""
from collections import OrderedDict
import pickle
import json

from common import setup_script_env
setup_script_env()

from util import jsonfuncs

from newsegsmodel import sprakemodel
from newsegsfinance import sprakefinance
from newsegsvariable import variable

if __name__ == '__main__':
    with open('data/sprakemodel-validation-config.json', 'r') as f:
        mdl_conf = json.load(f)
    mdl = sprakemodel.SprakeModel.from_dict(mdl_conf)

    with open('data/sprakemodel-validation-finance-config.json', 'r') as f:
        fnc_conf = json.load(f)
    fnc = sprakefinance.SprakeFinance.from_dict(fnc_conf)

    with open('data/sprake-variable-config-novalues.json', 'r') as f:
        var_conf_list = json.load(f)
    variables = [variable.Variable(**x) for x in var_conf_list] # pyright: ignore[reportAbstractUsage]

    for var in variables:
        if var.is_model_type(mdl):
            var.synchronise_from_model(mdl)
        elif var.is_model_type(fnc):
            var.synchronise_from_model(fnc)

    # Update variances etc here
    # It will be easier to work with an ordered dictionary
    vd = OrderedDict()
    for var in variables:
        vd[var.model_parameter] = var

    vd['storage_capacity'].dsa_bounds_type = 'relative'
    vd['storage_capacity'].dsa_lower = 0.9
    vd['storage_capacity'].dsa_upper = 1.1

    # Assume +- 2% rte on mean
    vd['storage_rte'].set_parameters(vd['storage_rte'].deterministic_value, 0.02)

    vd['n_units'].dsa_lower = round(0.9*vd['n_units'].deterministic_value)
    vd['n_units'].dsa_upper = round(1.1*vd['n_units'].deterministic_value)

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
    
    variables_ser = [var.to_dict() for var in variables]
    
    with open('data/sprake-variable-config.json', 'w') as f:
        json.dump(variables_ser, f, sort_keys=False, indent=4)
    