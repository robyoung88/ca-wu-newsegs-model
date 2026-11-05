"""
Functions and classes for performing deterministic sensitivity analysis
"""
from typing import Any, Callable, Literal, Sequence, cast
from typing import get_args

import numpy as np
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

DSA_PAIRWISE_STATISTIC = Literal[
    'incremental_net_monetary_value_discounted',
    'incremental_net_monetary_value_undiscounted',
    'incremental_benefit_cost_ratio_discounted',
    'incremental_benefit_cost_ratio_undiscounted',
    'incremental_total_costs_discounted',
    'incremental_total_costs_undiscounted',
    'incremental_total_benefits_discounted',
    'incremental_total_benefits_undiscounted',
    'incremental_all_capex_costs_discounted',
    'incremental_all_capex_costs_undiscounted',
    'incremental_all_recurrent_costs_discounted',
    'incremental_all_recurrent_costs_undiscounted',
]
"""Statistics comparing two metamodels (a comparator against a reference) in a whole-project DSA."""

DSA_MULTIPLE_INDEX_COLUMNS = ['metamodel', 'varid', 'varied', 'variable', 'bound', 'value']
"""The columns of the results of `run_dsa_multiple` which precede the statistics."""

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

    # The central run, and a run at each bound of each selected variable
    n_calcs = 1
    for v in variables:
        if v.dsa_possible and v.dsa_selected:
            n_calcs += 2
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
                    if progress is not None:
                        prog_i += 1
                        progress(prog_i, n_calcs)
            finally:
                v.dsa_focussed = False
                v.update_model(mdl)
                v.update_model(fnc)

    for v in variables:
        v.dsa_active = False
    
    results = pd.DataFrame(results)
    return results

def _dsa_variable_is_candidate(var) -> bool:
    return bool(var.dsa_possible and var.dsa_selectable)

def synchronise_dsa_selection(metamodels: Sequence[NewsegsMetaModel]) -> list[str]:
    """Make the DSA selection of variables common to several metamodels consistent.

    A variable (identified by its varid) which is selected for DSA in any of the metamodels is selected in all of
    the metamodels that have it; otherwise it is deselected in all. Only variables which are DSA-possible and
    selectable are changed. A variable shared by metamodels is a single instance, so is already consistent;
    independent instances with the same varid keep their own bounds.

    Args:
        metamodels: The metamodels.

    Returns:
        The varids of the selected variables, in the order in which they first appear in the metamodels.
    """
    order: dict[str, None] = {}
    selected: set[str] = set()
    for mm in metamodels:
        for varid, var in mm.variables.items():
            order.setdefault(varid, None)
            if _dsa_variable_is_candidate(var) and var.dsa_selected:
                selected.add(varid)

    for mm in metamodels:
        for varid, var in mm.variables.items():
            if not _dsa_variable_is_candidate(var):
                continue
            is_selected = varid in selected
            if var.dsa_selected != is_selected:
                var.dsa_selected = is_selected

    return [x for x in order if x in selected]

