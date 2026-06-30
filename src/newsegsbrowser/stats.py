import copy
from typing import List
from collections.abc import Callable, Mapping, Iterable

from dash import html
from functools import reduce, partial

import pandas as pd
import plotly.graph_objects as go

from core.timespan import SEASON_NAMES
from newsegssensitivity import common as sensitivity

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
    return f'{val:,.0f} ({prop:0.1%})'

def format_twoval(
    val1,
    val2
):
    return f'{val1:,.0f} | {val2:,.0f}'

def format_val_and_proportion_with_range(
    mean_val,
    min_val,
    max_val,
    mean_prop,
    min_prop,
    max_prop
):
    return f'{mean_val:,.0f} ({min_val:,.0f}, {max_val:,.0f}) - {mean_prop:,.1%} ({min_prop:,.1%}, {max_prop:,.1%})'

def annual_selfconsumption_format(rw):
    return format_val_and_proportion_with_range(
        rw[('self_consumption', 'mean')],
        rw[('self_consumption', 'min')],
        rw[('self_consumption', 'max')],
        rw[('prop_gen_self_consumption', 'mean')],
        rw[('prop_gen_self_consumption', 'min')],
        rw[('prop_gen_self_consumption', 'max')]
        )

def annual_selfconsumption_format_single(rw, stat='mean'):
    return format_val_and_proportion(
        rw[('self_consumption', stat)].iloc[0],
        rw[('prop_gen_self_consumption', stat)].iloc[0]
        )

def annual_consumption_format_single(rw):
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
    return str(stat_dict)

def recursive_get(d, *keys):
    return reduce(lambda c, k: c.get(k, {}), keys, d)

def hours_in_range_formatter(d):
    if d is None:
        return "( -  kW) - (%)"
    return f"({d.get('min_power'):,.0f} - {d.get('max_power'):,.0f}) {d.get('hours'):,.1f} ({d.get('horizon_fraction'):,.1%})"

def days_in_range_formatter(d):
    if d is None:
        return "( - kWh) - (%)"
    return f"({d.get('min_value'):,.0f} - {d.get('max_value'):,.0f}) {d.get('days'):,.0f} ({d.get('horizon_fraction'):,.1%})"

def val_percent_formatter_factory(value_id, fraction_id, value_dp=0, fraction_dp=1):
    fmt = "{:,." + str(value_dp) + "f} ({:,." + str(fraction_dp) + "%})"
    def val_percent_formatter(d):
        if d is None:
            return "- (-%)"
        return fmt.format(d.get(value_id),d.get(fraction_id))
    return val_percent_formatter

def recursive_val_percent_formatter_factory(value_id, fraction_id, value_dp=0, fraction_dp=1):
    fmt = "{:,." + str(value_dp) + "f} ({:,." + str(fraction_dp) + "%})"
    def val_percent_formatter(d):
        if d is None:
            return "- (-%)"
        return fmt.format(recursive_get(d, *value_id), recursive_get(d, *fraction_id))
    return val_percent_formatter

def present_single_stat(data_list,
                        stat_name,
                        stat_label,
                        stat_value='mean',
                        fmt='{:.2f}',
                        none_str='-'):
    n_configs = len(data_list)

    if isinstance(stat_name, str):
        comp_result = [x.get(stat_name, None) for x in data_list]
    else:
        comp_result = [recursive_get(x, stat_name) for x in data_list]
        
    vals = [x.get(stat_value, None) if x is not None else None for x in comp_result]
    
    rw = [html.Td(stat_label, colSpan=2)] \
        + [html.Td(fmt.format(x)) if x is not None else html.Td(none_str) for x in vals]

    return [html.Tr(rw)]

def as_df(
    df: None|pd.DataFrame|dict,
    orient: str = 'columns',
    index_variables: list = ['variable', 'statistic']
) -> pd.DataFrame | None:
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
    
    src_data = [x.get(value_name) for x in data_list]

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
    src_data_1 = [x.get(value1_name) for x in data_list]
    src_data_2 = [x.get(value2_name) for x in data_list]
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
    n_configs = len(data_list)

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
            .rename(columns = {'value': 'config-'+str(idx+1)})
        )
        return subtable
    
    otbl = pd.concat([extract_from_table(i) for i in range(n_configs)], axis=1)

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
    n_configs = len(data_list)

    src_data1 = [as_df(x.get(table1_name), index_variables=['variable', 'season_index', 'statistic']) for x in data_list]
    src_data2 = [as_df(x.get(table2_name), index_variables=['variable', 'season_index', 'statistic']) for x in data_list]

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
            .rename(columns = {'value': 'config-'+str(idx+1)})
        )
        return subtable
    
    otbl = pd.concat([extract_from_table(i) for i in range(n_configs)], axis=1)

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
    n_configs = len(data_list)

    src_data = [as_df(x.get(table_name)) for x in data_list]
    scalar_data_1 = [x.get(scalar_value1_name) for x in data_list]
    scalar_data_2 = [x.get(scalar_value2_name) for x in data_list]

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
            .rename(columns = {'value': 'config-'+str(idx+1)})
        )
        return subtable
    
    otbl = pd.concat([extract_from_table(i) for i in range(n_configs)], axis=1)

    variable_labels = _label_demap(variable_names, variable_mapper)
    statistic_labels = _label_demap(statistic_names, statistic_mapper)
    
    label_mi = pd.MultiIndex.from_product(
        [variable_labels, statistic_labels], 
        names=['variable','statistic']
    )

    otbl.index = label_mi
    
    return otbl
    
