import json
from typing import Any

from dash import dcc, html, no_update, ctx
import pandas as pd
import dash_ag_grid as dag

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser import stats as browserstats
from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager
from newsegsmodelapp.newsegsbrowser.postprocess import postprocess_utils
from newsegsmodelapp.newsegsbrowser.postprocess.tables import result_tables_sprake
from newsegsmodelframework.newsegssensitivity import common as sensitivity
from newsegsmodelframework.newsegssensitivity import psa


def _make_generation_result_header(
    res,
    ann_hori_toggle: bool,
):
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

def _make_storage_result_header(
    res,
    ann_hori_toggle: bool,
):
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

def _make_consumption_result_header(
    res,
    ann_hori_toggle: bool,
):
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

def _make_net_result_header(
    res,
    ann_hori_toggle: bool,
):
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

_MODEL_RESULT_HEADER_MAP = {
    'generation': _make_generation_result_header,
    'storage': _make_storage_result_header,
    'consumption': _make_consumption_result_header,
    'net_energy': _make_net_result_header,
}

def _make_model_result_header(
    result_type,
    model_id,
    ann_hori_toggle: bool,
    acm: NewsegsBrowserCacheManager
):
    res_id = postprocess_utils.get_model_result_id(
        postprocess_utils.RESULT_CACHE_PREFIXES[result_type],
        model_id
    )
    res = acm.results.get(res_id)
    if res is None:
        return None
    return _MODEL_RESULT_HEADER_MAP[result_type](res, ann_hori_toggle)

def update_model_result_headers(
    res_trigger,
    ann_hori_toggle: bool,
    selected_config,
    result_trigger_ids,
    result_header_ids,
    acm: NewsegsBrowserCacheManager
):
    NUP = [no_update] * len(result_header_ids)

    rval: list[Any] = NUP

    if ctx.triggered_id == 'annual-horizon-toggle':
        update_triggers = result_trigger_ids
    else:
        update_triggers = [v for v in ctx.triggered_prop_ids.values()]
    
    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']

    for i, header_id in enumerate(result_header_ids):
        hdr = None
        match header_id['key']:
            case 'gen-ressmry':
                if any(x['key'] == 'res-gen' for x in update_triggers):
                    hdr = _make_model_result_header(
                        'generation', model_id, ann_hori_toggle, acm
                    )        
            case 'stor-ressmry':
                if any(x['key'] == 'res-stor' for x in update_triggers):
                    hdr = _make_model_result_header(
                        'storage', model_id, ann_hori_toggle, acm
                    )
            case 'cons-ressmry':
                if any(x['key'] == 'res-cons' for x in update_triggers):
                    hdr = _make_model_result_header(
                        'consumption', model_id, ann_hori_toggle, acm
                    )
            case 'net-ressmry':
                if any(x['key'] == 'res-net' for x in update_triggers):
                    hdr = _make_model_result_header(
                        'net_energy', model_id, ann_hori_toggle, acm
                    )
        if hdr:
            rval[i] = hdr
    return rval

def _make_finance_result_header(
    res_benefits,
    res_costs,
    res_value,
    ann_hori_toggle
):
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

def update_finance_result_headers(
    res_trigger,
    ann_hori_toggle: bool,
    selected_config,
    result_trigger_ids,
    result_header_ids,
    acm: NewsegsBrowserCacheManager
):
    NUP = [no_update] * len(result_header_ids)

    rval: list[Any] = NUP

    if ctx.triggered_id == 'annual-horizon-toggle':
        update_triggers = result_trigger_ids
    else:
        update_triggers = [v for v in ctx.triggered_prop_ids.values()]

    selected_config = json.loads(selected_config)
    model_id = selected_config['model_id']
    finance_id = selected_config['finance_id']

    for i, header_id in enumerate(result_header_ids):
        hdr = None
        match header_id['key']:
            case 'finance-ressmry':
                if any(x['key'] in (
                    'res-finance-so-benefits',
                    'res-finance-so-costs',
                    'res-finance-so-value'
                ) for x in update_triggers):
                    res_benefits = acm.results.get(
                        postprocess_utils.get_finance_result_id(
                            postprocess_utils.RESULT_CACHE_PREFIXES['finance_benefits_so'], 
                            finance_id, 
                            model_id
                        )
                    )
                    if not res_benefits:
                        continue
                    
                    res_costs = acm.results.get(
                        postprocess_utils.get_finance_result_id(
                            postprocess_utils.RESULT_CACHE_PREFIXES['finance_costs_so'],
                            finance_id,
                            model_id
                        )
                    )
                    if not res_costs:
                        continue
                    
                    res_value = acm.results.get(
                        postprocess_utils.get_finance_result_id(
                            postprocess_utils.RESULT_CACHE_PREFIXES['finance_value_so'],
                            finance_id,
                            model_id
                        )
                    )
                    if not res_value:
                        continue

                    hdr = _make_finance_result_header(
                        res_benefits, res_costs, res_value,
                        ann_hori_toggle
                    )
        if hdr:
            rval[i] = hdr

    return rval

