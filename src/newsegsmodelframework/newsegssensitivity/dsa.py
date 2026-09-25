"""
Functions and classes for performing deterministic sensitivity analysis
"""
from typing import Any, Callable, Literal, Sequence, cast
from typing import get_args

import pandas as pd

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsvariable.variable import DSA_BOUND

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

def make_dsa_result(
    variable_changed: str,
    dsa_bound: str,
    variable_value: str,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    statistics: Sequence[DSA_FLOAT_STATISTIC]
) -> dict[str, Any]:
    """_summary_

    Args:
        variable_changed (str): _description_
        dsa_bound (str): _description_
        variable_value (str): _description_
        mdl (NewsegsModel): _description_
        fnc (NewsegsFinance): _description_
        statistics (Sequence[DSA_FLOAT_STATISTIC]): _description_

    Returns:
        dict[str, Any]: _description_
    """
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
    statistics: Sequence[DSA_FLOAT_STATISTIC] = get_args(DSA_FLOAT_STATISTIC),
    progress: Callable[[int, int], None] | None = None,
    cancel_status: Callable[[], bool] | None = None,
) -> pd.DataFrame:
    """_summary_

    Args:
        mm (NewsegsMetaModel): _description_
        statistics (Sequence[DSA_FLOAT_STATISTIC], optional): _description_. Defaults to get_args(DSA_FLOAT_STATISTIC).
        progress (Callable[[int, int], None] | None, optional): _description_. Defaults to None.

    Returns:
        pd.DataFrame: _description_
    """
    variables = mm.variables.values()
    mdl = mm.model
    fnc = mm.finance

    n_calcs = 1
    for v in variables:
        if v.dsa_possible and v.dsa_selected:
            n_calcs += 1
    prog_i = 0
    if progress is not None:
        progress(prog_i, n_calcs)

    if cancel_status is None:
        cancel_status = lambda: False

    if cancel_status():
        raise InterruptedError('PSA job cancelled')
    
    results = []

    # Run 0 - deterministic
    for v in variables:
        v.update_model(mdl)
        v.update_model(fnc)
    
    mdl.run()
    fnc.run()
    results.append(
        make_dsa_result('deterministic', 'central', '-', mdl, fnc, statistics)
    )
    if progress is not None:
        prog_i += 1
        progress(prog_i, n_calcs)

    # Other results
    for v in variables:
        v.dsa_active = True
    
    for v in variables:
        if v.dsa_possible and v.dsa_selected:
            v.dsa_focussed = True

            try:
                if cancel_status():
                    raise InterruptedError('PSA job cancelled')
                for bound in ['lower', 'upper']:
                    bound = cast(DSA_BOUND, bound)
                    v.update_model_dsa(mdl, bound)
                    v.update_model_dsa(fnc, bound)
                    mdl.run()
                    fnc.run()
                    results.append(
                        make_dsa_result(v.name, bound, str(v.get_dsa_value(bound)), mdl, fnc, statistics)
                    )
            finally:
                v.dsa_focussed = False
                v.update_model(mdl)
                v.update_model(fnc)

            if progress is not None:
                prog_i += 1
                progress(prog_i, n_calcs)

    for v in variables:
        v.dsa_active = False
    
    results = pd.DataFrame(results)
    return results

class DSAComponent(NewsegsComponent):
    """A container for DSA settings"""

    component_type = 'dsa'

    statistics: Sequence[DSA_FLOAT_STATISTIC] = get_args(DSA_FLOAT_STATISTIC)

    def __init__(
        self,
        **kwargs
    ):
        super().__init__(**kwargs)
        for k, v in kwargs.items():
            if hasattr(self, k):
                setattr(self, k, v)
                