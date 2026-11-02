"""Presentation of statistics of results: formatters, and tables of the statistics of several configurations side by side.
"""
from collections.abc import Callable, Mapping, Iterable

from functools import reduce, partial

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from newsegsmodelframework.core.timespan import SEASON_NAMES
from newsegsmodelframework.newsegssensitivity import common as sensitivity

DEFAULT_SEASON_MAPPER = {k: v for k,v in enumerate(SEASON_NAMES)}

DEFAULT_STATISTIC_MAPPER = {
    'mean': 'Mean',
    'min': 'Min',
    'max': 'Max',
    'sum': 'Total',
}

DEFAULT_STATISTICS_ANNUAL = ['mean', 'min', 'max']
DEFAULT_STATISTICS_HORIZON = ['sum']

ANNUAL_DEFAULT_STATS = [
                                {'label':'Mean',
                                 'value':'mean'},
                                {'label':'Max',
                                 'value':'max'},
                                {'label':'Min',
                                 'value':'min'}
                             ]

TOTAL_DEFAULT_STATS = [
                            {'label':'Total',
                             'value':'sum'}
                            ]

def format_val_and_proportion(
    val,
    prop
):
    """Format a value with a proportion, as `value (proportion)`.

    Args:
        val: The value.
        prop: The proportion.

    Returns:
        The string.
    """
    return f'{val:,.0f} ({prop:0.1%})'

def format_twoval(
    val1,
    val2
):
    """Format two values, as `value1 | value2`.

    Args:
        val1: First value.
        val2: Second value.

    Returns:
        The string.
    """
    return f'{val1:,.0f} | {val2:,.0f}'

def format_val_and_proportion_with_range(
    mean_val,
    min_val,
    max_val,
    mean_prop,
    min_prop,
    max_prop
):
    """Format a mean value and proportion with their minimum and maximum.

    Args:
        mean_val: Mean value.
        min_val: Minimum value.
        max_val: Maximum value.
        mean_prop: Mean proportion.
        min_prop: Minimum proportion.
        max_prop: Maximum proportion.

    Returns:
        The string.
    """
    return f'{mean_val:,.0f} ({min_val:,.0f}, {max_val:,.0f}) - {mean_prop:,.1%} ({min_prop:,.1%}, {max_prop:,.1%})'

# REVIEW (unreferenced): no references to `annual_selfconsumption_format` found in src/, scripts/ or data/.
def annual_selfconsumption_format(rw):
    """Format the annual self-consumption and its proportion of generation, with ranges, from a row of statistics.

    Args:
        rw: A row of the statistics table.

    Returns:
        The string.
    """
    return format_val_and_proportion_with_range(
        rw[('self_consumption', 'mean')],
        rw[('self_consumption', 'min')],
        rw[('self_consumption', 'max')],
        rw[('prop_gen_self_consumption', 'mean')],
        rw[('prop_gen_self_consumption', 'min')],
        rw[('prop_gen_self_consumption', 'max')]
        )

def annual_selfconsumption_format_single(rw, stat='mean'):
    """Format the annual self-consumption and its proportion of generation, for one statistic.

    Args:
        rw: A row of the statistics table.
        stat: The statistic to use.

    Returns:
        The string.
    """
    return format_val_and_proportion(
        rw[('self_consumption', stat)].iloc[0],
        rw[('prop_gen_self_consumption', stat)].iloc[0]
        )

def annual_consumption_format_single(rw):
    """Format the annual consumption and the consumption per day.

    Args:
        rw: A row of the statistics table.

    Returns:
        The string.
    """
    return format_twoval(
        rw['consumption'].iloc[0],
        rw['per_day'].iloc[0]
        )

ANNUAL_SC_STATS = [
    {'label': 'Year Mean',
     'season': 'Year',
     'formatter': partial(annual_selfconsumption_format_single, stat='mean')},
    {'label': 'Year Max',
     'season': 'Year',
     'formatter': partial(annual_selfconsumption_format_single, stat='max')},
    {'label': 'Year Min',
     'season': 'Year',
     'formatter': partial(annual_selfconsumption_format_single, stat='min')},
    {'label': 'Wtr Mean',
     'season': 'Wtr',
     'formatter': partial(annual_selfconsumption_format_single, stat='mean')},
    {'label': 'Wtr Max',
     'season': 'Wtr',
     'formatter': partial(annual_selfconsumption_format_single, stat='max')},
    {'label': 'Wtr Min',
     'season': 'Wtr',
     'formatter': partial(annual_selfconsumption_format_single, stat='min')},
    {'label': 'Spr Mean',
     'season': 'Spr',
     'formatter': partial(annual_selfconsumption_format_single, stat='mean')},
    {'label': 'Spr Max',
     'season': 'Spr',
     'formatter': partial(annual_selfconsumption_format_single, stat='max')},
    {'label': 'Spr Min',
     'season': 'Spr',
     'formatter': partial(annual_selfconsumption_format_single, stat='min')},
    {'label': 'Smr Mean',
     'season': 'Smr',
     'formatter': partial(annual_selfconsumption_format_single, stat='mean')},
    {'label': 'Smr Max',
     'season': 'Smr',
     'formatter': partial(annual_selfconsumption_format_single, stat='max')},
    {'label': 'Smr Min',
     'season': 'Smr',
     'formatter': partial(annual_selfconsumption_format_single, stat='min')},
    {'label': 'Aut Mean',
     'season': 'Aut',
     'formatter': partial(annual_selfconsumption_format_single, stat='mean')},
    {'label': 'Aut Max',
     'season': 'Aut',
     'formatter': partial(annual_selfconsumption_format_single, stat='max')},
    {'label': 'Aut Min',
     'season': 'Aut',
     'formatter': partial(annual_selfconsumption_format_single, stat='min')},
]

HORIZON_SC_STATS = [
    {'label': 'Total',
     'season': 'Year',
     'formatter': partial(annual_selfconsumption_format_single, stat='sum')},
    {'label': 'Wtr',
     'season': 'Wtr',
     'formatter': partial(annual_selfconsumption_format_single, stat='sum')},
    {'label': 'Spr',
     'season': 'Spr',
     'formatter': partial(annual_selfconsumption_format_single, stat='sum')},
    {'label': 'Smr',
     'season': 'Smr',
     'formatter': partial(annual_selfconsumption_format_single, stat='sum')},
    {'label': 'Aut',
     'season': 'Aut',
     'formatter': partial(annual_selfconsumption_format_single, stat='sum')},
]

