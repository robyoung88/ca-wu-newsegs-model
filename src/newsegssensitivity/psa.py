"""
Functions and classes for performing probabilistic sensitivity analysis
"""
from typing import Any, Callable, Literal, Sequence
from typing import get_args
import warnings

import numpy as np
import pandas as pd

from newsegsmetamodel import NewsegsMetaModel
from newsegsmodel import NewsegsModel
from newsegsfinance import NewsegsFinance
from newsegsvariable import variable

PSA_FLOAT_STATISTIC = Literal[
    'total_present_costs_undiscounted',
    'total_present_costs_discounted',
    'total_present_benefits_undiscounted',
    'total_present_benefits_discounted',
    'net_present_value_undiscounted',
    'net_present_value_discounted'
]

def _psa_float_statistic_mapper(
    stat: PSA_FLOAT_STATISTIC,
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
    
    raise ValueError(f'stat {stat} is not known as a PSA statistic')

def _make_psa_result(
    mm: NewsegsMetaModel,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    statistics: Sequence[PSA_FLOAT_STATISTIC],
    return_draws: bool = False,
):
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
    include_deterministic: bool = True,
) -> pd.DataFrame:
    variables = mm.variables.values()
    mdl = mm.model
    fnc = mm.finance

    results = []

    if include_deterministic:
        for v in variables:
            v.psa_active = False
            v.update_model(mdl)
            v.update_model(fnc)
        mdl.run()
        fnc.run()

        res = _make_psa_result(mm, mdl, fnc, statistics, return_draws)
        res['deterministic'] = True
        res['draw'] = 0
        results.append(res)
    
    if samples <= 0:
        return pd.DataFrame(results)
    
    if rng is None:
        rng = np.random.default_rng(seed)
    elif seed is not None:
        warnings.warn('Both a seed and a random generator are provided - existing generator will be used without reseeding')
    
    for v in variables:
        v.psa_active = True
    
    try:
        for i in range(samples):
            for v in variables:
                v.draw_psa(rng)
                v.update_model_psa(mdl)
                v.update_model_psa(fnc)
            
            mdl.run()
            fnc.run()

            res = _make_psa_result(mm, mdl, fnc, statistics, return_draws)
            res['deterministic'] = False
            res['draw'] = i+1
            results.append(res)
            if progress is not None:
                progress(i+1, samples)
    finally:
        for v in variables:
            v.psa_active = False
            v.update_model(mdl)
            v.update_model(fnc)
    
    results = pd.DataFrame(results)
    return results
