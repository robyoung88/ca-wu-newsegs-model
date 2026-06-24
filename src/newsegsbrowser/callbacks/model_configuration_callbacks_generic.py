import datetime
from functools import partial
import json
import logging
from typing import Callable, MutableSequence
import uuid

from dash import Patch, html, no_update
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
import newsegsbrowser.common as browser

from newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodel.newsegsmodel import NewsegsModel
from newsegsvariable import variable
import newsegsmetamodel

logger = logging.getLogger(__name__)

def sync_config(
    firstload_config_watcher,
    store_selected_configuration,
    store_configurations,
    input_containers,
    trigger_ids,
    app,

    create_default_model: Callable[[], NewsegsModel],
    create_default_finance: Callable[[], NewsegsFinance],
    create_default_variables: Callable[[], MutableSequence[variable.Variable]],
    
    model_and_finance_to_interface_function
):
    """
    Take values from model/finance and push to interface.

    This is also fired on first load of model page, so is responsible for
    creation of the first metamodel / configuration.
    """
    NUP = (
        no_update, # store-selected-configurations
        no_update, # store-configurations
        no_update, # model-config
        no_update, # finance-config
        [no_update] * len(input_containers), # input-container children
        [no_update] * len(trigger_ids), # trigger data
        no_update # prequeue-action-user patch
    )

    if store_selected_configuration is None:
        if store_configurations is None or len(store_configurations) == 0:
            # On first load, we can generate a random configuration
            store_configurations = [
                json.dumps(
                    newsegsmetamodel.NewsegsMetaModel.generate_new_config()
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

    mm = app.metamodels.get(store_selected_configuration['metamodel_id'])
    if mm is None:
        variables = create_default_variables()
        for v in variables:
            v.update_model(mdl)
            v.update_model(fnc)
        mm = newsegsmetamodel.NewsegsMetaModel(
            mdl,
            fnc,
            variables
        )
        mm.id = store_selected_configuration['metamodel_id']
        app.metamodels[mm.id] = mm

    inputs = []
    logger.info('Creating inputs for metamodel: %s', mm.id)
    for ic in input_containers:
        cnts = []
        section = ic.get('section')
        for var in mm.variables.values():
            if var.interface_section == section and var.configuration_show:
                if not isinstance(var, variable.ScalarVariable):
                    raise TypeError(f'Cannot handle variables of type {type(var)}')
                # Create an input
                cnts.append(
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            var.icon_name,
                            f'{var.label} ({var.unit})',
                            'input-finance-config' if var.configuration_type == 'finance' else 'input-model-config',
                            var.interface_key,
                            section = var.interface_section,
                            subindex = var.interface_subindex,
                            value = var.get_deterministic_value(), # pyright: ignore[reportArgumentType]
                            min = var.interface_min,
                            max = var.interface_max,
                            step = var.interface_step if var.interface_step else 1
                        )
                    )
                )
        inputs.append(cnts)

    # TODO - these do not require an update if store_configurations was the trigger
    
    mcfg, fcfg = model_and_finance_to_interface_function(mdl, fnc)

    if mdl.dirty:
        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(browser.model_run_interface_action(mm.id, mdl.id))
        )
    else:
        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(browser.result_update_interface_action(mm.id))
        )

    return (
        json.dumps(store_selected_configuration), # store-selected-configurations
        store_configurations, # store-configurations
        json.dumps(mcfg), # model-config
        json.dumps(fcfg), # finance-config
        inputs,  # input-container children
        [datetime.datetime.now().timestamp()] * len(trigger_ids), # trigger data
        prequeue_patch # prequeue-action-user patch
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
