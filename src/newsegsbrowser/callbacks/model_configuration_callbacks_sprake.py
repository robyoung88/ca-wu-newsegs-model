"""

functions:
- sync_config
"""

import json
import logging
from typing import Tuple
from functools import partial

from dash import html, no_update
import pandas as pd
import plotly.express as px

from core import location
from newsegsbrowser import icons
from newsegsbrowser import common as browser
import newsegsbrowser.callbacks.model_configuration_callbacks_generic as generic_callbacks
from newsegsbrowser.callbacks import model_creation_sprake

from newsegsmodel import sprakemodel
from newsegsfinance import sprakefinance
from newsegsbrowser import energy_balance_estimation

logger = logging.getLogger(__name__)

def sprake_model_set_gen_input(gen_input: dict, mdl: sprakemodel.SprakeModel):
    turbine_size = mdl.generation.generator.generators[0].turbine.nameplate_capacity # pyright: ignore[reportAttributeAccessIssue]
    n_turbines = gen_input.get('wind_capacity', 0.0) / turbine_size
    
    pv_size = mdl.generation.generator.generators[1].pv_array.nameplate_capacity # pyright: ignore[reportAttributeAccessIssue]
    n_arrays = gen_input.get('pv_capacity', 0.0) / pv_size

    mdl.generation.generator.generators[0].n_turbines = n_turbines # pyright: ignore[reportAttributeAccessIssue]
    mdl.generation.generator.generators[1].n_arrays = n_arrays # pyright: ignore[reportAttributeAccessIssue]
    
    mdl.generation.dirty = True

def sprake_model_set_stor_input(stor_input: dict, mdl: sprakemodel.SprakeModel):
    mdl.consumption_storage.set_storage_params(stor_input.copy())
    # consumption storage will be dirtied by this method

def sprake_model_set_bc_input(bc_input: dict, mdl: sprakemodel.SprakeModel):
    cs = mdl.consumption_storage
    spaceheat_p = cs.spaceheat_params
    dhw_p = cs.dhw_params

    cs.n_units = bc_input.get('n_units', 1.0)
    spaceheat_p['hlp'] = bc_input.get('hlp', 1.1)
    spaceheat_p['gfa'] = bc_input.get('gfa', 1.0)
    dhw_p['ref_daily_consumption'] = bc_input.get('ref_daily_consumption', 0.0)
    dhw_p['seasonal_variance'] = bc_input.get('seasonal_variance', 0.01)
    cs.dirty = True

def sprake_model_set_dc_input(dc_input: dict, mdl: sprakemodel.SprakeModel):
    cs = mdl.consumption_storage
    app_p = cs.appliance_params
    ev_p = cs.ev_params

    app_p['efficiency_reduction'] = dc_input.get('efficiency_reduction', 0.0)
    ev_p['annual_residential_consumption_per_ev'] = dc_input.get('annual_residential_consumption_per_ev', 0.0)
    ev_p['n_evs'] = dc_input.get('n_evs_per_household', 0.0) * cs.n_units
    cs.dirty = True

def sprake_model_set_mc_input(mc_input: dict, mdl: sprakemodel.SprakeModel):
    ts = mdl.get_run_period()
    ts.end = ts.start + pd.Timedelta(mc_input.get('horizon',1)*365, unit='d') 
    while ts.end.day != ts.start.day:
        ts.end = ts.end + pd.Timedelta(1, unit='d')
    mdl.set_run_period(ts)

def sprake_model_set_loc_input(loc_input: dict, mdl: sprakemodel.SprakeModel):
    loc_0 = mdl.location
    loc = location.Location(
        loc_input.get('lat', loc_0.lat),
        loc_input.get('lon', loc_0.lon),
        name = loc_input.get('name', loc_0.name)
    )
    mdl.location = loc