ANNUAL_CONS_STATS = [
    {'label': 'Year Mean',
     'season': 'Year',
     'statistic': 'mean',
     'formatter': annual_consumption_format_single},
    {'label': 'Year Max',
     'season': 'Year',
     'statistic': 'max',
     'formatter': annual_consumption_format_single},
    {'label': 'Year Min',
     'season': 'Year',
     'statistic': 'min',
     'formatter': annual_consumption_format_single},
    {'label': 'Wtr Mean',
     'season': 'Wtr',
     'statistic': 'mean',
     'formatter': annual_consumption_format_single},
    {'label': 'Wtr Max',
     'season': 'Wtr',
     'statistic': 'max',
     'formatter': annual_consumption_format_single},
    {'label': 'Wtr Min',
     'season': 'Wtr',
     'statistic': 'min',
     'formatter': annual_consumption_format_single},
    {'label': 'Spr Mean',
     'season': 'Spr',
     'statistic': 'mean',
     'formatter': annual_consumption_format_single},
    {'label': 'Spr Max',
     'season': 'Spr',
     'statistic': 'max',
     'formatter': annual_consumption_format_single},
    {'label': 'Spr Min',
     'season': 'Spr',
     'statistic': 'min',
     'formatter': annual_consumption_format_single},
    {'label': 'Smr Mean',
     'season': 'Smr',
     'statistic': 'mean',
     'formatter': annual_consumption_format_single},
    {'label': 'Smr Max',
     'season': 'Smr',
     'statistic': 'max',
     'formatter': annual_consumption_format_single},
    {'label': 'Smr Min',
     'season': 'Smr',
     'statistic': 'min',
     'formatter': annual_consumption_format_single},
    {'label': 'Aut Mean',
     'season': 'Aut',
     'statistic': 'mean',
     'formatter': annual_consumption_format_single},
    {'label': 'Aut Max',
     'season': 'Aut',
     'statistic': 'max',
     'formatter': annual_consumption_format_single},
    {'label': 'Aut Min',
     'season': 'Aut',
     'statistic': 'min',
     'formatter': annual_consumption_format_single},
]

HORIZON_CONS_STATS = [
    {'label': 'Total',
     'season': 'Year',
     'statistic': 'sum',
     'formatter': annual_consumption_format_single},
    {'label': 'Wtr',
     'season': 'Wtr',
     'statistic': 'sum',
     'formatter': annual_consumption_format_single},
    {'label': 'Spr',
     'season': 'Spr',
     'statistic': 'sum',
     'formatter': annual_consumption_format_single},
    {'label': 'Smr',
     'season': 'Smr',
     'statistic': 'sum',
     'formatter': annual_consumption_format_single},
    {'label': 'Aut',
     'season': 'Aut',
     'statistic': 'sum',
     'formatter': annual_consumption_format_single},
]

ANNUAL_SEASONAL_STATS = [
    {'label':'Year Mean',
     'value':'mean_year'},
    {'label':'Year Max',
     'value':'max_year'},
    {'label':'Year Min',
     'value':'min_year'},
    {'label':'Wtr Mean',
     'value':'mean_wtr'},
    {'label':'Wtr Max',
     'value':'max_wtr'},
    {'label':'Wtr Min',
     'value':'min_wtr'},
    {'label':'Spr Mean',
     'value':'mean_spr'},
    {'label':'Spr Max',
     'value':'max_spr'},
    {'label':'Spr Min',
     'value':'min_spr'},
    {'label':'Smr Mean',
     'value':'mean_smr'},
    {'label':'Smr Max',
     'value':'max_smr'},
    {'label':'Smr Min',
     'value':'min_smr'},
    {'label':'Aut Mean',
     'value':'mean_aut'},
    {'label':'Aut Max',
     'value':'max_aut'},
    {'label':'Aut Min',
     'value':'min_aut'}
]

TOTAL_SEASONAL_STATS = [
    {'label':'Year',
     'value':'total_year'},
    {'label':'Wtr',
     'value':'total_wtr'},
    {'label':'Spr',
     'value':'total_spr'},
    {'label':'Smr',
     'value':'total_smr'},
    {'label':'Aut',
     'value':'total_aut'}
]

DEFAULT_HOURS_IN_RANGE_STATS = [
    {'label':r'0%≤x<5%',
     'value':'hrs_000_to_005'},
    {'label':r'5%≤x<25%',
     'value':'hrs_005_to_025'},
    {'label':r'25%≤x<50%',
     'value':'hrs_025_to_050'},
    {'label':r'50%≤x<75%',
     'value':'hrs_050_to_075'},
    {'label':r'75%≤x<95%',
     'value':'hrs_075_to_095'},
    {'label':r'95%≤x≤100%',
     'value':'hrs_095_to_999'}
    ]

DEFAULT_DAYS_IN_RANGE_STATS = [
    {'label':r'0%≤x<5%',
     'value':'days_000_to_005'},
    {'label':r'5%≤x<25%',
     'value':'days_005_to_025'},
    {'label':r'25%≤x<50%',
     'value':'days_025_to_050'},
    {'label':r'50%≤x<75%',
     'value':'days_050_to_075'},
    {'label':r'75%≤x<95%',
     'value':'days_075_to_095'},
    {'label':r'95%≤x≤100%',
     'value':'days_095_to_999'}
    ]

def DEFAULT_STAT_FORMATTER(stat_dict):
    """Default formatter of a dictionary of statistics: its string.

    Args:
        stat_dict: Dictionary of the statistics.

    Returns:
        The string.
    """
    return str(stat_dict)

def recursive_get(d, *keys):
    """Follow a sequence of keys through nested dictionaries.

    A missing key gives an empty dictionary.

    Args:
        d: Dictionary of the statistics, or None.
        *keys: The keys to follow.

    Returns:
        The value found.
    """
    return reduce(lambda c, k: c.get(k, {}), keys, d)

