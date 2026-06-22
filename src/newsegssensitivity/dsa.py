"""
Functions and classes for performing deterministic sensitivity analysis
"""
from typing import Any, Literal, Sequence, cast
from typing import get_args

import pandas as pd

from newsegsmetamodel import NewsegsMetaModel
from newsegsmodel import NewsegsModel
from newsegsfinance import NewsegsFinance
from newsegsvariable.variable import DSA_BOUND

DSA_FLOAT_STATISTIC = Literal[
    'total_present_costs_undiscounted',
    'total_present_costs_discounted',
    'total_present_benefits_undiscounted',
    'total_present_benefits_discounted',
    'net_present_value_undiscounted',
    'net_present_value_discounted'
]

def _dsa_float_statistic_mapper(
    stat: DSA_FLOAT_STATISTIC,
    mdl: NewsegsModel,
    fnc: NewsegsFinance
) -> float:
    fnc_attrname = 'get_' + stat
    if hasattr(fnc, fnc_attrname):
        return getattr(fnc, fnc_attrname)()
    #elif hasattr(type(fnc), fnc_attrname):
    #    return getattr(type(fnc), fnc_attrname)(fnc)
    
    # Nothing to look for here yet, but included for future expansion
    if hasattr(mdl, fnc_attrname):
        return getattr(mdl, fnc_attrname)()
    #elif hasattr(type(mdl), fnc_attrname):
    #    return getattr(type(mdl), fnc_attrname)(mdl)
    
    raise ValueError(f'stat {stat} is not known as a DSA statistic')

def _make_dsa_result(
    variable_changed: str,
    dsa_bound: str,
    variable_value: str,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    statistics: Sequence[DSA_FLOAT_STATISTIC]
) -> dict[str, Any]:
    res: dict[str, Any] = {
        'variable': variable_changed,
        'bound': dsa_bound,
        'value': variable_value,
    }
    for stat in statistics:
        res[stat] = _dsa_float_statistic_mapper(stat, mdl, fnc)
    return res
    
def run_dsa(
    mm: NewsegsMetaModel,
    statistics: Sequence[DSA_FLOAT_STATISTIC] = get_args(DSA_FLOAT_STATISTIC)
) -> pd.DataFrame:
    variables = mm.variables
    mdl = mm.model
    fnc = mm.finance

    results = []

    # Run 0 - deterministic
    for v in variables:
        v.update_model(mdl)
        v.update_model(fnc)
    
    mdl.run()
    fnc.run()
    results.append(
        _make_dsa_result('deterministic', 'central', '-', mdl, fnc, statistics)
    )

    # Other results
    for v in variables:
        v.dsa_active = True
    
    for v in variables:
        if v.dsa_possible and v.dsa_selected:
            v.dsa_focussed = True

            try:
                for bound in ['lower', 'upper']:
                    bound = cast(DSA_BOUND, bound)
                    v.update_model_dsa(mdl, bound)
                    v.update_model_dsa(fnc, bound)
                    mdl.run()
                    fnc.run()
                    results.append(
                        _make_dsa_result(v.name, bound, str(v.get_dsa_value(bound)), mdl, fnc, statistics)
                    )
            finally:
                v.dsa_focussed = False
                v.update_model(mdl)
                v.update_model(fnc)

    for v in variables:
        v.dsa_active = False
    
    results = pd.DataFrame(results)
    return results