def run_dsa_multiple(
    metamodels: Sequence[NewsegsMetaModel],
    statistics: Sequence[DSA_FLOAT_STATISTIC] = get_args(DSA_FLOAT_STATISTIC),
    progress: Callable[[int, int], None] | None = None,
    cancel_status: Callable[[], bool] | None = None,
    precomputed_deterministic: bool = False,
    synchronise: bool = True,
) -> pd.DataFrame:
    """Run a deterministic sensitivity analysis across several metamodels (a whole-project DSA).

    First the central run of each metamodel. Then, for each variable selected for DSA, and for each of its
    bounds (lower, then upper), every metamodel is evaluated with that variable at the bound and all others at
    their deterministic values, so that the metamodels can be compared at the same bound limit. Each metamodel
    uses its own bounds for the variable, which may differ where its variable is an independent instance.

    A metamodel which does not have the variable, or for which it cannot be varied, is not run again: its row
    repeats its deterministic statistics, with `varied` False, so that every metamodel has a row for every
    variable and bound.

    Args:
        metamodels: The metamodels.
        statistics: The statistics to calculate for each run.
        progress: Function reporting progress, called with the number of runs completed and the total.
        cancel_status: Function returning whether cancellation has been requested; checked before each variable.
        precomputed_deterministic: Whether the metamodels already hold valid results of their deterministic runs,
            so that the central runs need not be repeated.
        synchronise: Whether to make the DSA selection of common variables consistent first (see
            `synchronise_dsa_selection`).

    Returns:
        Dataframe with a row for each metamodel for each run, and columns `metamodel` (id), `varid`, `varied`,
        `variable` (label), `bound`, `value` and the statistics. The central rows come first, with an empty varid.

    Raises:
        InterruptedError: if cancellation is requested.
    """
    metamodels = list(metamodels)
    if cancel_status is None:
        cancel_status = lambda: False

    if synchronise:
        varids = synchronise_dsa_selection(metamodels)
    else:
        order: dict[str, None] = {}
        for mm in metamodels:
            for varid, var in mm.variables.items():
                if var.dsa_possible and var.dsa_selected:
                    order.setdefault(varid, None)
        varids = list(order)

    # Which metamodels vary each variable, and the label of each variable
    varying: dict[str, set[int]] = {}
    labels: dict[str, str] = {}
    for varid in varids:
        varying[varid] = set()
        for idx, mm in enumerate(metamodels):
            var = mm.variables.get(varid)
            if var is None:
                continue
            labels.setdefault(varid, var.name)
            if var.dsa_possible and var.dsa_selected:
                varying[varid].add(idx)

    n_calcs = len(metamodels) + 2 * sum(len(x) for x in varying.values())
    prog_i = 0
    def _report():
        if progress is not None:
            progress(prog_i, n_calcs)
    _report()

    if cancel_status():
        raise InterruptedError('DSA job cancelled')

    results = []

    # Central runs
    deterministic_results = []
    for mm in metamodels:
        if not precomputed_deterministic:
            for v in mm.variables.values():
                v.update_model(mm.model)
                v.update_model(mm.finance)
            mm.model.run()
            mm.finance.run()
        res = make_dsa_result('deterministic', 'central', '-', mm.model, mm.finance, statistics)
        deterministic_results.append(res)
        results.append({'metamodel': mm.id, 'varid': '', 'varied': False, **res})
        prog_i += 1
        _report()

    # Shared variables are a single instance; flag each instance once
    all_variables = {id(v): v for mm in metamodels for v in mm.variables.values()}.values()
    for v in all_variables:
        v.dsa_active = True

    try:
        for varid in varids:
            if cancel_status():
                raise InterruptedError('DSA job cancelled')
            for bound in ('lower', 'upper'):
                bound = cast(DSA_BOUND, bound)
                for idx, mm in enumerate(metamodels):
                    if idx in varying[varid]:
                        var = mm.variables[varid]
                        var.dsa_focussed = True
                        try:
                            var.update_model_dsa(mm.model, bound)
                            var.update_model_dsa(mm.finance, bound)
                            mm.model.run()
                            mm.finance.run()
                            res = make_dsa_result(
                                labels[varid], bound, str(var.get_dsa_value(bound)),
                                mm.model, mm.finance, statistics
                            )
                        finally:
                            var.dsa_focussed = False
                            var.update_model(mm.model)
                            var.update_model(mm.finance)
                        varied = True
                        prog_i += 1
                        _report()
                    else:
                        res = {
                            **deterministic_results[idx],
                            'variable': labels[varid], 'bound': bound, 'value': '-'
                        }
                        varied = False
                    results.append({'metamodel': mm.id, 'varid': varid, 'varied': varied, **res})
    finally:
        for v in all_variables:
            v.dsa_active = False

    return pd.DataFrame(results, columns = DSA_MULTIPLE_INDEX_COLUMNS + list(statistics))

def dsa_multiple_for_metamodel(
    results: pd.DataFrame,
    metamodel_id: str,
    varied_only: bool = True,
) -> pd.DataFrame:
    """The results of one metamodel from a whole-project DSA, in the form of the results of `run_dsa`.

    Args:
        results: The results of `run_dsa_multiple`.
        metamodel_id: Id of the metamodel.
        varied_only: Whether to leave out the variables which the metamodel did not vary.

    Returns:
        Dataframe with columns `variable`, `bound`, `value` and the statistics, the central run first.

    Raises:
        KeyError: if the metamodel is not in the results.
    """
    mm_results = results.loc[results['metamodel'] == metamodel_id, :]
    if len(mm_results) == 0:
        raise KeyError(f'Metamodel {metamodel_id} not found in DSA results')
    if varied_only:
        mm_results = mm_results.loc[mm_results['varied'] | (mm_results['bound'] == 'central'), :]
    return (
        mm_results
        .drop(columns = ['metamodel', 'varid', 'varied'])
        .reset_index(drop = True)
    )