def hours_in_range_formatter(d):
    """Format the hours spent within a power range, with the fraction of the horizon.

    Args:
        d: Dictionary of the statistics, or None.

    Returns:
        The string.
    """
    if d is None:
        return "( -  kW) - (%)"
    return f"({d.get('min_power'):,.0f} - {d.get('max_power'):,.0f}) {d.get('hours'):,.1f} ({d.get('horizon_fraction'):,.1%})"

def days_in_range_formatter(d):
    """Format the days spent within a range of daily energy, with the fraction of the horizon.

    Args:
        d: Dictionary of the statistics, or None.

    Returns:
        The string.
    """
    if d is None:
        return "( - kWh) - (%)"
    return f"({d.get('min_value'):,.0f} - {d.get('max_value'):,.0f}) {d.get('days'):,.0f} ({d.get('horizon_fraction'):,.1%})"

# REVIEW (unreferenced): no references to `val_percent_formatter_factory` found in src/, scripts/ or data/.
def val_percent_formatter_factory(value_id, fraction_id, value_dp=0, fraction_dp=1):
    """Make a formatter of a value and a fraction in a dictionary, as `value (percent)`.

    Args:
        value_id: Key of the value in the dictionary.
        fraction_id: Key of the fraction in the dictionary.
        value_dp: Decimal places of the value.
        fraction_dp: Decimal places of the fraction.

    Returns:
        The formatter, a function of the dictionary.
    """
    fmt = "{:,." + str(value_dp) + "f} ({:,." + str(fraction_dp) + "%})"
    def val_percent_formatter(d):
        if d is None:
            return "- (-%)"
        return fmt.format(d.get(value_id),d.get(fraction_id))
    return val_percent_formatter

# REVIEW (unreferenced): no references to `recursive_val_percent_formatter_factory` found in src/, scripts/ or data/.
def recursive_val_percent_formatter_factory(value_id, fraction_id, value_dp=0, fraction_dp=1):
    """Make a formatter of a value and a fraction in nested dictionaries, as `value (percent)`.

    The ids are sequences of keys, followed through the dictionaries.

    Args:
        value_id: Key of the value in the dictionary.
        fraction_id: Key of the fraction in the dictionary.
        value_dp: Decimal places of the value.
        fraction_dp: Decimal places of the fraction.

    Returns:
        The formatter, a function of the dictionary.
    """
    fmt = "{:,." + str(value_dp) + "f} ({:,." + str(fraction_dp) + "%})"
    def val_percent_formatter(d):
        if d is None:
            return "- (-%)"
        return fmt.format(recursive_get(d, *value_id), recursive_get(d, *fraction_id))
    return val_percent_formatter

def as_df(
    df: None|pd.DataFrame|dict,
    orient: str = 'columns',
    index_variables: list = ['variable', 'statistic']
) -> pd.DataFrame | None:
    """Convert statistics to a dataframe indexed by the index variables.

    Args:
        df: The dataframe.
        orient: Orientation of the data in a dictionary.
        index_variables: Names of the index levels.

    Returns:
        The dataframe, or None if there are no statistics.
    """
    if df is None:
        return None
    if isinstance(df, pd.DataFrame):
        if set(df.index.names) == set(index_variables):
            return df
        else:
            if df.index.names[0] is None:
                df.set_index(index_variables)
            else:
                df.reset_index().set_index(index_variables)
    return pd.DataFrame.from_dict(df, orient=orient).set_index(index_variables) # pyright: ignore[reportCallIssue, reportArgumentType]

def _label_demap(str_list:Iterable, mapper: None|Callable|Mapping = None) -> Iterable:
    if mapper is None:
        return str_list
    elif isinstance(mapper, Callable):
        return [mapper(x) for x in str_list]
    elif isinstance(mapper, Mapping):
        return [mapper[x] for x in str_list]
    elif isinstance(mapper, pd.DataFrame):
        return [mapper.loc[x,:] for x in str_list]
    else:
        raise ValueError("`mapper` must be a mapping or callable, is ", type(mapper))

def present_single_scalar(
    data_list,
    value_name,
    variable_label,
    statistic_label,
    fmt='{:,.2f}',
    none_str = '-'
) -> pd.DataFrame:
    
    """Present one scalar of each configuration as a single row of a table, with a column for each configuration.

    Args:
        data_list: Statistics of each configuration (metamodel), or None where there are none.
        value_name: Key of the value in the statistics.
        variable_label: Label of the variable in the table.
        statistic_label: Label of the statistic in the table.
        fmt: Format string for the values.
        none_str: String shown where there is no value.

    Returns:
        The dataframe.
    """
    src_data = [x.get(value_name) if x is not None else None for x in data_list]

    odata = {f'config-{i+1}': [fmt.format(x)] if x is not None else [none_str] for i,x in enumerate(src_data)}
    odata['variable'] = [variable_label]
    odata['statistic'] = [statistic_label]
    
    return (
        pd.DataFrame
        .from_dict(odata, orient='columns')
        .set_index(['variable', 'statistic'])
    )

def present_paired_scalars(
    data_list,
    value1_name,
    value2_name,
    variable_label,
    statistic_label,
    fmt='{:,.2f} ({:,.1%})',
    none_str = '-'
) -> pd.DataFrame:
    """Present a scalar and a related scalar (e.g. a value and its proportion) of each configuration as a single row of a table.

    Args:
        data_list: Statistics of each configuration (metamodel), or None where there are none.
        value1_name: See the description.
        value2_name: See the description.
        variable_label: Label of the variable in the table.
        statistic_label: Label of the statistic in the table.
        fmt: Format string for the values.
        none_str: String shown where there is no value.

    Returns:
        The dataframe.
    """
    src_data_1 = [x.get(value1_name) if x is not None else None for x in data_list]
    src_data_2 = [x.get(value2_name) if x is not None else None for x in data_list]
    odata = {f'config-{i+1}': [fmt.format(src_data_1[i], src_data_2[i])] if src_data_1[i] is not None else [none_str] for i,_ in enumerate(src_data_1)}

    odata['variable'] = [variable_label]
    odata['statistic'] = [statistic_label]
    return (
        pd.DataFrame
        .from_dict(odata, orient='columns')
        .set_index(['variable', 'statistic'])
    )