def present_stat_description(
        data_list,
        stat_name,
        stat_label,
        stat_list=ANNUAL_DEFAULT_STATS,
        fmt='{:,.2f}',
        none_str='-'
    ):
    n_rows = len(stat_list)
    n_configs = len(data_list)

    # Make a list of the dictionaries of computational results for this stat,
    # e.g. if stat_name is annual_production,
    # then comp_result may consist of dicts of {'mean': xxx, 'min': yyy, 'max': zzz}
    if isinstance(stat_name, str):
        comp_result = [x.get(stat_name, None) for x in data_list]
    else:
        comp_result = [recursive_get(x, *stat_name) for x in data_list]

    def get_Tr(idx):
        stat = stat_list[idx]
        if (idx == 0):
            rw = [html.Td(stat_label, rowSpan=n_rows)]
        else:
            rw = []
        rw = rw + [html.Td(stat['label'])]
        val_fmt = stat.get('fmt', None)
        if val_fmt is None:
            val_fmt = fmt
        
        val_lookup = stat.get('value')
        
        vals = [x.get(val_lookup, None) if x is not None else None for x in comp_result]
        
        rw = rw + [html.Td(val_fmt.format(x)) if x is not None else html.Td(none_str) for x in vals]
        return html.Tr(rw)

    rws = [get_Tr(i) for i in range(n_rows)]
    return rws

def present_stat_description_parallel(
    data_list,
    container_name,
    stat_label,
    stat1_name,
    stat2_name,
    stat_list = ANNUAL_DEFAULT_STATS,
    fmt1='{:,.0f}',
    fmt2='{:,.1%}',
    none_str='-'
):
    n_rows = len(stat_list)
    n_configs = len(data_list)

    if isinstance(container_name, str):
        config_containers = [x.get(container_name, None) for x in data_list]
    else:
        config_containers = [recursive_get(x, *container_name) for x in data_list]
    
    def get_Tr(idx):
        stat = stat_list[idx]
        if (idx == 0):
            rw = [html.Td(stat_label, rowSpan=n_rows)]
        else:
            rw = []
        rw = rw + [html.Td(stat['label'])]

        val_lookup = stat.get('value')
        
        vals_1 = [x.get(stat1_name,{}).get(val_lookup) if x is not None else None for x in config_containers]
        vals_2 = [x.get(stat2_name,{}).get(val_lookup) if x is not None else None for x in config_containers]

        rw = rw + [html.Td(fmt1.format(x)+' ('+fmt2.format(y)+")") if x is not None else html.Td(none_str) for x, y in zip(vals_1, vals_2)]
        return html.Tr(rw)
    
    rws = [get_Tr(i) for i in range(n_rows)]
    return rws

def present_stat_description_compound(data_list,
                                      stat_name,
                                      stat_label,
                                      stat_formatter=DEFAULT_STAT_FORMATTER,
                                      stat_list=DEFAULT_HOURS_IN_RANGE_STATS):
    # Extension to present_stat_description to allow for complex compound formatting of table values
    n_rows = len(stat_list)
    n_configs = len(data_list)

    # Grab the computed results for the desired stat
    if isinstance(stat_name, str):
        comp_result = [x.get(stat_name, None) for x in data_list]
    else:
        comp_result = [recursive_get(x, *stat_name) for x in data_list]

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

    trans_stats = [{str(stat_name): transform_stats(x)} for x in comp_result]

    return present_stat_description(trans_stats, str(stat_name), stat_label, stat_list, fmt="{}")

