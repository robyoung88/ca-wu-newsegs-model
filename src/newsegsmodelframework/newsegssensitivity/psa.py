"""
Functions and classes for performing probabilistic sensitivity analysis
"""
from dataclasses import field
from typing import Any, Callable, Literal, NamedTuple, Sequence, override
from typing import get_args
import warnings

import numpy as np
import pandas as pd

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegssensitivity.common import COST_FRAME_STATISTICS, total_of_cost_frame
from newsegsmodelframework.newsegsvariable import variable

PSA_FLOAT_STATISTIC = Literal[
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
"""The statistics of a run of the NewSEGS Energy Model and finance model that a PSA can calculate."""

PSA_PLOT_TYPES = [
    'Scatter plot',
    'Cumulative probability',
    'Convergence'
]
"""The types of plot of the results of a PSA."""

PSA_STATISTIC_LABELS = {
    'total_present_costs_undiscounted': 'Total cost (undisc.)',
    'total_present_costs_discounted': 'Total cost (disc.)',
    'total_present_benefits_undiscounted': 'Total benefits (undisc.)',
    'total_present_benefits_discounted': 'Total benefits (disc.)',
    'net_present_value_undiscounted': 'NPV (undisc.)',
    'net_present_value_discounted': 'NPV (disc.)',
    'all_capex_costs_undiscounted': 'Total capex (undisc.)',
    'all_capex_costs_discounted': 'Total capex (disc.)',
    'all_recurrent_costs_undiscounted': 'Total opex (undisc.)',
    'all_recurrent_costs_discounted': 'Total opex (disc.)',
}
"""Short labels of the statistics of a PSA, for plots."""

_CONVERGENCE_STATISTICS = Literal[
    'Mean',
    'Variance',
    'Median',
    'First Decile',
    'First Quartile',
    'Third Quartile',
    'Ninth Decile'
]

CONVERGENCE_STATISTICS = get_args(_CONVERGENCE_STATISTICS)
"""The statistics whose convergence, over the draws of a PSA, can be plotted."""

def quantile_stderr_cum(
    x,
    p: float = 0.5,
    bw: float | None = None
):
    """Standard error of the quantile of the first n values, for each n.

    The standard error of a sample quantile is `sqrt(p (1 - p) / n) / f`, where `f` is the density at the quantile,
    estimated by a Gaussian kernel density estimate. See
    [quantileSE](https://github.com/kbroman/broman/blob/main/R/quantileSE.R).

    Args:
        x: The sample, in order of draw.
        p: The probability of the quantile; 0.5 is the median.
        bw: Bandwidth of the kernel density estimate; by default chosen by scipy.

    Returns:
        Array of the standard error after each draw; NaN throughout if the density cannot be estimated, as when there
        are fewer than two values or they are all equal (such as the placeholder data of an empty plot).
    """
    # https://github.com/kbroman/broman/blob/main/R/quantileSE.R
    from scipy.stats import gaussian_kde
    values = np.asarray(x, dtype = float)
    finite = values[np.isfinite(values)]
    if len(finite) < 2 or np.ptp(finite) == 0.:
        return np.full(len(values), np.nan)
    quant = np.quantile(x, p)
    R = np.sqrt(p * (1. - p) / (np.arange(len(x))+1))
    if bw is None:
        pdf_ = gaussian_kde(x)
        f = pdf_.pdf(quant)
    else:
        pdf_ = gaussian_kde(x, bw_method = bw)
        f = pdf_.pdf(quant)
    return R / f

def _psa_float_statistic_mapper(
    stat: PSA_FLOAT_STATISTIC,
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
    
    raise ValueError(f'stat {stat} is not known as a PSA statistic')

def make_psa_result(
    mm: NewsegsMetaModel,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    statistics: Sequence[PSA_FLOAT_STATISTIC],
    return_draws: bool = False,
):
    """One row of the results of a PSA: a run of the NewSEGS Energy Model and finance model.

    Args:
        mm: The metamodel.
        mdl: The NewSEGS Energy Model, after the run.
        fnc: The finance model, after the run.
        statistics: The statistics to take from the models.
        return_draws: Whether to include the values drawn for each variable selected for PSA.

    Returns:
        Dictionary of the statistics and, if requested, the values of the variables (a vector variable gives one entry for each value).

    Raises:
        TypeError: if a variable selected for PSA is neither a scalar nor a vector variable.
    """
    res: dict[str, Any] = {}
    if return_draws:
        for var in mm.variables.values():
            if var.psa_selected:
                if isinstance(var, variable.ScalarVariable):
                    res[var.name] = var.get_psa_value()
                elif isinstance(var, variable.VectorVariable):
                    nms = [var.name + '_' + str(x) for x in var.value_name]
                    vals = var.get_psa_value()
                    for nm, v in zip(nms, vals):
                        res[nm] = v
                else:
                    raise TypeError(f'var is not a supported variable type - is {type(var)}')
    for stat in statistics:
        res[stat] = _psa_float_statistic_mapper(stat, mdl, fnc)
    return res

def run_psa(
    mm: NewsegsMetaModel,
    statistics: Sequence[PSA_FLOAT_STATISTIC] = get_args(PSA_FLOAT_STATISTIC),
    samples: int = 100,
    seed: int | None = None,
    rng: np.random.Generator | None = None,
    return_draws: bool = False,
    progress: Callable[[int, int], None] | None = None,
    cancel_status: Callable[[], bool] | None = None,
    include_deterministic: bool = True,
    precomputed_deterministic: bool = False,
) -> pd.DataFrame:
    """Run a probabilistic sensitivity analysis of a metamodel.

    Each sample draws a value for every variable that is selected for PSA from its distribution, then runs the NewSEGS Energy Model
    and finance model. Optionally the deterministic run is included first. Afterwards the variables are returned to their deterministic values.

    Args:
        mm: The metamodel.
        statistics: The statistics to calculate for each run.
        samples: The number of samples to draw.
        seed: Seed of the random number generator, if none is provided.
        rng: Random number generator; used in preference to the seed.
        return_draws: Whether to return the values drawn for each variable.
        progress: Function reporting progress, called with the number of runs completed and the total.
        cancel_status: Function returning whether cancellation has been requested; checked before each sample.
        include_deterministic: Whether to include the deterministic run (marked `deterministic`).
        precomputed_deterministic: Whether the metamodel already holds valid results of the deterministic run, so that
            it need not be repeated.

    Returns:
        Dataframe with a row for each run, and columns of the statistics, `deterministic` and `draw` (0 for the deterministic run).

    Raises:
        InterruptedError: if cancellation is requested.
    """
    variables = mm.variables.values()
    mdl = mm.model
    fnc = mm.finance

    results = []
    n_calcs = samples if not include_deterministic else samples + 1
    prog_i = 0
    if progress is not None:
        progress(prog_i, n_calcs)

    if cancel_status is None:
        cancel_status = lambda: False

    if cancel_status():
        raise InterruptedError('PSA job cancelled')
    
    if include_deterministic:
        if not precomputed_deterministic:
            for v in variables:
                v.psa_active = False
                v.update_model(mdl)
                v.update_model(fnc)
            mdl.run()
            fnc.run()

        res = make_psa_result(mm, mdl, fnc, statistics, return_draws)
        res['deterministic'] = True
        res['draw'] = 0
        results.append(res)
        if progress is not None:
            prog_i += 1
            progress(prog_i, n_calcs)
    
    if samples <= 0:
        return pd.DataFrame(results)
    
    if rng is None:
        rng = np.random.default_rng(seed)
    elif seed is not None:
        warnings.warn('Both a seed and a random generator are provided - existing generator will be used without reseeding')

    variables = [v for v in variables if v.psa_selected]
    
    for v in variables:
        v.psa_active = True
    
    try:
        for i in range(samples):
            if cancel_status():
                raise InterruptedError('PSA job cancelled')
            
            for v in variables:
                v.draw_psa(rng)
                v.update_model_psa(mdl)
                v.update_model_psa(fnc)
            
            mdl.run()
            fnc.run()

            res = make_psa_result(mm, mdl, fnc, statistics, return_draws)
            res['deterministic'] = False
            res['draw'] = i+1
            results.append(res)
            if progress is not None:
                prog_i += 1
                progress(prog_i, n_calcs)
    finally:
        for v in variables:
            v.psa_active = False
            v.update_model(mdl)
            v.update_model(fnc)
            mdl.run()
            fnc.run()
    
    results = pd.DataFrame(results)
    return results


@revision_dataclass
class PSAConfig(DataWithRevision):
    """Configuration of a probabilistic sensitivity analysis.

    Attributes:
        samples: Number of samples to draw.
        seed: Seed of the random number generator; random if None.
        return_draws: Whether to return the values drawn.
        include_deterministic: Whether to include the deterministic run.
        statistics: The statistics calculated from the samples.
    """
    samples: int = 1000
    seed: int | None = None
    return_draws: bool = False
    include_deterministic: bool = False
    statistics: list[PSA_FLOAT_STATISTIC] = field(default_factory = lambda: get_args(PSA_FLOAT_STATISTIC))


class PSAComponent(NewsegsComponent):
    """A container for PSA settings"""

    component_type = 'psa'

    @override
    def _generate_config(self, *args, **kwargs) -> PSAConfig:
        return PSAConfig(*args, **kwargs)
    _config: PSAConfig
    
    def __init__(
        self,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)            

def basic_psa_stats(
    psa_results: pd.DataFrame,
    statistics: Sequence[PSA_FLOAT_STATISTIC] = get_args(PSA_FLOAT_STATISTIC),
    quantiles: Sequence[float] = [0.025, 0.975],
    npv_statistics = [
        'net_present_value_undiscounted',
        'net_present_value_discounted'
    ]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarise the results of a PSA.

    Args:
        psa_results: The results of the PSA, from `run_psa`.
        statistics: The statistics to summarise.
        quantiles: Quantiles to report.
        npv_statistics: The net present value statistics for which to find the probability of being positive.

    Returns:
        A dataframe with a row for each statistic and columns of the deterministic value, the count, mean, median and standard deviation
        of the samples, and the quantiles; and a dataframe of the probability that each net present value is positive.
        Statistics missing from the results (e.g. results from before the statistic was added) are left out.
    """
    statistics = [s for s in statistics if s in psa_results.columns]
    res_det = (
        psa_results
        .query('deterministic == True')
        .loc[:, statistics]
        .sum()
        .to_frame()
        .rename(columns={0:'Deterministic'})
        )
    
    res_psa_raw = (
        psa_results
        .query('deterministic == False')
        .loc[:, statistics]
    )
    res_psa = (
        res_psa_raw
        .agg(
            ['count', 'mean', 'median', 'std']
        )
        .transpose()
        .rename(columns=lambda x: x.title())
    )
    res_psa_quants = (
        res_psa_raw
        .quantile(quantiles)
        .transpose()
        .rename(columns = lambda x: f'{100.*float(x):.1f} pctile'.replace('.','_'))
    )

    all_res = (
        res_det
        .join(res_psa)
        .join(res_psa_quants)
    )
    
    prob_positive_npv = (
        res_psa_raw
        .loc[:, npv_statistics]
        .gt(0)
        .mean(axis=0)
        .to_frame() # pyright: ignore[reportAttributeAccessIssue]
        .rename(columns={0:'prob_pos_npv'})
    )

    return all_res, prob_positive_npv

##### Whole-project PSA #####

PSA_PAIRWISE_STATISTIC = Literal[
    'incremental_net_monetary_value_discounted',
    'incremental_net_monetary_value_undiscounted',
    'incremental_total_costs_discounted',
    'incremental_total_costs_undiscounted',
    'incremental_total_benefits_discounted',
    'incremental_total_benefits_undiscounted',
    'incremental_all_capex_costs_discounted',
    'incremental_all_capex_costs_undiscounted',
    'incremental_all_recurrent_costs_discounted',
    'incremental_all_recurrent_costs_undiscounted',
]
"""Statistics comparing two metamodels (a comparator against a reference), draw by draw, in a whole-project PSA."""

PSA_MULTIPLE_INDEX_COLUMNS = ['metamodel', 'draw', 'deterministic']
"""The columns of the results of `run_psa_multiple` which precede the statistics."""

_NON_VARIABLE_COLUMNS = set(PSA_MULTIPLE_INDEX_COLUMNS) | set(get_args(PSA_FLOAT_STATISTIC)) | set(get_args(PSA_PAIRWISE_STATISTIC))

def psa_variable_columns(results: pd.DataFrame) -> list[str]:
    """The columns of PSA results which hold the values drawn for the variables (labelled by variable).

    Args:
        results: Results of `run_psa`, `run_psa_multiple`, `psa_multiple_for_metamodel` or `psa_pairwise`.

    Returns:
        The columns, in order.
    """
    return [x for x in results.columns if x not in _NON_VARIABLE_COLUMNS]

def _psa_variable_is_candidate(var) -> bool:
    return bool(var.psa_possible and var.psa_selectable)

def _psa_variable_is_varied(var) -> bool:
    return _psa_variable_is_candidate(var) and bool(var.psa_selected)

def synchronise_psa_selection(metamodels: Sequence[NewsegsMetaModel]) -> list[str]:
    """Make the PSA selection of variables common to several metamodels consistent.

    A variable (identified by its varid) which is selected for PSA in any of the metamodels is selected in all of
    the metamodels that have it; otherwise it is deselected in all. Only variables which are PSA-possible and
    selectable are changed. Independent instances with the same varid keep their own distributions.

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
            if _psa_variable_is_varied(var):
                selected.add(varid)

    for mm in metamodels:
        for varid, var in mm.variables.items():
            if not _psa_variable_is_candidate(var):
                continue
            is_selected = varid in selected
            if var.psa_selected != is_selected:
                var.psa_selected = is_selected

    return [x for x in order if x in selected]

def run_psa_multiple(
    metamodels: Sequence[NewsegsMetaModel],
    statistics: Sequence[PSA_FLOAT_STATISTIC] = get_args(PSA_FLOAT_STATISTIC),
    samples: int = 100,
    seed: int | None = None,
    rng: np.random.Generator | None = None,
    progress: Callable[[int, int], None] | None = None,
    cancel_status: Callable[[], bool] | None = None,
    include_deterministic: bool = True,
    precomputed_deterministic: bool = False,
    synchronise: bool = True,
) -> pd.DataFrame:
    """Run a probabilistic sensitivity analysis across several metamodels (a whole-project PSA).

    In each sample every metamodel is run with the same draw of each variable, so that the metamodels can be
    compared draw by draw. A variable shared by metamodels is a single instance, drawn once. Independent instances
    with the same varid are drawn with common random numbers - each from a generator seeded identically for the
    varid and draw - so that instances with the same distribution take the same value, and instances whose
    distributions differ only in their parameters take correspondingly correlated values. Different variables are
    drawn independently.

    A metamodel which does not have a variable, or for which it cannot be varied, keeps the variable at its
    deterministic value.

    Args:
        metamodels: The metamodels.
        statistics: The statistics to calculate for each run.
        samples: The number of samples to draw.
        seed: Seed of the random number generator, if none is provided.
        rng: Random number generator; used in preference to the seed.
        progress: Function reporting progress, called with the number of runs completed and the total.
        cancel_status: Function returning whether cancellation has been requested; checked before each sample.
        include_deterministic: Whether to include the deterministic run of each metamodel (draw 0).
        precomputed_deterministic: Whether the metamodels already hold valid results of their deterministic runs,
            so that they need not be repeated.
        synchronise: Whether to make the PSA selection of common variables consistent first (see
            `synchronise_psa_selection`).

    Returns:
        Dataframe with a row for each metamodel for each run, and columns `metamodel` (id), `draw` (0 for the
        deterministic run), `deterministic`, the statistics, and the value of each variable selected for PSA
        (labelled by the variable; empty for a metamodel which does not vary it).

    Raises:
        InterruptedError: if cancellation is requested.
    """
    metamodels = list(metamodels)
    if cancel_status is None:
        cancel_status = lambda: False

    if synchronise:
        varids = synchronise_psa_selection(metamodels)
    else:
        order: dict[str, None] = {}
        for mm in metamodels:
            for varid, var in mm.variables.items():
                if _psa_variable_is_varied(var):
                    order.setdefault(varid, None)
        varids = list(order)

    n_calcs = len(metamodels) * (samples + (1 if include_deterministic else 0))
    prog_i = 0
    def _report():
        if progress is not None:
            progress(prog_i, n_calcs)
    _report()

    if cancel_status():
        raise InterruptedError('PSA job cancelled')

    def _result(mm, draw: int, deterministic: bool) -> dict[str, Any]:
        res = make_psa_result(mm, mm.model, mm.finance, statistics, return_draws = True)
        return {'metamodel': mm.id, 'draw': draw, 'deterministic': deterministic, **res}

    results = []
    # Shared variables are a single instance; flag each instance once
    all_variables = list({id(v): v for mm in metamodels for v in mm.variables.values()}.values())

    if include_deterministic:
        for mm in metamodels:
            if not precomputed_deterministic:
                for v in mm.variables.values():
                    v.psa_active = False
                    v.update_model(mm.model)
                    v.update_model(mm.finance)
                mm.model.run()
                mm.finance.run()
            results.append(_result(mm, 0, True))
            prog_i += 1
            _report()

    if samples > 0:
        if rng is None:
            rng = np.random.default_rng(seed)
        elif seed is not None:
            warnings.warn('Both a seed and a random generator are provided - existing generator will be used without reseeding')

        varied_variables = [v for v in all_variables if _psa_variable_is_varied(v)]
        for v in varied_variables:
            v.psa_active = True

        try:
            for i in range(samples):
                if cancel_status():
                    raise InterruptedError('PSA job cancelled')

                draw_seed = int(rng.integers(0, 2**63 - 1))
                for k, varid in enumerate(varids):
                    drawn: set[int] = set()
                    for mm in metamodels:
                        var = mm.variables.get(varid)
                        if var is None or id(var) in drawn or not _psa_variable_is_varied(var):
                            continue
                        # Common random numbers: the same stream for every instance of the varid in this draw
                        var.draw_psa(np.random.default_rng([draw_seed, k]))
                        drawn.add(id(var))

                for mm in metamodels:
                    for v in mm.variables.values():
                        if _psa_variable_is_varied(v):
                            v.update_model_psa(mm.model)
                            v.update_model_psa(mm.finance)
                    mm.model.run()
                    mm.finance.run()
                    results.append(_result(mm, i + 1, False))
                    prog_i += 1
                    _report()
        finally:
            for v in varied_variables:
                v.psa_active = False
            for mm in metamodels:
                for v in mm.variables.values():
                    v.update_model(mm.model)
                    v.update_model(mm.finance)
                mm.model.run()
                mm.finance.run()

    odf = pd.DataFrame(results)
    statistic_columns = [x for x in statistics if x in odf.columns]
    leading = PSA_MULTIPLE_INDEX_COLUMNS + statistic_columns
    return odf.loc[:, leading + [x for x in odf.columns if x not in leading]]

def psa_multiple_for_metamodel(
    results: pd.DataFrame,
    metamodel_id: str,
) -> pd.DataFrame:
    """The results of one metamodel from a whole-project PSA, in the form of the results of `run_psa`.

    Args:
        results: The results of `run_psa_multiple`.
        metamodel_id: Id of the metamodel.

    Returns:
        Dataframe with columns of the statistics, the values of the variables that the metamodel varied,
        `deterministic` and `draw`.

    Raises:
        KeyError: if the metamodel is not in the results.
    """
    mm_results = results.loc[results['metamodel'] == metamodel_id, :]
    if len(mm_results) == 0:
        raise KeyError(f'Metamodel {metamodel_id} not found in PSA results')
    variable_columns = [x for x in psa_variable_columns(mm_results) if mm_results[x].notna().any()]
    statistic_columns = [x for x in mm_results.columns if x in get_args(PSA_FLOAT_STATISTIC)]
    return (
        mm_results
        .loc[:, variable_columns + statistic_columns + ['deterministic', 'draw']]
        .reset_index(drop = True)
    )

def psa_pairwise(
    results: pd.DataFrame,
    comparator_id: str,
    reference_id: str,
) -> pd.DataFrame:
    """Compare two metamodels of a whole-project PSA: the comparator against the reference, draw by draw.

    For each draw (including the deterministic run, draw 0, if present) the statistics of the reference are
    subtracted from those of the comparator:

    - incremental total costs and benefits: the change in total present costs and in total present benefits;
    - incremental net monetary value: incremental benefits less incremental costs (the change in net present value);
    - incremental capex and opex: the change in total capital expenditure and in total recurrent costs. These are
      NaN if the results do not include the capex and opex statistics.

    each discounted and undiscounted. The values drawn for the variables are kept (those of the comparator, or of
    the reference for a variable that only the reference varies), so that increments can be related to the draws.

    Args:
        results: The results of `run_psa_multiple`, which must include the total present costs and benefits,
            discounted and undiscounted.
        comparator_id: Id of the comparator metamodel.
        reference_id: Id of the reference metamodel.

    Returns:
        Dataframe with columns `draw`, `deterministic`, the pairwise statistics and the values of the variables.

    Raises:
        KeyError: if a metamodel, or a required statistic, is not in the results.
    """
    required = [
        f'total_present_{x}_{y}' for x in ('costs', 'benefits') for y in ('discounted', 'undiscounted')
    ]
    missing = [x for x in required if x not in results.columns]
    if missing:
        raise KeyError(f'PSA results do not include the statistics required for pairwise comparison: {missing}')

    def _frame(mm_id):
        df = results.loc[results['metamodel'] == mm_id, :]
        if len(df) == 0:
            raise KeyError(f'Metamodel {mm_id} not found in PSA results')
        return df.set_index('draw')

    comp = _frame(comparator_id)
    ref = _frame(reference_id).reindex(comp.index)

    odf = pd.DataFrame({'deterministic': comp['deterministic']}, index = comp.index)
    for disc in ('discounted', 'undiscounted'):
        d_costs = comp[f'total_present_costs_{disc}'] - ref[f'total_present_costs_{disc}']
        d_benefits = comp[f'total_present_benefits_{disc}'] - ref[f'total_present_benefits_{disc}']
        odf[f'incremental_net_monetary_value_{disc}'] = d_benefits - d_costs
        odf[f'incremental_total_costs_{disc}'] = d_costs
        odf[f'incremental_total_benefits_{disc}'] = d_benefits
        for cost in ('all_capex_costs', 'all_recurrent_costs'):
            stat = f'{cost}_{disc}'
            odf[f'incremental_{stat}'] = comp[stat] - ref[stat] if stat in results.columns else np.nan

    variable_columns = psa_variable_columns(results)
    draws = comp.loc[:, variable_columns].combine_first(ref.loc[:, variable_columns])
    draws = draws.loc[:, [x for x in variable_columns if draws[x].notna().any()]]

    odf = odf.join(draws).reset_index()
    return odf.loc[:, ['draw', 'deterministic'] + list(get_args(PSA_PAIRWISE_STATISTIC)) + list(draws.columns)]

def psa_net_benefit(
    results: pd.DataFrame,
    metamodel_ids: Sequence[str],
    benefit_value: float = 1.,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted',
) -> pd.DataFrame:
    """The net benefit of each metamodel in each draw of a whole-project PSA, valuing benefits by a multiplier.

    The net benefit is `benefit_value * benefits - costs`; with a multiplier of 1 it is the net present value.

    Args:
        results: The results of `run_psa_multiple`.
        metamodel_ids: Ids of the metamodels.
        benefit_value: The value of one pound of benefit.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.

    Returns:
        Dataframe indexed by draw (sampled draws only), with a column for each metamodel.

    Raises:
        KeyError: if a metamodel is not in the results.
    """
    sampled = results.loc[~results['deterministic'].astype(bool), :]
    frames = {}
    for mm_id in metamodel_ids:
        df = sampled.loc[sampled['metamodel'] == mm_id, :]
        if len(df) == 0:
            raise KeyError(f'Metamodel {mm_id} not found in PSA results')
        df = df.set_index('draw')
        frames[mm_id] = benefit_value * df[benefit_statistic] - df[cost_statistic]
    return pd.DataFrame(frames).dropna()

def psa_ceac(
    results: pd.DataFrame,
    metamodel_ids: Sequence[str],
    benefit_values: Sequence[float],
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted',
) -> pd.DataFrame:
    """Cost-effectiveness acceptability curves and frontier of the metamodels of a whole-project PSA.

    For each value of benefits (see `psa_net_benefit`), the probability that each metamodel is cost-effective -
    has the greatest net benefit of the metamodels in a draw - and the frontier: the metamodel with the greatest
    expected (mean) net benefit, which is the one to choose at that value, with its probability of being cost-effective.

    Args:
        results: The results of `run_psa_multiple`.
        metamodel_ids: Ids of the metamodels compared.
        benefit_values: The values of one pound of benefit at which to evaluate the curves.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.

    Returns:
        Dataframe indexed by `benefit_value`, with a column of the probability for each metamodel, `frontier`
        (the id of the metamodel on the frontier) and `frontier_probability`.

    Raises:
        KeyError: if a metamodel is not in the results.
        ValueError: if no metamodels are given.
    """
    metamodel_ids = list(metamodel_ids)
    if not metamodel_ids:
        raise ValueError('No metamodels to compare')
    rows = []
    for benefit_value in benefit_values:
        nb = psa_net_benefit(results, metamodel_ids, benefit_value, cost_statistic, benefit_statistic)
        values = nb.to_numpy(dtype = np.float64)
        best = np.argmax(values, axis = 1)
        probabilities = np.bincount(best, minlength = len(metamodel_ids)) / max(1, len(best))
        frontier = int(np.argmax(values.mean(axis = 0))) if len(values) else 0
        row: dict[str, Any] = {'benefit_value': float(benefit_value)}
        row.update({mm_id: p for mm_id, p in zip(metamodel_ids, probabilities)})
        row['frontier'] = metamodel_ids[frontier]
        row['frontier_probability'] = probabilities[frontier]
        rows.append(row)
    return pd.DataFrame(rows).set_index('benefit_value')

class PSAMarginalData(NamedTuple):
    """Data for a marginal (univariate) sensitivity plot of a statistic of a PSA against the draws of a variable.

    Attributes:
        points: The sampled draws: columns `x` (the variable) and `y` (the statistic).
        binned: The draws grouped by quantile of the variable: columns `x` and `y` (the means of each group),
            `y_lower` and `y_upper` (the 5th and 95th percentiles of the statistic in each group) and `count`.
        spearman: Spearman rank correlation of the statistic with the variable.
        pearson: Pearson correlation of the statistic with the variable.
        slope: Slope of the least-squares line of the statistic on the variable (change of statistic per unit).
        intercept: Intercept of the least-squares line.
        r_squared: Proportion of the variance of the statistic explained by the line.
    """
    points: pd.DataFrame
    binned: pd.DataFrame
    spearman: float
    pearson: float
    slope: float
    intercept: float
    r_squared: float

def psa_marginal(
    results: pd.DataFrame,
    variable_column: str,
    statistic: str,
    bins: int = 10,
) -> PSAMarginalData:
    """Marginal (univariate) sensitivity of a statistic of a PSA to the draws of one variable.

    The other variables vary too, so the relation is that of the statistic to the variable averaged over the
    other variables. Works on the results of one metamodel or on pairwise (incremental) results.

    Args:
        results: The results: those of `run_psa`, `psa_multiple_for_metamodel` or `psa_pairwise`.
        variable_column: The column of the variable.
        statistic: The column of the statistic.
        bins: The number of quantile groups of the variable.

    Returns:
        The points, the binned means and the summary statistics. The statistics are NaN where they cannot be
        found (fewer than three draws, or a variable or statistic which does not vary).

    Raises:
        KeyError: if the variable or the statistic is not in the results.
    """
    if variable_column not in results.columns:
        raise KeyError(f'Variable {variable_column} not found in PSA results')
    if statistic not in results.columns:
        raise KeyError(f'Statistic {statistic} not found in PSA results')
    sampled = results
    if 'deterministic' in results.columns:
        sampled = results.loc[~results['deterministic'].astype(bool), :]
    points = (
        pd.DataFrame({
            'x': pd.to_numeric(sampled[variable_column], errors = 'coerce'),
            'y': pd.to_numeric(sampled[statistic], errors = 'coerce'),
        })
        .dropna()
        .reset_index(drop = True)
    )

    nan = float('nan')
    spearman = pearson = slope = intercept = r_squared = nan
    x = points['x'].to_numpy(dtype = np.float64)
    y = points['y'].to_numpy(dtype = np.float64)
    if len(points) >= 3 and np.ptp(x) > 0:
        slope, intercept = (float(v) for v in np.polyfit(x, y, 1))
        if np.ptp(y) > 0:
            pearson = float(np.corrcoef(x, y)[0, 1])
            spearman = float(points['x'].rank().corr(points['y'].rank()))
            r_squared = pearson**2
        else:
            r_squared = 0.

    if len(points):
        if np.ptp(x) > 0:
            groups = pd.qcut(points['x'], q = min(bins, len(points)), duplicates = 'drop')
        else:
            # A variable that does not vary is a single group
            groups = pd.Series(0, index = points.index)
        binned = (
            points
            .groupby(groups, observed = True)
            .agg(
                x = ('x', 'mean'),
                y = ('y', 'mean'),
                y_lower = ('y', lambda s: s.quantile(0.05)),
                y_upper = ('y', lambda s: s.quantile(0.95)),
                count = ('y', 'count'),
            )
            .reset_index(drop = True)
        )
    else:
        binned = pd.DataFrame(columns = ['x', 'y', 'y_lower', 'y_upper', 'count'])

    return PSAMarginalData(points, binned, spearman, pearson, slope, intercept, r_squared)

##### Generic Graph functions #####

def get_null_psa_data(statistics: Sequence[str]) -> pd.DataFrame:
    """Placeholder PSA results, to draw plots before there are results.

    Args:
        statistics: The statistics for which to make data.

    Returns:
        A dataframe of two rows - one deterministic and one not (draws 0 and 1) - with every statistic equal to 1.
    """
    stat_dict = {
        x: [1, 1] for x in statistics
    }
    stat_dict['deterministic'] = [True, False]
    stat_dict['draw'] = [0, 1]
    return pd.DataFrame.from_dict(
            stat_dict
        )

##### Scatter ######

class PSAScatterData(NamedTuple):
    """NamedTuple of data for a PSA scatter plot
    """
    scatter_data: pd.DataFrame
    det_point: pd.Series
    ce_proportion: float


def psa_scatter_data(
    psa_data: pd.DataFrame,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted'
) -> PSAScatterData:
    """Data for the scatter plot of the costs and benefits of the samples of a PSA.

    Each sample is categorised as cost effective (`CE`) if its benefits exceed its costs.

    Args:
        psa_data: The results of the PSA.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.

    Returns:
        The samples with their category, the deterministic point and the proportion of samples that are cost effective.
    """
    scatter_data = (
        psa_data
        .query('deterministic == False')
        .loc[:, [cost_statistic, benefit_statistic]]
        .assign(
            cost_effective = lambda df: (df[benefit_statistic] > df[cost_statistic]).map({True: 'CE', False: 'Not CE'})
        )
        .assign(
            cost_effective = lambda df: pd.Categorical(df['cost_effective'], categories=['CE', 'Not CE'], ordered = True)
        )
    )

    det_point = (
        psa_data
        .query('deterministic == True')
        .loc[:, [cost_statistic, benefit_statistic]]
        .iloc[0]
    )

    ce_proportion = scatter_data['cost_effective'].eq('CE').mean()

    return PSAScatterData(scatter_data, det_point, ce_proportion)

###### CDF #####

class PSACDFData(NamedTuple):
    """Data for the cumulative distribution plot of a statistic of a PSA.

    Attributes:
        cdf_data: The samples in ascending order, with their cumulative probability.
        det_value: The value of the statistic of the deterministic run.
        min: Lowest sample.
        max: Highest sample.
    """
    cdf_data: pd.DataFrame
    det_value: float
    min: float
    max: float


def psa_cdf_data(
    psa_data: pd.DataFrame,
    statistic: str
) -> PSACDFData:
    """Data for the cumulative distribution plot of a statistic of a PSA.

    Args:
        psa_data: The results of the PSA.
        statistic: The statistic.

    Returns:
        The samples, the deterministic value and the range.
    """
    cdf_data = (
        psa_data
        .query('deterministic == False')
        .loc[:, [statistic,]]
        .sort_values(statistic)
        .reset_index(drop = True)
        .assign(
            cdf = lambda df: df[statistic].index / max(1, df[statistic].count())
        )
    )

    det_value = (
        psa_data
        .query('deterministic == True')
        .loc[:, statistic]
        .iloc[0]
    )

    return PSACDFData(
        cdf_data,
        det_value,
        cdf_data[statistic].iloc[0],
        cdf_data[statistic].iloc[-1]
    )

##### Convergence #####

class PSAConvergenceData(NamedTuple):
    """NamedTuple of data for PSA convergence summaries
    """
    stat_data: pd.DataFrame
    final_stat: float

def psa_convergence_data(
    psa_data: pd.DataFrame,
    statistic: str,
    convergence_statistic: _CONVERGENCE_STATISTICS
):
    """Data for the plot of the convergence of a statistic of a PSA over its draws.

    For each draw, the value of the convergence statistic (e.g. the mean) of the samples so far, with its standard error.

    Args:
        psa_data: The results of the PSA.
        statistic: The statistic of the model whose convergence is plotted.
        convergence_statistic: The statistic of the samples: mean, variance, median or a decile or quartile.

    Returns:
        The convergence of the statistic with its standard error at each draw, and its final value.

    Raises:
        ValueError: if the convergence statistic is not recognised.
    """
    raw_frame = (
        psa_data
        .query('deterministic == False')
        .loc[:, ['draw', statistic]]
    )

    match convergence_statistic:
        case 'Mean':
            final_stat = raw_frame[statistic].mean()
            sample_std = raw_frame[statistic].std()
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().mean(),
                    stderr = lambda df: sample_std / np.sqrt(df['draw'])
                )
            )
        case 'Variance':
            final_stat = raw_frame[statistic].var()
            # Assume that we have convergence and Normally distributed so SE can
            # be estimated using s^2 as sigma^2
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().var(),
                    stderr = lambda df: np.sqrt((2. * final_stat**2) / df['draw'])
                )
            )
        case 'Median':
            final_stat = raw_frame[statistic].median()
            # https://search.r-project.org/CRAN/refmans/wrappedtools/html/se_median.html
            # https://github.com/abusjahn/wrappedtools/blob/main/R/descriptives.R
            from scipy.stats import median_abs_deviation
            mad = median_abs_deviation(raw_frame[statistic])
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().median(),
                    stderr = lambda df: mad / np.sqrt(df['draw'])
                )
            )
        case 'First Decile':
            q = 0.1
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case 'First Quartile':
            q = 0.25
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case 'Third Quartile':
            q = 0.75
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case 'Ninth Decile':
            q = 0.9
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case _:
            raise ValueError(f'convergence_statistic not recognised: {convergence_statistic}')
    
    stat_data = (
        stat_data
        .assign(
            lower_bound = lambda df: final_stat - 2.0 * df['stderr'],
            upper_bound = lambda df: final_stat + 2.0 * df['stderr']
        )
    )

    return PSAConvergenceData(
        stat_data,
        final_stat
    )
