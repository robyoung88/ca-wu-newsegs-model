"""
Functions and classes for finding optimal system configurations
"""
import copy
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import pandas as pd
from scipy import optimize as scipy_opt

from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.optim_component import ( # noqa: F401 - re-exported for the pages
    OPTIM_TARGET_STATISTIC as _OPTIM_TARGET_STATISTIC,
    OPTIM_TARGET_STATISTICS,
    OPTIM_TARGET_STATISTIC_LABELS,
    OPTIMISATION_METHODS,
)
from newsegsmodelframework.newsegsmodel.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsvariable.variable import Variable

_MAXIMISE_OPTIM_TARGET_STATISTICS = [
    'net_present_value_discounted',
    'net_present_value_undiscounted',
]
"""
Statistics in this list will be inverted for minimization
"""

def _optim_float_statistic_mapper(
    stat: _OPTIM_TARGET_STATISTIC,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    do_optim: bool = True
) -> float:
    if do_optim:
        fac = 1.0 if stat not in _MAXIMISE_OPTIM_TARGET_STATISTICS else -1.0
    else:
        fac = 1.0
    fnc_attrname = 'get_' + stat
    if hasattr(fnc, fnc_attrname):
        return fac * getattr(fnc, fnc_attrname)()
    #elif hasattr(type(fnc), fnc_attrname):
    #    return getattr(type(fnc), fnc_attrname)(fnc)
    
    # Nothing to look for here yet, but included for future expansion
    if hasattr(mdl, fnc_attrname):
        return fac * getattr(mdl, fnc_attrname)()
    
    raise ValueError(f'stat {stat} is not known as an optimisation statistic')

def evaluate_statistic(mm: NewsegsMetaModel, stat: _OPTIM_TARGET_STATISTIC) -> float:
    """The value of an optimisation statistic of a metamodel at its current parameters.

    Runs the NewSEGS Energy Model and the finance model, after bringing the models up to date with
    the variables.

    Args:
        mm: The metamodel.
        stat: The statistic.

    Returns:
        The value of the statistic, e.g. the NPV (£).
    """
    mm.sync_model_with_changed_variables_deterministic()
    mm.model.run()
    mm.finance.run()
    return _optim_float_statistic_mapper(stat, mm.model, mm.finance, do_optim = False)

def statistic_from_objective(stat: _OPTIM_TARGET_STATISTIC, objective: float) -> float:
    """The value of an optimisation statistic from the value of the objective minimised for it.

    Statistics which are maximised, such as the NPV, are minimised as their negative.

    Args:
        stat: The statistic.
        objective: The value of the objective, such as `fun` of the result of `run_optimisation`.

    Returns:
        The value of the statistic.
    """
    return -objective if stat in _MAXIMISE_OPTIM_TARGET_STATISTICS else objective

def statistic_is_maximised(stat: _OPTIM_TARGET_STATISTIC) -> bool:
    """Whether an optimisation statistic is maximised, rather than minimised."""
    return stat in _MAXIMISE_OPTIM_TARGET_STATISTICS

@dataclass
class OptimVariable:
    """Specification of a variable to vary in an optimisation.

    Attributes:
        varid: The varid of the variable.
        positive: Whether the variable must remain positive. Where no variable is bounded, a positive variable is searched on the log scale.
        bounded: Whether the variable is limited to `lower` and `upper`.
        lower: Lower limit of the variable.
        upper: Upper limit of the variable.
        param_index: Which parameter of the variable is varied; the first by default.
    """
    varid: str
    positive: bool = False
    bounded: bool = True
    lower: float = -np.inf
    upper: float = np.inf
    param_index: int = 0

class InvalidOptimBoundsError(ValueError):
    """Raised when variables to be optimised have bounds that cannot be used.

    The message is intended for the user, and names the variables and their problems.
    """
    retryable = False
    """Running again gives the same result until the bounds are changed, so the app does not retry."""

def optim_bounds_problem(var: Variable) -> str | None:
    """Why the optimisation bounds of a variable cannot be used, if they cannot.

    Args:
        var: The variable.

    Returns:
        A description of the problem, or `None` if the bounds are valid.
    """
    lower, upper = var.get_optim_bounds()
    if lower is None and upper is None:
        return 'no lower or upper bound'
    if lower is None:
        return 'no lower bound'
    if upper is None:
        return 'no upper bound'
    if not lower < upper: # pyright: ignore[reportOperatorIssue]
        return f'lower bound {lower} is not below upper bound {upper}'
    return None

def check_optim_bounds(variables: Sequence[Variable]) -> None:
    """Check that the optimisation bounds of the variables can be used.

    Args:
        variables: The variables.

    Raises:
        InvalidOptimBoundsError: Naming every variable whose bounds cannot be used.
    """
    problems = [
        f'{var.label} ({problem})' for var in variables
        if (problem := optim_bounds_problem(var)) is not None
    ]
    if problems:
        raise InvalidOptimBoundsError('Invalid optimisation bounds: ' + '; '.join(problems))

