import json

from dash import html, no_update
import pandas as pd

from src.newsegsbrowser import icons
from src.newsegsbrowser.postprocess import postprocess_utils
from src.newsegsbrowser.postprocess.tables import result_tables_sprake

def update_generation_results_header(
    res_trigger, 
    ann_hori_toggle, 
    selected_config,
    app
):
    NUP = no_update
    
    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']
    res_id = postprocess_utils.get_model_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['generation'],
            model_id
    )
    res = app.results.get(res_id)
    if res is None:
        return NUP

    gm = res.get('generator_meter_summary')
    
    if ann_hori_toggle:
        str_1 = 'Total generation: '
        wind_ann = gm.get('wind_export').get('sum')
        pv_ann = gm.get('solar_export').get('sum')
        total_ann = wind_ann + pv_ann
    else:
        str_1 = 'Annual generation: '
        wind_ann = gm.get('wind_export').get('mean')
        pv_ann = gm.get('solar_export').get('mean')
        total_ann = wind_ann + pv_ann
    
    return [
        str_1,
        icons.get_icon('generation'),
        " = ",
        html.Span(f'{total_ann:,.1f}'),
        " kWh; ",
        icons.get_icon('gen-wind'),
        " = ",
        html.Span(f'{wind_ann:,.1f}'),
        " kWh; ",
        icons.get_icon('gen-pv'),
        " = ",
        html.Span(f'{pv_ann:,.1f}'),
        " kWh"
    ]

def update_storage_results_header(
    res_trigger, 
    ann_hori_toggle,
    selected_config,
    app
):
    NUP = no_update

    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']
    res_id = postprocess_utils.get_model_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['storage'],
            model_id
    )
    res = app.results.get(res_id)
    if res is None:
        return NUP

    hrs_full = res.get('stor_hours_at_max').get('hrs_at_max_soc')
    hrs_empty = res.get('stor_hours_at_min').get('hrs_at_min_soc')
    cc = res.get('no_charge_cycles').get('charge_cycles')
    
    if ann_hori_toggle:
        stat='sum'
    else:
        stat='mean'
    
    hrs_full = hrs_full.get(stat)
    hrs_empty = hrs_empty.get(stat)
    cc = cc.get(stat)

    return [
        'Hours full = ',
        html.Span(f'{hrs_full:,.0f}'),
        "; Hours empty = ",
        html.Span(f'{hrs_empty:,.0f}'),
        "; Charge cycles = ",
        html.Span(f'{cc:,.0f}')
    ]

def update_consumption_results_header(
    res_trigger, 
    ann_hori_toggle, 
    selected_config,
    app
):
    NUP = no_update
    
    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']
    res_id = postprocess_utils.get_model_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['consumption'],
            model_id
    )
    res = app.results.get(res_id)
    if res is None:
        return NUP
    
    if ann_hori_toggle:
        str_1 = 'Total consumption: '
        stat='sum'
    else:
        str_1 = 'Annual consumption: '
        stat='mean'
    residential_cons = res.get('consumption_meter_summaries').get('residential').get(stat)
    ev_cons = res.get('consumption_meter_summaries').get('evcharge_import').get(stat)

    return [
        str_1,
        icons.get_icon('consumption-building'),
        ' = ',
        html.Span(f'{residential_cons:,.1f}'),
        ' kWh; ',
        icons.get_icon('consumption-direct-ev'),
        ' = ',
        html.Span(f'{ev_cons:,.1f}'),
        ' kWh'                
    ]

def update_net_results_header(
    res_trigger,
    ann_hori_toggle,
    selected_config,
    app
):
    NUP = no_update
    
    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']
    res_id = postprocess_utils.get_model_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['net_energy'],
            model_id
    )
    res = app.results.get(res_id)
    if res is None:
        return NUP

    if ann_hori_toggle:
        str_1 = 'Total export = '
        str_2 = 'Total import = '
        stat = 'sum'
    else:
        str_1 = 'Annual export = '
        str_2 = 'Annual import = '
        stat = 'mean'
    
    ms = (
        pd.DataFrame
        .from_dict(res['meter_summaries'], orient='columns')
        .set_index(['variable', 'statistic'])
    )
    energy_export = ms.loc[('grid_export',stat),'value']
    energy_import = ms.loc[('grid_import',stat),'value']
    storage_loss = ms.loc[('storage_loss',stat),'value']

    return [
        str_1,
        html.Span(f'{energy_export:,.1f}'),
        ' kWh; ',
        str_2,
        html.Span(f'{energy_import:,.1f}'),
        ' kWh; Storage losses = ',
        html.Span(f'{storage_loss:,.1f}'),
        ' kWh'
    ]