def present_self_consumption_data(data_list,
                                  table_name,
                                  stat_label,
                                  stat_list=ANNUAL_SC_STATS,
                                  index_filter='generation_export'):
    """
    Process a list of generation data to extract self-consumption into a table


    """
    n_rows = len(stat_list)
    n_configs = len(data_list)

    # Get the list of tight dictionary representations of dataframes
    if isinstance(table_name, str):
        dict_data = [x.get(table_name, None) for x in data_list]
    else:
        dict_data = [recursive_get(x, *table_name) for x in data_list]

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

    stat_list = copy.copy(stat_list)
    for i in range(len(stat_list)):
        stat_list[i]['value'] = stat_list[i]['label']

    return present_stat_description(trans_stats, str(table_name), stat_label, stat_list, fmt="{}")

def present_seasonal_consumption_data(
    data_list,
    table_name,
    stat_label,
    stat_list=ANNUAL_CONS_STATS
):
    """
    Process a list of seasonal consumption data into a table
    """
    n_rows = len(stat_list)
    n_configs = len(data_list)

    # Get the list of tight dictionary representations of dataframes
    if isinstance(table_name, str):
        dict_data = [x.get(table_name, None) for x in data_list]
    else:
        dict_data = [recursive_get(x, *table_name) for x in data_list]

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

    stat_list = copy.copy(stat_list)
    for i in range(len(stat_list)):
        stat_list[i]['value'] = stat_list[i]['label']

    return present_stat_description(trans_stats, str(table_name), stat_label, stat_list, fmt="{}")        

def present_event_and_date(data_list,
                           event_name,
                           event_label,
                           event_value,
                           event_value_formatter,
                           date_label='On:',
                           event_date='datetime',
                           none_str='-',
                           nonedate_str='#/#/#',
                           trimdate=15):
    n_configs = len(data_list)

    if isinstance(event_name, str):
        comp_result = [x.get(event_name, None) for x in data_list]
    else:
        comp_result = [recursive_get(x, event_name) for x in data_list]

    val_row = html.Tr([html.Td(event_label,rowSpan=2), html.Td()] +
        [html.Td(event_value_formatter(x.get(event_value))) if x is not None else html.Td(none_str) for x in comp_result])

    date_row = html.Tr(
        [html.Td(date_label, style={'text-align':'end'})] 
        + [
            html.Td(
                html.A(
                    f'{x.get(event_date)[:-trimdate]}',
                    disable_n_clicks = False,
                    id = {
                        'type': 'link-event-date',
                        'date': x.get(event_date)[:-trimdate]
                    },
                    style = {
                        'cursor': 'zoom-in'
                    }
                )
            ) if x is not None else html.Td(none_str) for x in comp_result
        ]
    )

    return [val_row, date_row]    

def present_event_and_daterange(data_list,
                                event_name,
                                event_label,
                                event_value,
                                event_value_formatter,
                                range_label='From - To',
                                event_start='datetime_start',
                                event_end='datetime_end',
                                none_str='-',
                                nonedate_str='#/#/# - #/#/#',
                                trimdate = 9):
    #n_rows = 2
    n_configs = len(data_list)

    if isinstance(event_name, str):
        comp_result = [x.get(event_name, None) for x in data_list]
    else:
        comp_result = [recursive_get(x, event_name) for x in data_list]

    val_row = html.Tr([html.Td(event_label,rowSpan=2), html.Td()] + 
        [html.Td(event_value_formatter(x.get(event_value))) if x is not None else html.Td(none_str) for x in comp_result])

    date_row = html.Tr(
        [html.Td(range_label, style={'text-align':'end'})] 
        + [
            html.Td(
                html.A(
                    f'{x.get(event_start)[:-trimdate]} - {x.get(event_end)[:-trimdate]}',
                    disable_n_clicks = False,
                    id = {
                        'type': 'link-event-daterange',
                        'datetime_start': x.get(event_start)[:-trimdate],
                        'datetime_end': x.get(event_end)[:-trimdate],
                    },
                    style = {
                        'cursor': 'zoom-in'
                    }
                )
            ) if x is not None else html.Td(nonedate_str) for x in comp_result
        ]
    )

    return [val_row, date_row]

def tornado_plot(
    dsa_df,
    label_df,
    statistic = 'net_present_value_undiscounted'
):
    plot_data = (
        dsa_df
        .xs(statistic, axis = 0, level = 'statistic')
        .sort_values(
            ('absolute', 'interval'),
            ascending = False
        )
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
        title='Lower and Upper DSA variation',
        xaxis_title = sensitivity.DSA_STATISTIC_LABELS.get(statistic, statistic),
        yaxis_title='Variable',
        barmode='overlay',
        template='plotly_white',
        height=800,
        margin=dict(l=20, r=20, t=60, b=20)
    )
    fig.update_yaxes(autorange='reversed')
    #fig.show()

    return fig
