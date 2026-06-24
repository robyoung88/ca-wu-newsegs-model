import datetime
from functools import partial
import json
import logging
from typing import Callable, MutableSequence, cast
import uuid

from dash import Patch, html, no_update
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
import newsegsbrowser.common as browser
from newsegsbrowser import variable_dash_component as var_dc

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
        ss = ic.get('supersection')
        if ss == 'dsa':
            for var in mm.variables.values():
                if var.dsa_show:
                    if var.unit != '':
                        lbl = f'{var.name} ({var.unit})'
                    else:
                        lbl = f'{var.name}'
                    match var.distribution.distribution:
                        case 'constant':
                            is_scalar = True,
                            creation_func = var_dc.create_dsa_input_scalar_constant
                        case 'normal':
                            is_scalar = True,
                            creation_func = var_dc.create_dsa_input_scalar_normal
                        case 'beta':
                            is_scalar = True,
                            creation_func = var_dc.create_dsa_input_scalar_beta
                        case 'gamma':
                            is_scalar = True,
                            creation_func = var_dc.create_dsa_input_scalar_gamma
                        case _:
                            raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
                    
                    if is_scalar:
                        var = cast(variable.ScalarVariable, var)
                        if not var.interface_section:
                            cnts.append(
                                creation_func(
                                    lbl, 
                                    var.dsa_selected,
                                    'dsa-input-model-config',
                                    var.interface_key,
                                ),
                            )
                        else:
                            cnts.append(
                                creation_func(
                                    lbl, 
                                    var.dsa_selected,
                                    'dsa-input-model-config',
                                    var.interface_key,
                                    section = var.interface_section),
                            )
        else:
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

        inputs,  # input-container children
        [datetime.datetime.now().timestamp()] * len(trigger_ids), # trigger data
        prequeue_patch # prequeue-action-user patch
    ) 

def sync_loc_inputs_to_store(selected_configuration, app):
    if selected_configuration is None:
        return no_update
    selected_configuration = json.loads(selected_configuration)
    mdl = app.models.get(selected_configuration['model_id'])
    if mdl is None:
        return no_update
    
    loc_input = {
        'lat': mdl.location.lat,
        'lon': mdl.location.lon,
        'name': mdl.location.name
    }
    return json.dumps(loc_input)