def present_single_stat_per_row(
    data_list,
    table_name,
    variable_names,
    statistic_names=DEFAULT_STATISTICS_ANNUAL,
    fmt='{:,.2f}',
    none_str='-',
    variable_mapper: None|Callable|Mapping = None,
    statistic_mapper: None|Callable|Mapping = DEFAULT_STATISTIC_MAPPER
) -> pd.DataFrame:

    """Present statistics of variables in a table with a row for each variable and statistic and a column for each configuration.

    Args:
        data_list: Statistics of each configuration (metamodel), or None where there are none.
        table_name: Key of the table in the statistics.
        variable_names: Names of the variables to show.
        statistic_names: Names of the statistics to show.
        fmt: Format string for the values.
        none_str: String shown where there is no value.
        variable_mapper: Mapping or function from variable names to labels.
        statistic_mapper: Mapping or function from statistic names to labels.

    Returns:
        The dataframe; empty if there are no statistics.
    """
    valid_config_indexes = [i for i, x in enumerate(data_list) if x is not None]
    if len(valid_config_indexes) == 0:
        return pd.DataFrame()

    src_data = [as_df(x.get(table_name)) for x in data_list if x is not None]
    
    if isinstance(variable_names, str):
        variable_names = [variable_names]
    if isinstance(statistic_names, str):
        statistic_names = [statistic_names]

    extract_mi = pd.MultiIndex.from_product(
        [variable_names, statistic_names], 
        names=['variable','statistic']
    )

    def extract_from_table(idx):
        tbl = src_data[idx]
        if tbl is None:
            subtable = (
                pd.DataFrame({'value':[none_str]*len(extract_mi)})
                .set_index(extract_mi)
            )
        else:
            subtable = (
                tbl.loc[extract_mi, ['value']]
                .assign(value = lambda df: df['value'].apply(lambda x: fmt.format(x)))
            )
        subtable = (
            subtable
            .rename(columns = {'value': 'config-'+str(valid_config_indexes[idx]+1)})
        )
        return subtable
    
    otbl = pd.concat([extract_from_table(i) for i in range(len(valid_config_indexes))], axis=1)

    variable_labels = _label_demap(variable_names, variable_mapper)
    statistic_labels = _label_demap(statistic_names, statistic_mapper)
    
    label_mi = pd.MultiIndex.from_product(
        [variable_labels, statistic_labels], 
        names=['variable','statistic']
    )

    otbl.index = label_mi
    
    return otbl

def present_paired_seasonal_stats(
    data_list,
    table1_name,
    table2_name,
    variable_names,
    statistic_names = DEFAULT_STATISTICS_ANNUAL,
    season_indices = range(len(SEASON_NAMES)),
    fmt='{:,.2f} ({:,.1%})',
    none_str='-',
    variable_mapper: None|Callable|Mapping = None,
    statistic_mapper: None|Callable|Mapping = DEFAULT_STATISTIC_MAPPER,
    season_mapper: None|Callable|Mapping = DEFAULT_SEASON_MAPPER,
) -> pd.DataFrame:
    """Present two related seasonal statistics (e.g. a value and its proportion) in a table with a row for each variable, season and statistic and a column for each configuration.

    Args:
        data_list: Statistics of each configuration (metamodel), or None where there are none.
        table1_name: Key of the first table in the statistics.
        table2_name: Key of the second table in the statistics.
        variable_names: Names of the variables to show.
        statistic_names: Names of the statistics to show.
        season_indices: Indices of the seasons to show.
        fmt: Format string for the values.
        none_str: String shown where there is no value.
        variable_mapper: Mapping or function from variable names to labels.
        statistic_mapper: Mapping or function from statistic names to labels.
        season_mapper: Mapping or function from season index to label.

    Returns:
        The dataframe; empty if there are no statistics.
    """
    valid_config_indexes = [i for i, x in enumerate(data_list) if x is not None]
    if len(valid_config_indexes) == 0:
        return pd.DataFrame()

    src_data1 = [as_df(x.get(table1_name), index_variables=['variable', 'season_index', 'statistic']) for x in data_list if x is not None]
    src_data2 = [as_df(x.get(table2_name), index_variables=['variable', 'season_index', 'statistic']) for x in data_list if x is not None]

    if isinstance(variable_names, str):
        variable_names = [variable_names]
    if isinstance(statistic_names, str):
        statistic_names = [statistic_names]

    extract_mi = pd.MultiIndex.from_product(
        [variable_names, season_indices, statistic_names],
        names=['variable', 'season', 'statistic']
    )

    def extract_from_table(idx):
        tbl1 = src_data1[idx]
        tbl2 = src_data2[idx]
        if tbl1 is None:
            subtable =  (
                pd.DataFrame({'value':[none_str]*len(extract_mi)})
                .set_index(extract_mi)
            )
        else:
            subtable = (
                pd.merge(
                    tbl1.loc[extract_mi, ['value']].rename(columns={'value':'v1'}),
                    tbl2.loc[extract_mi, ['value']].rename(columns={'value':'v2'}),
                    left_index=True,
                    right_index=True
                )
                .assign(value = lambda df: df.apply(lambda rw: fmt.format(rw['v1'], rw['v2']), axis=1))
                .drop(columns=['v1', 'v2'])
            )
        
        subtable = (
            subtable
            .rename(columns = {'value': 'config-'+str(valid_config_indexes[idx]+1)})
        )
        return subtable
    
    otbl = pd.concat([extract_from_table(i) for i in range(len(valid_config_indexes))], axis=1)

    variable_labels = _label_demap(variable_names, variable_mapper)
    season_labels = _label_demap(season_indices, season_mapper)
    statistic_labels = _label_demap(statistic_names, statistic_mapper)

    label_mi = pd.MultiIndex.from_product(
        [variable_labels, season_labels, statistic_labels], 
        names=['variable', 'season', 'statistic']
    )

    otbl.index = label_mi

    return otbl

