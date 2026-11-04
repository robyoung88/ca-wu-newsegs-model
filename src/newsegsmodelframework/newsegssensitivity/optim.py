"""
Functions and classes for finding optimal system configurations
"""
import copy
from dataclasses import dataclass
from typing import Callable, Sequence

import numpy as np
import pandas as pd
import plotly.express as px
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
        cancel_status: Function returning whether cancellation has been requested; checked after each iteration.
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
        setpars(x, mm)
        mm.model.run()
        mm.finance.run()
        return _optim_float_statistic_mapper(target, mm.model, mm.finance)

    cback_count = 0
    def cback(intermediate_result: scipy_opt.OptimizeResult):
        nonlocal cback_count
        
        cback_count += 1
        progress(cback_count, cback_count + 2)
        if cancel_status():
            return True
            #raise StopIteration(f'Optimisation process has been cancelled.')
    
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
    resolution: int    
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
    
    def statfunc(x) -> float:
        if len(par0) == 1:
            mm.variables[varid].set_parameters(x)
        else:
            par0[0] = x
            mm.variables[varid].set_parameters(*par0)
        mm.update_model_from_variable_deterministic(varid)
        mm.model.run()
        mm.finance.run()
        return _optim_float_statistic_mapper(stat, mm.model, mm.finance, False) # pyright: ignore[reportArgumentType]
    
    oarray = np.asarray(map(statfunc, param_range))
    #oarray = np.apply_along_axis(statfunc, 0, param_range)
    
    # Caution! map appears to be lazy, and if we don't use oarray until after we reset
    # the metamodel variables, it will run the map THEN and leave the metamodel
    # with the end of the range set.
    odf = pd.DataFrame({
        varid: param_range,
        stat: oarray,
    })

    mm.variables[varid] = var_hold
    mm.update_model_from_variable_deterministic(varid)
    mm.model.run()
    mm.finance.run()

    return odf

def statistic_across_margin_plot(
    plot_data,
    mm: NewsegsMetaModel
):
    """Plot a statistic across a range of values of a variable.

    Args:
        plot_data: The result of `evaluate_statistic_across_margin`: the values of the variable and the statistic.
        mm: The metamodel, used to label the axes.

    Returns:
        The line plot (a plotly figure).
    """
    fig = px.line(
        plot_data,
        x = plot_data.columns[0],
        y = plot_data.columns[1]
    )

    fig.update_xaxes(
        title = mm.variables[plot_data.columns[0]].name
    )
    fig.update_yaxes(
        title = OPTIM_TARGET_STATISTIC_LABELS[plot_data.columns[1]]
    )

    return fig
    