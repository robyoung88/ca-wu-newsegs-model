from functools import partial
import json
import logging
import uuid

from dash import html, no_update

from src.newsegsbrowser import icons
import src.newsegsbrowser.common as browser

logger = logging.getLogger(__name__)

def sync_config(
    firstload_config_watcher,
    store_selected_configuration,
    store_configurations,
    app,
    create_default_model,
    create_default_finance,
    model_and_finance_to_interface_function
):
    if store_selected_configuration is None:
        if store_configurations is None or len(store_configurations) == 0:
            # On first load, we can generate a random configuration
            store_configurations = [
                json.dumps(
                    browser.compose_configuration(
                        'Configuration Name',
                        'm-' + str(uuid.uuid4()),
                        'f-' + str(uuid.uuid4())
                    )
                )
            ]
        
        store_selected_configuration = json.loads(store_configurations[0])
        store_selected_configuration['config_index'] = 0
    else:
        store_selected_configuration = json.loads(store_selected_configuration)
    
    logger.info('Selected configuration is: %s', store_selected_configuration)
    
    mdl = app.models.get(store_selected_configuration['model_id'])
    if mdl is None:
        # TODO: Deal with if the model should exist.
        # Need to recreate it from the local store.
        mdl = create_default_model()
        mdl.id = store_selected_configuration['model_id']
        app.models[mdl.id] = mdl
    
    fnc = app.finances.get(store_selected_configuration['finance_id'])
    if fnc is None:
        # TODO: Deal with if the finance should exist.
        # Need to recreate it from the local store.
        fnc = create_default_finance()
        fnc.id = store_selected_configuration['finance_id']
        fnc.set_model(mdl, False)
        app.finances[fnc.id] = fnc
    
    # TODO - these do not require an update if store_configurations was the trigger
    
    mcfg, fcfg = model_and_finance_to_interface_function(mdl, fnc)

    return (
        json.dumps(store_selected_configuration),
        store_configurations,
        json.dumps(mcfg),
        json.dumps(fcfg)
    )

def sync_loc_inputs_to_store(mcfg, app):
    if mcfg is None:
        return no_update
    mcfg = json.loads(mcfg)
    loc_input = mcfg.get('loc_input', None)
    return json.dumps(loc_input)

def sync_gen_inputs_to_store(mcfg, input_values, input_ids, app):
    NUP = (no_update, [no_update] * len(input_values))
    if mcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    conf = mcfg.get('gen_input', {})
    
    header_children = [
        'Total generation: ',
        icons.get_icon('gen-wind','p-1 my-1, ml-1', 'unpadded'),
        " = ",
        html.Span(f"{conf.get('wind_capacity', 0.0):,.1f}"),
        " kW; ",
        icons.get_icon('gen-pv','p-1 my-1, ml-1', 'unpadded'),
        " = ",
        html.Span(f"{conf.get('pv_capacity', 0.0):,.1f}",),
        " kWp"
    ]

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in conf.keys():
            v = conf[id['key']]
            if input_values[i] != v:
                input_list[i] = v
    
    return (header_children, input_list)

def sync_stor_inputs_to_store(mcfg, input_values, input_ids, app):
    NUP = (no_update, [no_update] * len(input_values))
    if mcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    conf = mcfg.get('stor_input', {})
    
    header_children = [
        'Storage capacity: ',
        html.Span(f"{conf.get('storage_capacity', 0.0):,.0f}"),
        " kWh"
    ]

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in conf.keys():
            v = conf[id['key']]
            if input_values[i] != v:
                input_list[i] = v
    
    return (header_children, input_list)

def sync_bc_inputs_to_store(mcfg, input_values, input_ids, app):
    NUP = (no_update, [no_update] * len(input_values))
    if mcfg is None:
        return NUP
    mcfg = json.loads(mcfg)
    conf = mcfg.get('bc_input', {})
    
    header_children = [
        'Site size: ',
        html.Span(f"{conf.get('n_units', 0):,.0f}"),
        " units"
    ]

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in conf.keys():
            v = conf[id['key']]
            if input_values[i] != v:
                input_list[i] = v
    
    return (header_children, input_list)

def sync_fnc_inputs_to_store(
    mcfg,
    fcfg,
    input_values,
    input_ids,
    app
):
    NUP = (no_update, [no_update] * len(input_values))
    if mcfg is None or fcfg is None:
        return NUP
    #mcfg = json.loads(mcfg)
    fcfg = json.loads(fcfg)
    
    header_children = [
        icons.get_icon('finance-settings-benefit-discount'),
        " = ",
        html.Span(f"{fcfg.get('benefit_discount_rate', 0.0)/100:,.1%}"),
        "; ",
        icons.get_icon('finance-settings-cost-discount'),
        " = ",
        html.Span(f"{fcfg.get('cost_discount_rate', 0.0)/100:,.1%}"),
    ]

    input_list = [no_update] * len(input_values)
    for i, id in enumerate(input_ids):
        if id['key'] in fcfg.keys():
            v = fcfg[id['key']]
            if input_values[i] != v:
                input_list[i] = v
    
    return (header_children, input_list)