def present_single_stat_per_row_plus_paired_scalars(
    data_list,
    table_name,
    variable_names,
    scalar_value1_name,
    scalar_value2_name,
    statistic_names=DEFAULT_STATISTICS_ANNUAL,
    variable_mapper: None|Callable|Mapping = None,
    statistic_mapper: None|Callable|Mapping = DEFAULT_STATISTIC_MAPPER,
    fmt = '{:,.2f} ({:,.1%}/{:,.1%})',
    none_str = '-',
) -> pd.DataFrame:
    """
    Used primarily for discounted ratios in the form "val (num%/den%)"
    """
    valid_config_indexes = [i for i, x in enumerate(data_list) if x is not None]
    if len(valid_config_indexes) == 0:
        return pd.DataFrame()

    src_data = [as_df(x.get(table_name)) for x in data_list if x is not None]
    scalar_data_1 = [x.get(scalar_value1_name) for x in data_list if x is not None]
    scalar_data_2 = [x.get(scalar_value2_name) for x in data_list if x is not None]

    if isinstance(variable_names, str):
        variable_names = [variable_names]
    if isinstance(statistic_names, str):
        statistic_names = [statistic_names]

    extract_mi = pd.MultiIndex.from_product(
        [variable_names, statistic_names], 
        names=['variable','statistic']
    )

    def extract_from_table(idx):
        tbl = src_data[idx]
        if tbl is None:
            subtable = (
                pd.DataFrame({'value':[none_str]*len(extract_mi)})
                .set_index(extract_mi)
            )
        else:
            scl1 = scalar_data_1[idx]
            scl2 = scalar_data_2[idx]
            subtable = (
                tbl.loc[extract_mi, ['value']]
                .assign(value = lambda df: df['value'].apply(lambda x: fmt.format(x, scl1, scl2)))
            )
        subtable = (
            subtable
            .rename(columns = {'value': 'config-'+str(valid_config_indexes[idx]+1)})
        )
        return subtable
    
    otbl = pd.concat([extract_from_table(i) for i in range(len(valid_config_indexes))], axis=1)

    variable_labels = _label_demap(variable_names, variable_mapper)
    statistic_labels = _label_demap(statistic_names, statistic_mapper)
    
    label_mi = pd.MultiIndex.from_product(
        [variable_labels, statistic_labels], 
        names=['variable','statistic']
    )

    otbl.index = label_mi
    
    return otbl
    
def _compound_trans_stats(data_list, stat_name, stat_formatter, stat_list):
    n_rows = len(stat_list)

    # Grab the computed results for the desired stat
    if isinstance(stat_name, str):
        comp_result = [x.get(stat_name, None) if x is not None else None for x in data_list]
    else:
        comp_result = [recursive_get(x, *stat_name) if x is not None else None for x in data_list]

    def transform_stats(config_results):
        def trans_stat(idx):
            if config_results is None:
                return None
            stat = stat_list[idx]
            formatter = stat.get('formatter', None)
            if formatter is None:
                formatter = stat_formatter

            val_lookup = stat.get('value')

            idict = config_results.get(val_lookup, None)

            if idict is None:
                return idict            
            
            return formatter(idict)

        return {stat_list[i].get('value'): trans_stat(i) for i in range(n_rows)}

    return [{str(stat_name): transform_stats(x)} for x in comp_result]

def _self_consumption_trans_stats(data_list, table_name, stat_list, index_filter):
    """
    Returns the per-config formatted stats, and a copy of stat_list with each
    'value' set to its 'label' so that the formatted stats can be looked up.
    """
    n_rows = len(stat_list)

    # Get the list of tight dictionary representations of dataframes
    if isinstance(table_name, str):
        dict_data = [x.get(table_name, None if x is not None else None) for x in data_list]
    else:
        dict_data = [recursive_get(x, *table_name) if x is not None else None for x in data_list]

    def transform_stats(table_data):
        if table_data is None or table_data == {}:
            df = None
        else:
            df = pd.DataFrame.from_dict(table_data, orient='tight').loc[index_filter, :]

        def trans_stat(idx):
            if df is None:
                return None
            
            stat = stat_list[idx]
            season = stat.get('season')
            formatter = stat.get('formatter')

            fdf = df.loc[df['season']==season, :]

            return formatter(fdf)
        
        return {stat_list[i].get('label'): trans_stat(i) for i in range(n_rows)}

    trans_stats = [{str(table_name): transform_stats(x)} for x in dict_data]

    return trans_stats, [{**x, 'value': x['label']} for x in stat_list]

def _seasonal_consumption_trans_stats(data_list, table_name, stat_list):
    """
    Returns the per-config formatted stats, and a copy of stat_list with each
    'value' set to its 'label' so that the formatted stats can be looked up.
    """
    n_rows = len(stat_list)

    # Get the list of tight dictionary representations of dataframes
    if isinstance(table_name, str):
        dict_data = [x.get(table_name, None) if x is not None else None for x in data_list]
    else:
        dict_data = [recursive_get(x, *table_name) if x is not None else None for x in data_list]

    def transform_stats(table_data):
        if table_data is None or table_data == {}:
            df = None
        else:
            df = pd.DataFrame.from_dict(table_data, orient='tight')

        def trans_stat(idx):
            if df is None:
                return None
            
            stat = stat_list[idx]
            season = stat.get('season')
            statistic = stat.get('statistic')
            formatter = stat.get('formatter')
            fdf = df.loc[df['season']==season, :]
            fdf = fdf.loc[fdf['statistic']==statistic, :]

            return formatter(fdf)
        return {stat_list[i].get('label'): trans_stat(i) for i in range(n_rows)}

    trans_stats = [{str(table_name): transform_stats(x)} for x in dict_data]

    return trans_stats, [{**x, 'value': x['label']} for x in stat_list]

# -----------------------------------------------
# Record builders
#
# Each returns a list of row dicts for rendering with
# results_table.create_result_grid, keyed by the label fields 'variable',
# optionally 'season', and 'statistic', plus 'config-N' per configuration.
# A cell value is either a display string or, for a zoomable date,
# {'label': ..., 'start': ...[, 'end': ...]}.
# -----------------------------------------------

def _config_key(idx):
    return f'config-{idx+1}'