def sync_gen_results_table_to_store(
    res_trigger,
    ann_hori_toggle,
    table_ids,
    store_configurations,
    acm: NewsegsBrowserCacheManager
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP

    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['generation'], 
        store_configurations,
        acm
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
    acm: NewsegsBrowserCacheManager

):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['storage'],
        store_configurations,
        acm
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
    acm: NewsegsBrowserCacheManager

):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['consumption'],
        store_configurations,
        acm
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
    acm: NewsegsBrowserCacheManager
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    
    res = postprocess_utils.get_model_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['net_energy'],
        store_configurations,
        acm
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
    acm: NewsegsBrowserCacheManager
):
    NUP = [no_update] * len(table_ids)

    if store_configurations is None:
        return NUP
    
    benefits = postprocess_utils.get_finance_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['finance_benefits_so'],
        store_configurations,
        acm
    )
    costs = postprocess_utils.get_finance_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['finance_costs_so'],
        store_configurations,
        acm
    )
    value = postprocess_utils.get_finance_result_list(
        postprocess_utils.RESULT_CACHE_PREFIXES['finance_value_so'],
        store_configurations,
        acm
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

def sync_dsa_results_table_to_store(
    dsa_table_trigger,
    dsa_statistic_dropdown_values,
    table_ids,
    selected_conf,
    acm: NewsegsBrowserCacheManager
):
    if len(table_ids) == 0:
        return
    elif len(table_ids) > 1:
        raise ValueError('There are multiple containers for DSA results tables')
    NUP = [no_update]
    
    if len(dsa_statistic_dropdown_values) > 1:
        raise ValueError('App is receiving DSA statistic dropdown values from more than one page')
    elif len(dsa_statistic_dropdown_values) == 0:
        dsa_statistic = list(sensitivity.DSA_STATISTIC_LABELS.keys())[0]
    else:
        dsa_statistic = dsa_statistic_dropdown_values[0]
    
    if selected_conf is None:
        return NUP
    selected_conf = json.loads(selected_conf)
    
    tbl_id = postprocess_utils.get_dsa_result_id(
        postprocess_utils.RESULT_CACHE_PREFIXES['dsa_table'],
        selected_conf.get('metamodel_id')
    )

    tbl = acm.results.get(tbl_id)
    if tbl is None:
        return NUP

    otable = (
        tbl
        .xs(dsa_statistic, level=1, axis=0)
        .xs('absolute', level = 0, axis = 1)
        .loc[:,['central', 'interval', 'lower', 'upper']]
        .reset_index()
    )
    rval = []
    formatters = {
        'variable': {"function":  "params.value ? params.value : '-' "},
    }
    columnDefs = [
        {
            'field': i,
            "valueFormatter": formatters.get(i, {"function":  "params.value ? d3.format(',.2f')(params.value) : '-' "})
        }
        for i in otable.columns
    ]
    rval.append(
        dag.AgGrid(
            rowData = otable.to_dict('records'),
            columnDefs = columnDefs
        )
    )

    return rval

def sync_dsa_tornado_to_store(
    dsa_table_trigger,
    dsa_statistic_dropdown_values,
    plot_container_ids,
    selected_conf,
    acm: NewsegsBrowserCacheManager
):
    if len(plot_container_ids) == 0:
        return
    elif len(plot_container_ids) > 1:
        raise ValueError('There are multiple containers for DSA tornado diagrams')
    NUP = [no_update]
    
    if len(dsa_statistic_dropdown_values) > 1:
        raise ValueError('App is receiving DSA statistic dropdown values from more than one page')
    elif len(dsa_statistic_dropdown_values) == 0:
        dsa_statistic = list(sensitivity.DSA_STATISTIC_LABELS.keys())[0]
    else:
        dsa_statistic = dsa_statistic_dropdown_values[0]
    
    if selected_conf is None:
        return NUP
    selected_conf = json.loads(selected_conf)
    
    tbl_id = postprocess_utils.get_dsa_result_id(
        postprocess_utils.RESULT_CACHE_PREFIXES['dsa_table'],
        selected_conf.get('metamodel_id')
    )
    tbl = acm.results.get(tbl_id)
    lbl_id = postprocess_utils.get_dsa_result_id(
        postprocess_utils.RESULT_CACHE_PREFIXES['dsa_label'],
        selected_conf.get('metamodel_id')
    )
    lbl = acm.results.get(lbl_id)

    if tbl is None or lbl is None:
        return NUP
    
    plt = browserstats.tornado_plot(tbl, lbl, dsa_statistic)

    return [plt]

def sync_psa_results_table_to_store(
    psa_table_trigger,
    table_ids,
    selected_conf,
    acm: NewsegsBrowserCacheManager
):
    if len(table_ids) == 0:
        return
    elif len(table_ids) > 1:
        raise ValueError('There are multiple containers for PSA results tables')
    NUP = [no_update]

    if selected_conf is None:
        return NUP
    selected_conf = json.loads(selected_conf)

    tbl_id = postprocess_utils.get_psa_result_id(
        postprocess_utils.RESULT_CACHE_PREFIXES['psa_table'],
        selected_conf.get('metamodel_id')
    )

    tbl = acm.results.get(tbl_id)
    if tbl is None:
        return NUP
    
    otable = (
        tbl
        .rename(psa.PSA_STATISTIC_LABELS)
        .reset_index(drop=False)
        .rename(columns={'index':'Statistic'})
    )

    rval = []
    
    formatters = {
        'Statistic': {"function":  "params.value ? params.value : '-' "},
    }
    columnDefs = [
        {
            'field': i,
            "valueFormatter": formatters.get(i, {"function":  "params.value ? d3.format(',.2f')(params.value) : '-' "})
        }
        for i in otable.columns
    ]

    tbl1 = dag.AgGrid(
        rowData = otable.to_dict('records'),
        columnDefs = columnDefs
    )

    rval.append(
        tbl1   
    )

    npv_id = postprocess_utils.get_psa_result_id(
        postprocess_utils.RESULT_CACHE_PREFIXES['psa_prob_positive_npv'],
        selected_conf.get('metamodel_id')
    )
    npv_data = acm.results.get(npv_id)
    if npv_data is None:
        return NUP
    
    pnpv = [
        html.H2('Probability of positive NPV:'),
        html.H3(
            f'Undiscounted: {npv_data.loc['net_present_value_undiscounted','prob_pos_npv']:.1%}'
        ),
        html.H3(
            f'Discounted: {npv_data.loc['net_present_value_discounted','prob_pos_npv']:.1%}'
        ),
    ]
    rval.extend(pnpv)

    return [rval,]

def sync_psa_primary_plot_to_store(
    psa_table,
    graph_selection_dropdown,
    plot_controls,
    plot_header,
    plot,
    plot_container,
    selected_configuration,
    acm: NewsegsBrowserCacheManager,
    null_return,
):
    rval = null_return
    if len(plot_container['ids']) == 0 or len(graph_selection_dropdown['values']) == 0:
        return rval
    
    trig = ctx.triggered_id
    if trig is None:
        return rval
    
    selected_configuration = json.loads(selected_configuration['value'])
    
    psa_data = postprocess_utils.get_psa_raw_data(selected_configuration, acm)
    
    graph_type = None
    full_draw = False
    if trig.get('type') == 'psa-graph-selection-dropdown':
        # Need to do a full graph refresh
        full_draw = True
        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rsplit('.', 1)[0])
            val = prop['value']
            if val is None:
                continue
            
            if pid['type'] == 'psa-graph-selection-dropdown':
                graph_type = val
                break
    
    if graph_type is None:
        graph_type = graph_selection_dropdown['values'][0]
    
    graph_drawn_indicator_key = 'psa-primary-plot-'+graph_type+'-ii'
    if not full_draw:
        graph_is_drawn = False
        for id in plot_controls['ids']:
            if id.get('key') == graph_drawn_indicator_key:
                graph_is_drawn = True
        
         
        full_draw = not graph_is_drawn
    
    plot_funcs = psa.psa_plots.get(graph_type)
    if plot_funcs is None:
        raise ValueError(f'Plot functions not found for graph_type {graph_type}')

    plot_kwargs = plot_funcs['arguments'](plot_controls)

    if full_draw:
        rval['plot_header']['children'] = [
            plot_funcs['controls'](x['page']) for x in plot_header['ids']
        ]
        rval['plot']['figures'] = [plot_funcs['draw'](psa_data, **plot_kwargs)] * len(plot['ids'])

    else:
        rval['plot']['figures'] = [plot_funcs['update'](psa_data, **plot_kwargs)] * len(plot['ids'])

    return rval