def sprake_finance_set_finance_config(fcfg: dict, fnc: sprakefinance.SprakeFinance):
    fnc.set_unit_costs_from_dict(fcfg.get('unit_costs', {}))
    fnc.benefit_discount_rate = float(fcfg.get('benefit_discount_rate', 0.0) / 100)
    fnc.cost_discount_rate = float(fcfg.get('cost_discount_rate', 0.0) / 100)

def sprake_model_to_interface_config(
    mdl: sprakemodel.SprakeModel
) -> dict:
    gen_input = {
        'wind_capacity': mdl.generation.generator.generators[0].nameplate_capacity,
        'pv_capacity': mdl.generation.generator.generators[1].nameplate_capacity
    }

    cs = mdl.consumption_storage

    stor_input = cs.storage_params

    spaceheat_p = cs.spaceheat_params
    dhw_p = cs.dhw_params
    app_p = cs.appliance_params
    ev_p = cs.ev_params

    bc_input = {
        'n_units': cs.n_units,
        'hlp': spaceheat_p.get('hlp'),
        'gfa': spaceheat_p.get('gfa'),
        'ref_daily_consumption': dhw_p.get('ref_daily_consumption'),
        'seasonal_variance': dhw_p.get('seasonal_variance')
    }

    dc_input = {
        'efficiency_reduction': app_p.get('efficiency_reduction'),
        'annual_residential_consumption_per_ev': \
            ev_p.get('annual_residential_consumption_per_ev'),
        'n_evs_per_household': ev_p.get('n_evs', 0) / cs.n_units
    }

    # Model config

    # Note that we are only going to allow horizons in multiples
    # of one year. I may allow the start date to vary later.
    # As such, we are just going to take the horizon to be the
    # difference in year between the start and end of the timespan
    ts = mdl.get_run_period()
    mc_input = {
        'horizon': ts.end.year - ts.start.year
    }

    # Location config
    loc = mdl.location
    loc_input = {
        'lat': loc.lat,
        'lon': loc.lon,
        'name': loc.name
    }

    mcfg = {
        'model_uuid': mdl.uuid,
        'gen_input': gen_input,
        'stor_input': stor_input,
        'bc_input': bc_input,
        'dc_input': dc_input,
        'mc_input': mc_input,
        'loc_input': loc_input,
    }

    return mcfg

def sync_interface_config_to_model(
    local_model_config: dict,
    mdl: sprakemodel.SprakeModel,
) -> bool:
    """
    Pass a local model configuration dictionary into a Sprake model.

    Returns a bool indicating whether a configuration has changed.
    """
    # Get the existing model configuration so we only update if we have
    # changes
    mcfg = local_model_config
    w_mcfg = sprake_model_to_interface_config(mdl)

    if (
        mcfg.get('gen_input') is not None
        and w_mcfg.get('gen_input') != mcfg.get('gen_input')
    ):
        sprake_model_set_gen_input(mcfg.get('gen_input', {}), mdl)
    
    if (
        mcfg.get('stor_input') is not None
        and w_mcfg.get('stor_input') != mcfg.get('stor_input')
    ):
        sprake_model_set_stor_input(mcfg.get('stor_input', {}), mdl)

    if (
        mcfg.get('bc_input') is not None
        and w_mcfg.get('bc_input') != mcfg.get('bc_input')
    ):
        sprake_model_set_bc_input(mcfg.get('bc_input', {}), mdl)
    
    if (
        mcfg.get('dc_input') is not None
        and w_mcfg.get('dc_input') != mcfg.get('dc_input')
    ):
        sprake_model_set_dc_input(mcfg.get('dc_input', {}), mdl)
    
    if (
        mcfg.get('mc_input') is not None
        and w_mcfg.get('mc_input') != mcfg.get('mc_input')
    ):
        sprake_model_set_mc_input(mcfg.get('mc_input', {}), mdl)
    
    if (
        mcfg.get('loc_input') is not None
        and w_mcfg.get('loc_input') != mcfg.get('loc_input')
    ):
        sprake_model_set_loc_input(mcfg.get('loc_input', {}), mdl)
    
    return mdl.dirty