def _comp_results(data_list, stat_name):
    if isinstance(stat_name, str):
        return [x.get(stat_name, None) if x is not None else None for x in data_list]
    return [recursive_get(x, *stat_name) if x is not None else None for x in data_list]

def dataframe_records(df: pd.DataFrame) -> list[dict]:
    """
    Records from a table made by the present_* functions, indexed by
    'variable'[, 'season'], 'statistic' with a column per configuration.
    """
    if df.empty:
        return []
    return df.reset_index().to_dict('records')

def single_stat_records(
    data_list,
    stat_name,
    stat_label,
    stat_value='mean',
    fmt='{:.2f}',
    none_str='-'
) -> list[dict]:
    """A single row of one statistic per configuration"""
    comp_result = _comp_results(data_list, stat_name)

    rec = {'variable': stat_label, 'statistic': ''}
    for i, x in enumerate(comp_result):
        val = x.get(stat_value, None) if x is not None else None
        rec[_config_key(i)] = fmt.format(val) if val is not None else none_str
    return [rec]

def stat_description_records(
    data_list,
    stat_name,
    stat_label,
    stat_list=ANNUAL_DEFAULT_STATS,
    fmt='{:,.2f}',
    none_str='-'
) -> list[dict]:
    """A row per statistic in stat_list"""
    comp_result = _comp_results(data_list, stat_name)

    records = []
    for stat in stat_list:
        val_fmt = stat.get('fmt', None) or fmt
        val_lookup = stat.get('value')
        rec = {'variable': stat_label, 'statistic': stat['label']}
        for i, x in enumerate(comp_result):
            val = x.get(val_lookup, None) if x is not None else None
            rec[_config_key(i)] = val_fmt.format(val) if val is not None else none_str
        records.append(rec)
    return records

def stat_description_parallel_records(
    data_list,
    container_name,
    stat_label,
    stat1_name,
    stat2_name,
    stat_list = ANNUAL_DEFAULT_STATS,
    fmt1='{:,.0f}',
    fmt2='{:,.1%}',
    none_str='-'
) -> list[dict]:
    """A row per statistic in stat_list, formatted as 'stat1 (stat2)'"""
    config_containers = _comp_results(data_list, container_name)

    records = []
    for stat in stat_list:
        val_lookup = stat.get('value')
        rec = {'variable': stat_label, 'statistic': stat['label']}
        for i, x in enumerate(config_containers):
            val_1 = x.get(stat1_name, {}).get(val_lookup) if x is not None else None
            val_2 = x.get(stat2_name, {}).get(val_lookup) if x is not None else None
            rec[_config_key(i)] = fmt1.format(val_1) + ' (' + fmt2.format(val_2) + ')' if val_1 is not None else none_str
        records.append(rec)
    return records

def stat_description_compound_records(
    data_list,
    stat_name,
    stat_label,
    stat_formatter=DEFAULT_STAT_FORMATTER,
    stat_list=DEFAULT_HOURS_IN_RANGE_STATS
) -> list[dict]:
    """A row per statistic in stat_list, allowing compound formatting of values"""
    trans_stats = _compound_trans_stats(data_list, stat_name, stat_formatter, stat_list)
    return stat_description_records(trans_stats, str(stat_name), stat_label, stat_list, fmt="{}")

def self_consumption_records(
    data_list,
    table_name,
    stat_label,
    stat_list=ANNUAL_SC_STATS,
    index_filter='generation_export'
) -> list[dict]:
    """Self-consumption extracted from a list of generation data"""
    trans_stats, stat_list = _self_consumption_trans_stats(data_list, table_name, stat_list, index_filter)
    return stat_description_records(trans_stats, str(table_name), stat_label, stat_list, fmt="{}")

def seasonal_consumption_records(
    data_list,
    table_name,
    stat_label,
    stat_list=ANNUAL_CONS_STATS
) -> list[dict]:
    """Seasonal consumption extracted from a list of consumption data"""
    trans_stats, stat_list = _seasonal_consumption_trans_stats(data_list, table_name, stat_list)
    return stat_description_records(trans_stats, str(table_name), stat_label, stat_list, fmt="{}")

def event_and_date_records(
    data_list,
    event_name,
    event_label,
    event_value,
    event_value_formatter,
    date_label='On:',
    event_date='datetime',
    none_str='-',
    nonedate_str='#/#/#',
    trimdate=15
) -> list[dict]:
    """
    A value row and a date row for an event. The date row holds zoomable
    date cells.
    """
    comp_result = _comp_results(data_list, event_name)

    val_row = {'variable': event_label, 'statistic': ''}
    date_row = {'variable': event_label, 'statistic': date_label, '_align_end': True}
    for i, x in enumerate(comp_result):
        if x is None:
            val_row[_config_key(i)] = none_str
            date_row[_config_key(i)] = none_str
            continue
        val_row[_config_key(i)] = event_value_formatter(x.get(event_value))
        date = x.get(event_date)[:-trimdate]
        date_row[_config_key(i)] = {'label': date, 'start': date}

    return [val_row, date_row]

def event_and_daterange_records(
    data_list,
    event_name,
    event_label,
    event_value,
    event_value_formatter,
    range_label='From - To',
    event_start='datetime_start',
    event_end='datetime_end',
    none_str='-',
    nonedate_str='#/#/# - #/#/#',
    trimdate=9
) -> list[dict]:
    """
    A value row and a date range row for an event. The date row holds
    zoomable date range cells.
    """
    comp_result = _comp_results(data_list, event_name)

    val_row = {'variable': event_label, 'statistic': ''}
    # '_wrap' gives the row room for the range to wrap onto a second line
    date_row = {'variable': event_label, 'statistic': range_label, '_align_end': True, '_wrap': True}
    for i, x in enumerate(comp_result):
        if x is None:
            val_row[_config_key(i)] = none_str
            date_row[_config_key(i)] = nonedate_str
            continue
        val_row[_config_key(i)] = event_value_formatter(x.get(event_value))
        start = x.get(event_start)[:-trimdate]
        end = x.get(event_end)[:-trimdate]
        date_row[_config_key(i)] = {'label': f'{start} - {end}', 'start': start, 'end': end}

    return [val_row, date_row]