def update_finance_results_header(
    res_benefits_trigger,
    res_costs_trigger,
    res_value_trigger,
    ann_hori_toggle,
    selected_config,
    app
):
    NUP = no_update

    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']
    finance_id = selected_config['finance_id']

    res_benefits = app.results.get(
        postprocess_utils.get_finance_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['finance_benefits_so'], 
            finance_id, 
            model_id
        )
    )
    if not res_benefits:
        return NUP
    
    res_costs = app.results.get(
        postprocess_utils.get_finance_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['finance_costs_so'],
            finance_id,
            model_id
        )
    )
    if not res_costs:
        return NUP
    
    res_value = app.results.get(
        postprocess_utils.get_finance_result_id(
            postprocess_utils.RESULT_CACHE_PREFIXES['finance_value_so'],
            finance_id,
            model_id
        )
    )
    if not res_value:
        return NUP
    
    dr_benefits = res_benefits.get('benefits_discount_rate')
    prval_benefits = res_benefits.get('present_benefits_discounted')
    dr_costs = res_costs.get('costs_discount_rate')
    prval_costs = res_costs.get('present_costs_discounted')
    value = (
        pd.DataFrame
        .from_dict(res_value.get('value_summaries'), orient='columns')
        .set_index(['variable', 'statistic'])
    )
    npv = value.loc[('net_present_value_discounted','sum'),'value']

    return [
        'Total benefits (',
        html.Span(f'{dr_benefits:,.1%}'),
        ') = ',
        html.Span(f'£{prval_benefits:,.2f}'),
        '; Total costs (',
        html.Span(f'{dr_costs:,.1%}'),
        ') = ',
        html.Span(f'£{prval_costs:,.2f}'),
        '; NPV = ',
        html.Span(f'£{npv:,.2f}'),
    ]

def sync_gen_results_table_to_store(
    res_trigger,
    ann_hori_toggle,
    table_ids,
    store_configurations,
    app
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['generation'], 
        store_configurations,
        app
    )

    wind_results = result_tables_sprake.create_wind_results(res, not(ann_hori_toggle))
    pv_results = result_tables_sprake.create_pv_results(res, not(ann_hori_toggle))
    combined_generation_results = result_tables_sprake.create_combined_generation_results(res, not(ann_hori_toggle))

    rval = [no_update] * len(table_ids)

    for i, id in enumerate(table_ids):
        match id['key']:
            case 'wind':
                rval[i] = wind_results # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'pv':
                rval[i] = pv_results # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'combined_generation':
                rval[i] = combined_generation_results # pyright: ignore[reportArgumentType, reportCallIssue]
    return rval

def sync_stor_results_table_to_store(
    res_trigger,
    ann_hori_toggle,
    table_ids,
    store_configurations,
    app
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['storage'],
        store_configurations,
        app
    )

    stor_results = result_tables_sprake.create_stor_results(res, not(ann_hori_toggle))

    rval = [no_update] * len(table_ids)

    for i, id in enumerate(table_ids):
        match id['key']:
            case 'storage':
                rval[i] = stor_results # pyright: ignore[reportArgumentType, reportCallIssue]
            
    return rval

def sync_cons_results_table_to_store(
    res_trigger,
    ann_hori_toggle,
    table_ids,
    store_configurations,
    app
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['consumption'],
        store_configurations,
        app
    )

    cons_results = result_tables_sprake.create_cons_results(res, not(ann_hori_toggle))
    seasonal_cons_results = result_tables_sprake.create_seasonal_cons_results(res, not(ann_hori_toggle))

    rval = [no_update] * len(table_ids)

    for i, id in enumerate(table_ids):
        match id['key']:
            case 'consumption':
                rval[i] = cons_results # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'seasonal_consumption':
                rval[i] = seasonal_cons_results # pyright: ignore[reportArgumentType, reportCallIssue]
    return rval

def sync_net_results_table_to_store(
    res_trigger,
    ann_hori_toggle,
    table_ids,
    store_configurations,
    app
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['net_energy'],
        store_configurations,
        app
    )

    net_results = result_tables_sprake.create_net_results(res, not(ann_hori_toggle))
    seasonal_net_results = result_tables_sprake.create_seasonal_net_results(res, not(ann_hori_toggle))

    rval = [no_update] * len(table_ids)

    for i, id in enumerate(table_ids):
        match id['key']:
            case 'net_energy':
                rval[i] = net_results # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'seasonal_net_energy':
                rval[i] = seasonal_net_results # pyright: ignore[reportArgumentType, reportCallIssue]
    return rval

def sync_fnc_so_table_to_store(
    res_trigger,
    ann_hori_toggle,
    table_ids,
    store_configurations,
    app
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    benefits = postprocess_utils.get_finance_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['finance_benefits_so'],
        store_configurations,
        app
    )
    costs = postprocess_utils.get_finance_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['finance_costs_so'],
        store_configurations,
        app
    )
    value = postprocess_utils.get_finance_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['finance_value_so'],
        store_configurations,
        app
    )

    benefits_results = result_tables_sprake.create_so_benefits_results(benefits, not(ann_hori_toggle))
    costs_results = result_tables_sprake.create_so_costs_results(costs, not(ann_hori_toggle))
    value_results = result_tables_sprake.create_so_value_results(value, not(ann_hori_toggle))

    rval = [no_update] * len(table_ids)

    for i, id in enumerate(table_ids):
        match id['key']:
            case 'so_benefits':
                rval[i] = benefits_results # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'so_costs':
                rval[i] = costs_results # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'so_value':
                rval[i] = value_results # pyright: ignore[reportArgumentType, reportCallIssue]
    return rval