def run_optimisation(
    mm: NewsegsMetaModel,
    variables: Sequence[OptimVariable],
    target: _OPTIM_TARGET_STATISTIC = 'net_present_value_discounted',
    progress: Callable[[int, int], None] | None = None,
    cancel_status: Callable[[], bool] | None = None,
    method: str = 'Nelder-Mead'
):
    """Optimise the variables of a metamodel to maximise a statistic.

    The parameter of each variable is varied by a scipy optimiser, running the NewSEGS Energy Model and finance model
    for each trial. If any variable is bounded the search is on the natural scale with bounds; otherwise positive
    variables are searched on the log scale. On success the metamodel is left with the optimal values.

    Args:
        mm: The metamodel.
        variables: The variables to vary.
        target: The statistic to maximise.
        progress: Function reporting progress, called with the iteration and a count one or two larger; the total is not known in advance.
        cancel_status: Function returning whether cancellation has been requested; checked before each run of the
            models, so that the optimisation stops within one run whatever the method.
        method: The scipy optimisation method.

    Returns:
        The scipy optimisation result.

    Raises:
        InterruptedError: if cancellation is requested.
    """

    if progress is None:
        progress = lambda x, y: None
    if cancel_status is None:
        cancel_status = lambda: False

     # Ensure models are up-to-date
    mm.sync_model_with_changed_variables_deterministic()

    do_bound = False
    for var in variables:
        if var.bounded:
            do_bound = True
            break
    
    if do_bound:
        # Don't bother with log transform as we have a cliff-edge anyway
        transforms = [lambda v: v for x in variables]
        inv_transforms = [lambda v: v for x in variables]
    else:
        transforms = [np.log if x.positive else lambda v: v for x in variables]
        inv_transforms = [np.exp if x.positive else lambda v: v for x in variables]

    x0 = np.asarray(
        [
            y(mm.variables[x.varid].get_deterministic_value()) for x, y in zip(variables, transforms)
        ],
        dtype = np.float64
    )

    def setpars(x, mm):
        x_trans = [y(v) for v, y in zip(x, inv_transforms)]
        for var, val in zip(variables, x_trans):
            par0 = list(mm.variables[var.varid].parameters)
            par0[var.param_index] = val
            mm.variables[var.varid].set_parameters(*par0)
            mm.update_model_from_variable_deterministic(var.varid)

    def optfunc(x, *args) -> float:
        # Cancellation is checked here rather than in the callback: scipy ignores a callback returning True, and
        # some methods (e.g. Powell) run the models many times in each iteration. Raising from the objective stops
        # every method, and propagates out of `minimize`.
        if cancel_status():
            raise InterruptedError('Optimisation cancelled')
        setpars(x, mm)
        mm.model.run()
        mm.finance.run()
        return _optim_float_statistic_mapper(target, mm.model, mm.finance)

    cback_count = 0
    def cback(intermediate_result: scipy_opt.OptimizeResult):
        nonlocal cback_count

        cback_count += 1
        progress(cback_count, cback_count + 2)

    if do_bound:
        bounds = []
        for var, trans in zip(variables, transforms):
            if var.bounded:
                bounds.append((trans(var.lower), trans(var.upper)))
            else:
                bounds.append((None, None))
        opt = scipy_opt.minimize(optfunc, x0, method = method, bounds = bounds, callback = cback)
    else:
        opt = scipy_opt.minimize(optfunc, x0, method = method, callback = cback)

    if cancel_status():
        raise InterruptedError('Optimisation cancelled')

    if opt.success:
        setpars(opt.x, mm)
    return opt

def evaluate_statistic_across_margin(
    mm: NewsegsMetaModel,
    varid: str,
    stat: str,
    lower: float,
    upper: float,
    resolution: int,
    progress_callback: Callable[[float, float, str], None] | None = None,
) -> pd.DataFrame:
    """Evaluate a statistic across a range of values of one variable, for a marginal plot.

    The first parameter of the variable is set to `resolution + 1` evenly spaced values from `lower` to `upper`, and the
    NewSEGS Energy Model and finance model are run for each. The original variable is restored afterwards.

    Args:
        mm: The metamodel.
        varid: The varid of the variable.
        stat: The statistic to evaluate.
        lower: Lowest value of the parameter.
        upper: Highest value of the parameter.
        resolution: Number of intervals between the lowest and highest values.
        progress_callback: Function reporting progress: takes the progress, the total, and a message. Called
            before each point, e.g. 'Point 3 of 11', and before the run restoring the configuration, with the
            progress of each run within it, such as waits for environmental data.

    Returns:
        Dataframe of the values of the parameter (a column named for the varid) and of the statistic.
    """
    # Ensure models are up-to-date
    mm.sync_model_with_changed_variables_deterministic()

    var_hold = mm.variables[varid]
    var_edit = copy.deepcopy(mm.variables[varid])
    mm.variables[varid] = var_edit
    par0 = list(mm.variables[varid].parameters)

    param_range = np.linspace(lower, upper, resolution + 1, dtype = np.float64)
    # Each point, then the run restoring the configuration
    total = len(param_range) + 1

    def run(step: int, message: str):
        if progress_callback is None:
            mm.model.run()
        else:
            progress_callback(step, total, message)
            # The progress of the model run within this step, such as waits for environmental data
            def model_progress(fraction: float, model_message: str):
                progress_callback(step + fraction, total, f'{message}: {model_message}')
            mm.model.run(progress_callback = model_progress) # pyright: ignore[reportCallIssue]
        mm.finance.run()

    values = []
    for i, x in enumerate(param_range):
        if len(par0) == 1:
            mm.variables[varid].set_parameters(x)
        else:
            par0[0] = x
            mm.variables[varid].set_parameters(*par0)
        mm.update_model_from_variable_deterministic(varid)
        run(i, f'Point {i + 1} of {len(param_range)}')
        values.append(_optim_float_statistic_mapper(stat, mm.model, mm.finance, False)) # pyright: ignore[reportArgumentType]

    odf = pd.DataFrame({
        varid: param_range,
        stat: np.asarray(values, dtype = np.float64),
    })

    mm.variables[varid] = var_hold
    mm.update_model_from_variable_deterministic(varid)
    run(len(param_range), 'Restoring the configuration')

    return odf