# -----------------------------------------------
# DSA tables and plots
#
# The DSA tables are those of post_dsa_results.dsa_results_to_tables: indexed
# by 'variable' and 'statistic', with columns ('absolute', central / lower /
# upper / interval) and ('delta', lower / upper). The same tables hold the
# results of one configuration or the increments of a pairwise comparison.
# -----------------------------------------------

DSA_ALL_STATISTIC_LABELS = {**sensitivity.DSA_STATISTIC_LABELS, **sensitivity.DSA_PAIRWISE_STATISTIC_LABELS}
"""Labels of the statistics of a DSA, individual and pairwise, by statistic."""

DSA_BOUND_COLUMNS = ['central', 'lower', 'upper', 'interval']
"""Columns of the absolute values of a DSA table, in the order that they are shown."""

COMPARATOR_COLORS = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
"""Colors of the comparators (configurations) of a plot, in fixed order: a comparator keeps its color whatever is selected."""

def filter_dsa_variables(dsa_df: pd.DataFrame, variables: Iterable[str] | None = None) -> pd.DataFrame:
    """Keep the rows of a DSA table for the variables.

    Args:
        dsa_df: DSA table, indexed by 'variable' and 'statistic'.
        variables: Labels of the variables to keep; None keeps all.

    Returns:
        The dataframe.
    """
    if variables is None:
        return dsa_df
    variables = set(variables)
    return dsa_df.loc[dsa_df.index.get_level_values('variable').isin(variables), :]