def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """numerator / denominator, infinite (signed as the numerator) where only the denominator is zero, and NaN where both are."""
    num = numerator.to_numpy(dtype = np.float64)
    den = denominator.to_numpy(dtype = np.float64)
    with np.errstate(divide = 'ignore', invalid = 'ignore'):
        ratio = np.where(
            den == 0,
            np.where(num == 0, np.nan, np.sign(num) * np.inf),
            num / np.where(den == 0, 1.0, den)
        )
    return pd.Series(ratio, index = numerator.index)

def dsa_pairwise(
    results: pd.DataFrame,
    comparator_id: str,
    reference_id: str,
) -> pd.DataFrame:
    """Compare two metamodels of a whole-project DSA: the comparator against the reference, for every run.

    For each run (the central run, and each variable at each bound) the statistics of the reference are
    subtracted from those of the comparator:

    - incremental total costs: the change in total present costs;
    - incremental total benefits: the change in total present benefits;
    - incremental net monetary value: incremental benefits less incremental costs;
    - incremental benefit to cost ratio: incremental benefits divided by incremental costs. It is infinite
      (signed as the incremental benefits) where only the incremental costs are zero, and NaN where both are;
    - incremental capex and opex: the change in total capital expenditure and in total recurrent costs. These are
      NaN if the results do not include the capex and opex statistics.

    each discounted and undiscounted.

    Args:
        results: The results of `run_dsa_multiple`, which must include the total present costs and benefits,
            discounted and undiscounted.
        comparator_id: Id of the comparator metamodel.
        reference_id: Id of the reference metamodel.

    Returns:
        Dataframe in the form of the results of `run_dsa` - columns `variable`, `bound`, `value` and the pairwise
        statistics - with the central run first. `value` gives the values of the variable in the comparator and the
        reference, separated by ` | `.

    Raises:
        KeyError: if a metamodel, or a required statistic, is not in the results.
    """
    required = [
        f'total_present_{x}_{y}' for x in ('costs', 'benefits') for y in ('discounted', 'undiscounted')
    ]
    missing = [x for x in required if x not in results.columns]
    if missing:
        raise KeyError(f'DSA results do not include the statistics required for pairwise comparison: {missing}')

    def _frame(mm_id):
        df = results.loc[results['metamodel'] == mm_id, :]
        if len(df) == 0:
            raise KeyError(f'Metamodel {mm_id} not found in DSA results')
        return df.set_index(['varid', 'bound'])

    comp = _frame(comparator_id)
    ref = _frame(reference_id).reindex(comp.index)

    odf = pd.DataFrame(
        {
            'variable': comp['variable'],
            'value': comp['value'].astype(str) + ' | ' + ref['value'].astype(str),
        },
        index = comp.index
    )
    for disc in ('discounted', 'undiscounted'):
        d_costs = comp[f'total_present_costs_{disc}'] - ref[f'total_present_costs_{disc}']
        d_benefits = comp[f'total_present_benefits_{disc}'] - ref[f'total_present_benefits_{disc}']
        odf[f'incremental_net_monetary_value_{disc}'] = d_benefits - d_costs
        odf[f'incremental_benefit_cost_ratio_{disc}'] = _safe_ratio(d_benefits, d_costs)
        odf[f'incremental_total_costs_{disc}'] = d_costs
        odf[f'incremental_total_benefits_{disc}'] = d_benefits
        for cost in ('all_capex_costs', 'all_recurrent_costs'):
            stat = f'{cost}_{disc}'
            odf[f'incremental_{stat}'] = comp[stat] - ref[stat] if stat in results.columns else np.nan

    odf = odf.reset_index().drop(columns = ['varid'])
    return odf.loc[:, ['variable', 'bound', 'value'] + list(get_args(DSA_PAIRWISE_STATISTIC))]

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
                