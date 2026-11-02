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
from newsegsmodelframework.newsegssensitivity.common import COST_FRAME_STATISTICS, total_of_cost_frame
from newsegsmodelframework.newsegsvariable.variable import DSA_BOUND

DSA_FLOAT_STATISTIC = Literal[
    'total_present_costs_undiscounted',
    'total_present_costs_discounted',
    'total_present_benefits_undiscounted',
    'total_present_benefits_discounted',
    'net_present_value_undiscounted',
    'net_present_value_discounted',
    'all_capex_costs_undiscounted',
    'all_capex_costs_discounted',
    'all_recurrent_costs_undiscounted',
    'all_recurrent_costs_discounted',
]

def _dsa_float_statistic_mapper(
    stat: DSA_FLOAT_STATISTIC,
    mdl: NewsegsModel,
    fnc: NewsegsFinance
) -> float:
    if stat in COST_FRAME_STATISTICS:
        return total_of_cost_frame(getattr(fnc, stat))

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
    """One row of the results of a DSA: a run of the NewSEGS Energy Model and finance model.

    Args:
        variable_changed: Name of the variable that was varied; `deterministic` for the central run.
        dsa_bound: Which bound of the variable the run used: `lower`, `upper` or `central`.
        variable_value: The value of the variable at the bound, as a string; `-` for the central run.
        mdl: The NewSEGS Energy Model, after the run.
        fnc: The finance model, after the run.
        statistics: The statistics to take from the models.

    Returns:
        Dictionary of `variable`, `bound` and `value`, and the value of each statistic.
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
    precomputed_deterministic: bool = False,
) -> pd.DataFrame:
    """Run a deterministic (one-way) sensitivity analysis of a metamodel.

    First the central run, with every variable at its deterministic value. Then, for each variable that is
    selectable and selected for DSA, two runs: with the variable at its lower and at its upper bound, and all
    others at their deterministic values. Afterwards every variable is returned to its deterministic value.

    Args:
        mm: The metamodel.
        statistics: The statistics to calculate for each run.
        progress: Function reporting progress, called with the number of runs completed and the total.
        cancel_status: Function returning whether cancellation has been requested; checked before each variable.
        precomputed_deterministic: Whether the metamodel already holds valid results of the deterministic run, so that
            the central run need not be repeated.

    Returns:
        Dataframe with a row for each run, and columns `variable`, `bound`, `value` and the statistics.

    Raises:
        InterruptedError: if cancellation is requested.
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
    if not precomputed_deterministic:
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
                