def dsa_statistic_table(
    dsa_df: pd.DataFrame,
    statistic: str,
    variables: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Table of one statistic of a DSA: a row for each variable, with the central, lower and upper values and the interval.

    Args:
        dsa_df: DSA table, indexed by 'variable' and 'statistic'.
        statistic: The statistic.
        variables: Labels of the variables to show; None shows all.

    Returns:
        The dataframe, with a 'variable' column.
    """
    return (
        filter_dsa_variables(dsa_df, variables)
        .xs(statistic, level = 'statistic', axis = 0)
        .xs('absolute', level = 0, axis = 1)
        .loc[:, ['central', 'interval', 'lower', 'upper']]
        .reset_index()
    )

def _sorted_dsa_variables(plot_frames: Iterable[pd.DataFrame]) -> list:
    """Variables of the plot data of one or more DSAs, by the largest interval in any of them."""
    intervals = pd.concat(
        [x[('absolute', 'interval')].abs() for x in plot_frames], axis = 1
    ).max(axis = 1, skipna = True)
    return intervals.sort_values(ascending = False, na_position = 'last').index.tolist()

def dsa_comparison_table(
    dsa_dfs: Mapping[str, pd.DataFrame],
    statistic: str,
    variables: Iterable[str] | None = None,
) -> pd.DataFrame:
    """Table of one statistic of the DSAs of several comparators side by side.

    The variables are sorted by the largest interval of any comparator. A variable not varied by a comparator has
    no values for it.

    Args:
        dsa_dfs: DSA tables, indexed by 'variable' and 'statistic', by the label of the comparator.
        statistic: The statistic.
        variables: Labels of the variables to show; None shows all.

    Returns:
        The dataframe, indexed by variable, with columns (comparator, bound) for each bound of `DSA_BOUND_COLUMNS`.
    """
    frames = {
        k: filter_dsa_variables(v, variables).xs(statistic, level = 'statistic', axis = 0).xs('absolute', level = 0, axis = 1)
        for k, v in dsa_dfs.items()
    }
    frames = {k: v for k, v in frames.items() if len(v)}
    if not frames:
        return pd.DataFrame()
    order = _sorted_dsa_variables(
        [pd.concat({'absolute': v}, axis = 1) for v in frames.values()]
    )
    otable = pd.concat(
        {k: v.loc[:, DSA_BOUND_COLUMNS] for k, v in frames.items()}, axis = 1
    )
    otable.columns.names = ['comparator', 'bound']
    return otable.loc[order, :]

def _empty_dsa_figure(message: str = 'No DSA results to show'):
    fig = go.Figure()
    fig.add_annotation(text = message, showarrow = False, xref = 'paper', yref = 'paper', x = 0.5, y = 0.5)
    fig.update_layout(template = 'plotly_white', xaxis_visible = False, yaxis_visible = False)
    return fig

def _dsa_plot_data(dsa_df, statistic, variables = None):
    return (
        filter_dsa_variables(dsa_df, variables)
        .xs(statistic, axis = 0, level = 'statistic')
        # Ratios may be infinite where the incremental costs are zero
        .replace([np.inf, -np.inf], np.nan)
    )

def tornado_plot(
    dsa_df,
    label_df,
    statistic = 'net_present_value_undiscounted',
    variables: Iterable[str] | None = None,
    title: str = 'Lower and Upper DSA variation',
):
    """Draw a tornado plot of the results of a deterministic sensitivity analysis.

    The variables are sorted by the size of the interval of the statistic. The results may be those of one
    configuration, or the increments of a pairwise comparison.

    Args:
        dsa_df: Dataframe of the results of the sensitivity analysis.
        label_df: Dataframe of the labels of the variables.
        statistic: The statistic to plot.
        variables: Labels of the variables to plot; None plots all.
        title: Title of the plot.

    Returns:
        The figure.
    """
    plot_data = _dsa_plot_data(dsa_df, statistic, variables)
    if not len(plot_data):
        return _empty_dsa_figure()
    plot_data = plot_data.sort_values(
        ('absolute', 'interval'),
        ascending = False
    )

    label_data = (
        label_df
        .xs('variable_value', axis = 0, level = 'statistic')
        .loc[plot_data.index, :]
    )

    color_low = '#e1ceff'
    color_high = '#ff6262'
    labels = plot_data.index.tolist()
    central_values = plot_data[('absolute', 'central')].to_numpy()
    lower_values = plot_data[('absolute', 'lower')].to_numpy()
    upper_values = plot_data[('absolute', 'upper')].to_numpy()

    hover_text = []
    for var in labels:
        label_row = label_data.loc[var].dropna()
        label_parts = []
        for key, value in label_row.items():
            try:
                value = float(value)
            except:
                value = value
            if isinstance(key, tuple) and len(key) >= 2:
                if isinstance(value, float):
                    if value > 10:
                        label_parts.append(f"{key[1]}: {value:,.1f}")
                    elif value > 1:
                        label_parts.append(f"{key[1]}: {value:.2f}")
                    else:
                        label_parts.append(f"{key[1]}: {float(f'{value:.3g}')}")
                else:
                    label_parts.append(f"{key[1]}: {value}")
            else:
                if isinstance(value, float):
                    if value > 10:
                        label_parts.append(f"{key}: {value:,.1f}")
                    elif value > 1:
                        label_parts.append(f"{key}: {value:.2f}")
                    else:
                        label_parts.append(f"{key}: {float(f'{value:.3g}')}")
                else:
                    label_parts.append(f"{key}: {value}")
        hover_text.append(
            "<br>".join([f"<b>{var}</b>", *label_parts])
        )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=central_values - lower_values,
            y=labels,
            orientation='h',
            base=lower_values,
            marker=dict(color=color_low),
            name='Lower',
            hovertext=hover_text,
            hovertemplate='%{hovertext}<br>Lower variation: %{x:,.0f}<extra></extra>'
        )
    )
    fig.add_trace(
        go.Bar(
            x=upper_values - central_values,
            y=labels,
            orientation='h',
            base=central_values,
            marker=dict(color=color_high),
            name='Upper',
            hovertext=hover_text,
            hovertemplate='%{hovertext}<br>Upper variation: %{x:,.0f}<extra></extra>'
        )
    )

    fig.add_vline(
        x=central_values[0],
        line_color='black',
        line_width=1,
        annotation_text='Deterministic',
        annotation_position='bottom left'
    )

    fig.update_layout(
        title=title,
        xaxis_title = DSA_ALL_STATISTIC_LABELS.get(statistic, statistic),
        yaxis_title='Variable',
        barmode='overlay',
        template='plotly_white',
        height=800,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    fig.update_yaxes(autorange='reversed')
    #fig.show()

    return fig

def multi_tornado_plot(
    dsa_dfs: Mapping[str, pd.DataFrame],
    statistic: str = 'net_present_value_undiscounted',
    variables: Iterable[str] | None = None,
    label_dfs: Mapping[str, pd.DataFrame] | None = None,
    color_indexes: Mapping[str, int] | None = None,
    title: str = 'Lower and Upper DSA variation by configuration',
):
    """Draw a tornado plot of the results of the DSAs of several comparators, grouped by variable.

    Each comparator has a bar for each variable, from its central value to its values at the lower (hatched) and
    upper bounds, and a marker at its central value. The variables are sorted by the largest interval of any
    comparator.

    Args:
        dsa_dfs: DSA tables, indexed by 'variable' and 'statistic', by the label of the comparator.
        statistic: The statistic to plot.
        variables: Labels of the variables to plot; None plots all.
        label_dfs: Tables of the labels of the variables (the values at the bounds), by the label of the comparator.
        color_indexes: Index of the color of each comparator in `COMPARATOR_COLORS`, so that a comparator keeps its
            color whatever the selection; by default the order of `dsa_dfs`.
        title: Title of the plot.

    Returns:
        The figure.
    """
    frames = {k: _dsa_plot_data(v, statistic, variables) for k, v in dsa_dfs.items()}
    frames = {k: v for k, v in frames.items() if len(v)}
    if not frames:
        return _empty_dsa_figure()

    order = _sorted_dsa_variables(frames.values())
    label_dfs = label_dfs or {}
    color_indexes = color_indexes or {k: i for i, k in enumerate(dsa_dfs)}

    fig = go.Figure()
    for comparator, plot_data in frames.items():
        color = COMPARATOR_COLORS[color_indexes.get(comparator, 0) % len(COMPARATOR_COLORS)]
        plot_data = plot_data.reindex(order)
        central = plot_data[('absolute', 'central')].to_numpy(dtype = float)
        lower = plot_data[('absolute', 'lower')].to_numpy(dtype = float)
        upper = plot_data[('absolute', 'upper')].to_numpy(dtype = float)

        values = {}
        label_df = label_dfs.get(comparator)
        if label_df is not None:
            try:
                values = (
                    label_df
                    .xs('variable_value', axis = 0, level = 'statistic')
                    .xs('absolute', axis = 1, level = 0)
                    .reindex(order)
                )
            except KeyError:
                values = {}

        def hover(bound):
            texts = []
            for var in order:
                parts = [f'<b>{var}</b>', comparator]
                if len(values) and bound in values.columns and pd.notna(values.loc[var, bound]):
                    parts.append(f'{bound.capitalize()} value: {values.loc[var, bound]}')
                texts.append('<br>'.join(parts))
            return texts

        for bound, bound_values, pattern in (('lower', lower, '/'), ('upper', upper, '')):
            fig.add_trace(
                go.Bar(
                    x = bound_values - central,
                    y = order,
                    base = central,
                    orientation = 'h',
                    offsetgroup = comparator,
                    legendgroup = comparator,
                    name = f'{comparator} - {bound}',
                    marker = dict(
                        color = color,
                        opacity = 0.55 if bound == 'lower' else 0.9,
                        pattern = dict(shape = pattern, fgcolor = 'white', solidity = 0.3),
                        line = dict(color = 'white', width = 1),
                    ),
                    hovertext = hover(bound),
                    hovertemplate = '%{hovertext}<br>' + bound.capitalize() + ' result: %{x:,.2f} from central<extra></extra>',
                )
            )

    fig.update_layout(
        title = title,
        xaxis_title = DSA_ALL_STATISTIC_LABELS.get(statistic, statistic),
        yaxis_title = 'Variable',
        barmode = 'group',
        template = 'plotly_white',
        height = max(400, 120 + 40 * len(order) * max(1, len(frames)) // 2),
        margin = dict(l = 20, r = 20, t = 60, b = 20),
        legend = dict(orientation = 'h', yanchor = 'bottom', y = 1.0, xanchor = 'left', x = 0),
    )
    fig.update_yaxes(autorange = 'reversed')

    return fig