def sprake_finance_to_interface_config(
    fnc: sprakefinance.SprakeFinance,
) -> dict:
    fcfg = fnc.to_dict()
    fcfg['benefit_discount_rate'] *= 100.
    fcfg['cost_discount_rate'] *= 100.
    fcfg['finance_uuid'] = fnc.uuid

    return fcfg

def sync_interface_config_to_finance(
    local_finance_config: dict,
    fnc: sprakefinance.SprakeFinance,
) -> bool:
    fcfg = local_finance_config
    w_fcfg = sprake_finance_to_interface_config(fnc)

    if (
        fcfg is not None
        and w_fcfg != fcfg
    ):
        sprake_finance_set_finance_config(fcfg, fnc)
    return fnc.dirty

def sprake_model_finance_to_interface_configs(
    mdl: sprakemodel.SprakeModel, 
    fnc: sprakefinance.SprakeFinance,
) -> Tuple[dict, dict]:

    mcfg = sprake_model_to_interface_config(mdl)

    fcfg = sprake_finance_to_interface_config(fnc)

    return mcfg, fcfg

sync_config = partial(
    generic_callbacks.sync_config,
    create_default_model = model_creation_sprake.create_default_model,
    create_default_finance = model_creation_sprake.create_default_finance,
    create_default_variables = model_creation_sprake.create_default_variables,
    model_and_finance_to_interface_function = sprake_model_finance_to_interface_configs,
)

def sync_dc_inputs_to_store(mcfg, input_values, input_ids, app):
    NUP = (no_update, [no_update] * len(input_values))
    if mcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    conf = mcfg.get('dc_input', {})

    ann_appliance = (
        (1.0 - float(conf.get('efficiency_reduction', 0))) 
        * model_creation_sprake.MODEL_CONSTANTS['sprake_model']['sprake_ref_appliance_consumption_annual']
    )
    ann_ev = (
        conf.get('n_evs_per_household', 0) * conf.get('annual_residential_consumption_per_ev', 0)
    )
    
    header_children = [
        icons.get_icon('consumption-direct-appliance'),
        " = ",
        html.Span('{:,.0f}'.format(ann_appliance)),
        " kWh/yr/household; ",
        icons.get_icon('consumption-direct-ev'),
        " = ",
        html.Span('{:,.0f}'.format(ann_ev)),
        " kWh/yr/household"
    ]

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in conf.keys():
            v = conf[id['key']]
            if input_values[i] != v:
                input_list[i] = v
    
    return (header_children, input_list)

def sync_unit_cost_inputs_to_store(
        mcfg,
        fcfg,
        input_values,
        input_ids,
        app
):
    NUP = (no_update, no_update, no_update, no_update, [no_update] * len(input_values))
    if mcfg is None or fcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    fcfg = json.loads(fcfg)

    uc = fcfg.get('unit_costs', {})
    # Generation
    gen_conf = mcfg.get('gen_input', {})

    wind_cap = gen_conf.get('wind_capacity', 0.0)
    pv_cap = gen_conf.get('pv_capacity', 0.0)
    tot_capex = (
        uc.get('wind_capex_per_kw', 0) * wind_cap
        + uc.get('pv_capex_per_kw', 0) * pv_cap
    )
    tot_ongoing = (
        uc.get('wind_om_per_kw_year', 0) * wind_cap
        + uc.get('pv_om_per_kw_year', 0) * pv_cap
    )
    gen_header = [
            "Capital cost = £",
            html.Span('{:,.0f}'.format(tot_capex)),
            "; Ongoing costs = £",
            html.Span('{:,.0f}'.format(tot_ongoing)),
            "/yr"
        ]
    
    # Storage
    stor_conf = mcfg.get('stor_input', {})
    bess_cap = stor_conf.get('storage_capacity', 0.0)
    tot_capex = bess_cap * uc.get('bess_capex_per_kwh', 0)
    tot_ongoing = bess_cap * uc.get('bess_om_per_kwh_year', 0)
    stor_header = [
        "Capital cost = £",
        html.Span('{:,.0f}'.format(tot_capex)),
        "; Ongoing costs = £",
        html.Span('{:,.0f}'.format(tot_ongoing)),
        "/yr"
    ]

    # Sales
    # TODO: Incorporate the indicative net energy to allow estimation here.
    # For now, leave it.
    sales_header = no_update

    # Import
    # TODO: Incorporate indicative net energy
    # For now, leave.
    import_header = no_update

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in uc.keys():
            input_list[i] = uc[id['key']]
    
    return (gen_header, stor_header, sales_header, import_header, input_list)

