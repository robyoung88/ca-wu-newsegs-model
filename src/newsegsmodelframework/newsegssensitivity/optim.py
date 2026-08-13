"""
Functions and classes for finding optimal system configurations
"""
import copy
from dataclasses import dataclass
from typing import Callable, Collection, Iterable, Literal, Sequence, get_args

import numpy as np
import pandas as pd
import plotly.express as px
from scipy import optimize as scipy_opt

from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsvariable import variable

_OPTIM_TARGET_STATISTIC = Literal[
    'net_present_value_discounted',
    'net_present_value_undiscounted',
]

OPTIM_TARGET_STATISTICS = get_args(_OPTIM_TARGET_STATISTIC)

_MAXIMISE_OPTIM_TARGET_STATISTICS = [
    'net_present_value_discounted',
    'net_present_value_undiscounted',
]

OPTIM_TARGET_STATISTIC_LABELS = {
    'net_present_value_undiscounted': 'NPV (undiscounted)',
    'net_present_value_discounted': 'NPV (discounted)'
}

_OPTIMISATION_METHODS = Literal[
    'Nelder-Mead',
    'L-BFGS-B',
    'TNC',
    'SLSQP',
    'Powell'
]

OPTIMISATION_METHODS = get_args(_OPTIMISATION_METHODS)

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
    """_summary_
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
    method: str = 'Nelder-Mead'
):
    """_summary_

    Args:
        mm (NewsegsMetaModel): _description_
        variables (Sequence[OptimVariable]): _description_
        target (_OPTIM_TARGET_STATISTIC, optional): _description_. Defaults to 'net_present_value_discounted'.
        progress (Callable[[int, int], None] | None, optional): _description_. Defaults to None.
        method (str, optional): _description_. Defaults to 'Nelder-Mead'.
    """
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

    def optfunc(x, *args) -> float:
        x_trans = [y(v) for v, y in zip(x, inv_transforms)]
        for var, val in zip(variables, x_trans):
            par0 = list(mm.variables[var.varid].parameters)
            par0[var.param_index] = val
            mm.variables[var.varid].set_parameters(*par0)
            mm.update_model_from_variable_deterministic(var.varid)
        mm.model.run()
        mm.finance.run()
        return _optim_float_statistic_mapper(target, mm.model, mm.finance)
    
    if do_bound:
        bounds = []
        for var, trans in zip(variables, transforms):
            if var.bounded:
                bounds.append((trans(var.lower), trans(var.upper)))
            else:
                bounds.append((None, None))
        opt = scipy_opt.minimize(optfunc, x0, method = method, bounds = bounds)
    else:
        opt = scipy_opt.minimize(optfunc, x0, method = method)

    return opt

def evaluate_statistic_across_margin(
    mm: NewsegsMetaModel,
    varid: str,
    stat: str,
    lower: float,
    upper: float,
    resolution: int    
) -> pd.DataFrame:
    """_summary_

    Args:
        mm (NewsegsMetaModel): _description_
        varid (str): _description_
        stat (str): _description_
        lower (float): _description_
        upper (float): _description_
        resolution (int): _description_

    Returns:
        pd.DataFrame: _description_
    """
    # Ensure models are up-to-date
    mm.sync_model_with_changed_variables_deterministic()

    var_backup = copy.deepcopy(mm.variables[varid])
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

    mm.variables[varid] = var_backup
    mm.update_model_from_variable_deterministic(varid)
    mm.model.run()
    mm.finance.run()

    return odf

def statistic_across_margin_plot(
    plot_data,
    mm: NewsegsMetaModel
):
    """_summary_

    Args:
        plot_data (_type_): _description_
        mm (NewsegsMetaModel): _description_

    Returns:
        _type_: _description_
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
    