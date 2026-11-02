"""
Summarise self-consumption data.
"""
import copy
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
    """A variable name or names as a list.

    Args:
        varlist: A name, a sequence of names, or None.

    Returns:
        The names as a list; empty if None.
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
    """Summarise self-consumption and the proportion of generation that is self-consumed.

    The data are totalled for each generator and combination of the grouping variables, and the proportion of generation self-consumed
    is found. Then, if there are `unit_grouping_variables`, the totals are summarised across them by mean, minimum and maximum.

    Args:
        df: Dataframe of `production` and `self_consumption`, with a `generator` column and the grouping variables.
        unit_grouping_variables: Variables whose categories are the units to summarise across (e.g. years): the result gives the mean, minimum and maximum over them.
        agg_grouping_variables: Variables by which to keep the results separate (e.g. season).

    Returns:
        The summary: totals if there are no unit grouping variables, otherwise the mean, minimum and maximum across the units.
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