def sync_mc_inputs_to_store(mcfg, input_values, input_ids, app):
    NUP = (no_update, [no_update] * len(input_values))
    if mcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    conf = mcfg.get('mc_input', {})
    
    header_children = [
                icons.get_icon('model-settings-time-horizon'),
                " = ",
                html.Span(f"{conf.get('horizon', 1):.0f}"),
                " years"
            ]

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in conf.keys():
            v = conf[id['key']]
            if input_values[i] != v:
                input_list[i] = v
    
    return (header_children, input_list)

def _sync_estimated_energy_balance(
    mcfg: dict,
    energy_balance: energy_balance_estimation.EstimatedEnergyBalance
) -> energy_balance_estimation.EstimatedEnergyBalance:
    """
    Set up the energy balance according to Sprake assumptions and config.
    """
    energy_balance.set_wind_generation(mcfg['gen_input']['wind_capacity'])
    energy_balance.set_pv_generation(mcfg['gen_input']['pv_capacity'])
    energy_balance.set_spaceheat_consumption(mcfg['bc_input']['n_units'], mcfg['bc_input']['hlp'], mcfg['bc_input']['gfa'])
    energy_balance.set_dhw_consumption(mcfg['bc_input']['n_units'], mcfg['bc_input']['ref_daily_consumption'])
    energy_balance.set_direct_consumption(
        mcfg['bc_input']['n_units'], 
        (
            (1. - mcfg['dc_input'].get('efficiency_reduction', 0))
            * model_creation_sprake.MODEL_CONSTANTS['sprake_model']['sprake_ref_appliance_consumption_annual']
        )
    )
    energy_balance.set_ev_consumption(
        mcfg['bc_input']['n_units'],
        mcfg['dc_input']['annual_residential_consumption_per_ev'],
        mcfg['dc_input']['n_evs_per_household'],
    )
    energy_balance.set_storage_capacity(
        mcfg['stor_input']['storage_capacity']
    )

    return energy_balance

_feedback_graph_bar = partial(
    px.bar,
    x = 'value',
    color = 'label',
    orientation = 'h'
)

_feedback_graph_layout = dict(
    height=120,
    margin={'l': 0, 'r': 0, 't': 28, 'b': 0},
    title={
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 12, 'family': 'Arial', 'color': '#212529', 'weight': 'bold'}
    },
    showlegend=False,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    bargap=0.75
)

def update_feedback_graphs(
    mcfg,
    figure_ids,
    app
):
    NUP = [no_update] * len(figure_ids)
    if mcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    eb = _sync_estimated_energy_balance(mcfg, app.estimated_energy_balance)
    df = eb.estimated_annual_energy_balance

    fig_ann = _feedback_graph_bar(df, y = 'type')
    fig_ann.update_layout(**_feedback_graph_layout) # pyright: ignore[reportArgumentType]
    fig_ann.update_layout(title = {'text': 'Annual'})
    fig_ann.update_traces(width=0.35, marker_line_width=0)
    fig_ann.update_xaxes(showticklabels=False, title_text=None, showgrid=False, zeroline=False)
    fig_ann.update_yaxes(showticklabels=True, title_text=None, showgrid=False, zeroline=False)

    df = eb.estimated_maximum_daily_balance
    fig_max = _feedback_graph_bar(df, y = 'label')
    fig_max.update_layout(**_feedback_graph_layout) # pyright: ignore[reportArgumentType]
    fig_max.update_layout(title = {'text': '(Max) Daily'})
    fig_max.update_traces(width=0.35, marker_line_width=0)
    fig_max.update_xaxes(showticklabels=False, title_text=None, showgrid=False, zeroline=False)
    fig_max.update_yaxes(showticklabels=True, title_text=None, showgrid=False, zeroline=False)

    rval = NUP
    for i, id in enumerate(figure_ids):
        match id['key']:
            case 'estimated-annual-energy':
                rval[i] = fig_ann  # pyright: ignore[reportArgumentType, reportCallIssue]
            case 'estimated-maximum-daily-energy':
                rval[i] = fig_max # pyright: ignore[reportArgumentType, reportCallIssue]
    
    return rval

