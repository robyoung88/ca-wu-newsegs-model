"""
Summarise self-consumption data.
"""
import copy
from collections.abc import Iterable
from typing import MutableSequence

import numpy as np
import numpy.typing as npt
import pandas as pd

from newsegsmodelframework.core.newsegsmoduleresult import filter_meters, NewsegsModuleResult
from newsegsmodelframework.newsegsstats.core import assign_year_index, assign_season_index
from newsegsmodelframework.newsegsgeneration.newsegsgeneration import get_generation_meters

def self_consume(generation: npt.NDArray, 
                 consumption: npt.NDArray
) -> npt.NDArray:
    """
    For meter series, the quantity of generation self-consumed.
    """
    return np.where(
        generation > consumption,
        consumption,
        generation
    )

def as_list(varlist: str|MutableSequence[str]|None) -> list[str]:
    """_summary_

    Args:
        varlist (str | MutableSequence[str] | None): _description_

    Returns:
        list[str]: _description_
    """
    if varlist is None:
        return []
    if isinstance(varlist, str):
        return [varlist]
    return list(varlist)

def selfcons_summary(
    df: pd.DataFrame,
    unit_grouping_variables: str | MutableSequence[str] | None = None,
    agg_grouping_variables: str | MutableSequence[str] | None = None
):
    """_summary_

    Args:
        df (pd.DataFrame): _description_
        unit_grouping_variables (str | MutableSequence[str] | None, optional): _description_. Defaults to None.
        agg_grouping_variables (str | MutableSequence[str] | None, optional): _description_. Defaults to None.

    Returns:
        _type_: _description_
    """
    unit_grouping_variables = as_list(unit_grouping_variables)
    agg_grouping_variables = as_list(agg_grouping_variables)

    init_grouping_variables = (
        ['generator'] 
        + unit_grouping_variables 
        + agg_grouping_variables
    )
    init_grouping_variables = list(set(init_grouping_variables))

    precompute = (
        df
        .groupby(init_grouping_variables)
        .agg('sum')
        .assign(
            prop_gen_self_consumption = lambda df: \
                df['self_consumption'] / df['production']
        )
    )

    if len(unit_grouping_variables) == 0 and len(agg_grouping_variables) == 0:
        # No further disaggregation - makes sense to return as-is
        precompute.columns = pd.MultiIndex.from_arrays([precompute.columns, ['sum']*len(precompute.columns)])
        return precompute
    
    if len(agg_grouping_variables) == 0:
        init_grouping_variables.remove('generator')
        return(
            precompute
            .reset_index()
            .drop(columns=init_grouping_variables)
            .groupby('generator')
            .agg(['mean', 'min', 'max'])
        )
    
    if len(unit_grouping_variables) == 0:
        precompute.columns = pd.MultiIndex.from_arrays([precompute.columns, ['sum']*len(precompute.columns)])
        return precompute
    
    keepvars = ['generator'] + agg_grouping_variables
    keepvars = list(set(keepvars))
    dropvars = copy.copy(init_grouping_variables)
    for v in init_grouping_variables:
        if v in keepvars:
            dropvars.remove(v)

    return(
            precompute
            .reset_index()
            .drop(columns=dropvars)
            .groupby(keepvars)
            .agg(['mean', 'min', 'max'])
        )

def to_self_consumption(
    consumption_storage_result: NewsegsModuleResult,
    generation_result: NewsegsModuleResult
):
    """
    Convert model results to a self-consumption dataframe
    """
    conr = consumption_storage_result
    genr = generation_result

    cons_meters = filter_meters(conr, 'load')

    cons_data = (
        conr.meters_to_pandas()
        .loc[:, cons_meters]
        .apply(sum, axis=1)
        .rename('consumption')
    )

    gen_data = get_generation_meters(genr)

    selfcons_data = (
        gen_data
        .apply(
            lambda col: self_consume(col, cons_data.to_numpy())
        )
    )

    # Before we do the pivot, we might as well get the season indices so that we can
    # bind them on afterwards
    time_indices = (
        gen_data.index
        .to_frame()
        .rename(columns={0:'datetime'})
        .pipe(assign_year_index)
        .pipe(assign_season_index)
        .set_index('datetime')
    )

    pivoted = (
        gen_data
        .melt(
            var_name='generator',
            value_name='production',
            ignore_index=False
        )
        .reset_index(names='datetime')
        .set_index(['datetime', 'generator'])
        .join(
            selfcons_data
            .melt(
                var_name='generator',
                value_name='self_consumption',
                ignore_index=False
            )
            .reset_index(names='datetime')
            .set_index(['datetime', 'generator'])
        )
        .reset_index()
        .set_index('datetime')
        .join(time_indices)
        .query('year_index > -1')
    )

    return pivoted