def dispatcher_action_user(
    dispatchitem_action_user,
    store_model_interface_configurations,
    store_finance_interface_configurations,
    store_selected_configuration,
    app
):
    NUP = (
        no_update, # store-model-interface-configurations
        no_update, # store-finance-interface-configurations
        no_update, # model-config
        no_update, # finance-config
        no_update, # prequeue-model-run
        no_update, # prequeue-finance-run
        no_update, # trigger-postprocess-model-run
        no_update, # trigger-postprocess-finance-fun
    )

    if dispatchitem_action_user is None:
        return NUP
    
    if isinstance(dispatchitem_action_user, list):
        dispatchitem_action_user = [json.loads(x) for x in dispatchitem_action_user]
    else:
        dispatchitem_action_user = [json.loads(dispatchitem_action_user)]
    
    if store_model_interface_configurations is None:
        store_model_interface_configurations = {}
    else:
        store_model_interface_configurations = json.loads(
            store_model_interface_configurations
        )
    
    if store_finance_interface_configurations is None:
        store_finance_interface_configurations = {}
    else:
        store_finance_interface_configurations = json.loads(
            store_finance_interface_configurations
        )
    
    mdl_change_list = []
    fnc_change_list = []

    lastmodel = None
    lastfinance = None

    for action in dispatchitem_action_user:
        match action['type']:
            case 'model_config_interface_update':
                model_id = action['model_id']
                
                # Avoid doing the get if mdl_conf is already correctly assigned
                if not lastmodel or lastmodel != model_id:
                    if model_id not in mdl_change_list:
                        mdl_change_list.append(model_id)
                    lastmodel = model_id
                    mdl_conf = store_model_interface_configurations.get(model_id, {})
                    if not mdl_conf:
                        # Empty dictionary returned - ensure key-val pair set
                        store_model_interface_configurations[model_id] = mdl_conf

                # First update the interface conf
                update_val = {action['key']: action['val']}
                if action['key_section'] is None:
                    mdl_conf.update(update_val) # pyright: ignore[reportPossiblyUnboundVariable]
                else:
                    if mdl_conf.get(action['key_section']) is None or action['key_section'] == 'None': # pyright: ignore[reportPossiblyUnboundVariable]
                        mdl_conf[action['key_section']] = {} # pyright: ignore[reportPossiblyUnboundVariable]
                    
                    mdl_conf[action['key_section']].update(update_val) # pyright: ignore[reportPossiblyUnboundVariable]
                
                # We'll synchronise models once we've done all the updates
            case 'finance_config_interface_update':
                finance_id = action['finance_id']

                # Avoid doing the get if fnc_conf is already correctly assigned
                if not lastfinance or lastfinance != finance_id:
                    if finance_id not in fnc_change_list:
                        fnc_change_list.append(finance_id)
                    lastfinance = finance_id
                    fnc_conf = store_finance_interface_configurations.get(finance_id, {})
                    if not fnc_conf:
                        # Empty dictionary returned - ensure key-val pair set
                        store_finance_interface_configurations[finance_id] = fnc_conf
                
                update_val = {action['key']: action['val']}

                if action['key_section'] is None or action['key_section'] == 'None':
                    fnc_conf.update(update_val) # pyright: ignore[reportPossiblyUnboundVariable]
                else:
                    if fnc_conf.get(action['key_section']) is None: # pyright: ignore[reportPossiblyUnboundVariable]
                        fnc_conf[action['key_section']] = {} # pyright: ignore[reportPossiblyUnboundVariable]
                    
                    fnc_conf[action['key_section']].update(update_val) # pyright: ignore[reportPossiblyUnboundVariable]
                # We'll synchronise finances once we've done all the updates

    if store_selected_configuration is None:
        selected_model_id = ""
        selected_finance_id = ""
    else:
        selected_config = json.loads(store_selected_configuration)
        selected_model_id = selected_config['model_id']
        selected_finance_id = selected_config['finance_id']

    r_model_config = no_update
    r_finance_config = no_update
    
    mdl_run_list = []
    for model_id in mdl_change_list:
        mdl_conf = store_model_interface_configurations.get(model_id, {})
        mdl = app.models.get(model_id)
        dirty = sync_interface_config_to_model(mdl_conf, mdl)
        if dirty:
            mdl_run_list.append(model_id)
            if model_id == selected_model_id:
                r_model_config = json.dumps(sprake_model_to_interface_config(mdl))
    
    # Need to perform a manual trigger of the postprocess (for header updates)
    # even if no model runs have occurred
    r_trigger_postprocess_model_run = no_update
    if len(mdl_change_list) == 0:
        r_local_model_config = no_update
    else:
        logger.info('%d local model configs changed', len(mdl_change_list))
        r_local_model_config = json.dumps(store_model_interface_configurations)
        if len(mdl_run_list) == 0:
            r_trigger_postprocess_model_run = [
                json.dumps(
                    browser.model_run_request(model_id)
                ) for model_id in mdl_change_list
            ]
    
    fnc_run_list = []
    for finance_id in fnc_change_list:
        fnc_conf = store_finance_interface_configurations.get(finance_id, {})
        fnc = app.finances.get(finance_id)
        dirty = sync_interface_config_to_finance(fnc_conf, fnc)
        if dirty and fnc.model is not None:
            # Need to store both the finance id and its associated model id,
            # in case the model is locked
            fnc_run_list.append((finance_id, fnc.model.id))
            if finance_id == selected_finance_id:
                r_finance_config = json.dumps(
                    sprake_finance_to_interface_config(fnc)
                )

    # Need to perform a manual trigger of the postprocess (for header updates)
    # even if no finance runs have occurred
    r_trigger_postprocess_finance_run = no_update
    if len(fnc_change_list) == 0:
        r_local_finance_config = no_update
    else:
        logger.info('%d local finance configs changed', len(fnc_change_list))
        r_local_finance_config = json.dumps(store_finance_interface_configurations)
        if len(fnc_run_list) == 0:
            r_trigger_postprocess_finance_run = [
                json.dumps(
                    browser.finance_run_request(
                        finance_id,
                        app.finances.get(finance_id).model.id # pyright: ignore[reportOptionalMemberAccess]
                    ) 
                ) for finance_id in fnc_change_list
            ]

    if len(mdl_run_list) == 0:
        r_model_run_requests = no_update
    else:
        logger.info('%d models dirtied by updates', len(mdl_run_list))
        r_model_run_requests = [
            json.dumps(
                browser.model_run_request(model_id)
            ) for model_id in mdl_run_list
        ]

    if len(fnc_run_list) == 0:
        r_finance_run_requests = no_update
    else:
        logger.info('%d finances dirtied by updates', len(fnc_run_list))
        r_finance_run_requests = [
            json.dumps(
                browser.finance_run_request(finance_id, model_id)
            ) for finance_id, model_id in fnc_run_list
        ]
        
    return (
        r_local_model_config,
        r_local_finance_config,
        r_model_config,
        r_finance_config,
        r_model_run_requests,
        r_finance_run_requests,
        r_trigger_postprocess_model_run,
        r_trigger_postprocess_finance_run
    )
