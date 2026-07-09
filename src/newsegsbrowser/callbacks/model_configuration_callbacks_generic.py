import datetime
from functools import partial
import json
import logging
from typing import Any, Callable, MutableSequence, cast
import uuid

from dash import Patch, html, no_update, set_props
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
import newsegsbrowser.common as browser
from newsegsbrowser import variable_dash_component as var_dc
from newsegsbrowser.callbacks.locks import ok_run_model, ok_run_finance

from newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodel.newsegsmodel import NewsegsModel
from newsegsvariable import variable
import newsegsmetamodel

logger = logging.getLogger(__name__)

def create_dsa_input(
    var: variable.Variable
):
    if not var.dsa_show:
        return []
    match var.distribution.distribution:
        case 'constant':
            is_scalar = True
            creation_func = var_dc.create_dsa_input_scalar_constant
        case 'normal':
            is_scalar = True
            creation_func = var_dc.create_dsa_input_scalar_normal
        case 'beta':
            is_scalar = True
            creation_func = var_dc.create_dsa_input_scalar_beta
        case 'gamma':
            is_scalar = True
            creation_func = var_dc.create_dsa_input_scalar_gamma
        case _:
            raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
    
    if is_scalar:
        var = cast(variable.NumericScalarVariable, var)
        return creation_func(var)
    else:
        raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
    
def create_psa_input(
    var: variable.Variable
):
    if not var.psa_show:
        return None
    match var.distribution.distribution:
        case 'constant':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_constant
        case 'normal':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_normal
        case 'beta':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_beta
        case 'gamma':
            is_scalar = True
            creation_func = var_dc.create_psa_input_scalar_gamma
        case _:
            raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')
        
    if is_scalar:
        var = cast(variable.NumericScalarVariable, var)
        return creation_func(var)
    else:
        raise ValueError(f'Distribution {var.distribution.distribution} not currently supported')

def sync_config(
    firstload_config_watchers,
    selected_configuration,
    configurations,
    prequeue_locks,
    input_container_ids,
    generic_text_ids,
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
    rval: dict[str, Any] = dict(
        selected_configuration = no_update,
        configurations = no_update,

        input_container_children = [no_update] * len(input_container_ids),
        generic_text_children = [no_update] * len(generic_text_ids),
        trigger_values = [no_update] * len(trigger_ids),

        prequeue_action_user = no_update
    )

    if selected_configuration is None:
        if configurations is None or len(configurations) == 0:
            # On first load, we can generate a random configuration
            configurations = [
                json.dumps(
                    newsegsmetamodel.NewsegsMetaModel.generate_new_config()
                )
            ]
        
        selected_configuration = json.loads(configurations[0])
        selected_configuration['config_index'] = 0
    else:
        selected_configuration = json.loads(selected_configuration)
    
    logger.info('Selected configuration is: %s', selected_configuration)
    
    mdl = app.models.get(selected_configuration['model_id'])
    if mdl is None:
        # TODO: Deal with if the model should exist.
        # Need to recreate it from the local store.
        mdl = create_default_model()
        mdl.id = selected_configuration['model_id']
        app.models[mdl.id] = mdl
    
    fnc = app.finances.get(selected_configuration['finance_id'])
    if fnc is None:
        # TODO: Deal with if the finance should exist.
        # Need to recreate it from the local store.
        fnc = create_default_finance()
        fnc.id = selected_configuration['finance_id']
        fnc.set_model(mdl, False)
        app.finances[fnc.id] = fnc

    mm = app.metamodels.get(selected_configuration['metamodel_id'])
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
        mm.id = selected_configuration['metamodel_id']
        app.metamodels[mm.id] = mm
        # In the instance of creating a metamodel from scratch, need to update 
        # its name in input fields
        config_index = selected_configuration.get('config_index', 0)
        set_props({'type':'config-name-input', 'index': config_index}, {'value': mm.name})

    inputs = []
    logger.info('Creating inputs for metamodel: %s', mm.id)
    for ic in input_container_ids:
        cnts = []
        ss = ic.get('supersection')

        if ss == 'dsa':
            for var in mm.variables.values():
                cnts.append(create_dsa_input(var))
        elif ss == 'psa':
            for var in mm.variables.values():
                cnts.append(create_psa_input(var))
                
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

    text_values = []
    for text_id in generic_text_ids:
        match text_id.get('key'):
            case 'site-name':
                text_values.append(mm.model.location.name)
            case 'configuration-name':
                text_values.append(mm.name)
            case _:
                text_values.append(no_update)

    if mdl.dirty:
        prequeue_patch = Patch()
        if ok_run_model(prequeue_locks['ids'], prequeue_locks['values']):
            action = browser.model_run_interface_action(metamodel_id = mm.id, model_id = mdl.id)
            logger.info('Adding model_run_interface_action to prequeue_action_user: %s', action)
            prequeue_patch.append(
                json.dumps(action.as_dict())
            )
    else:
        prequeue_patch = Patch()
        action = browser.result_update_interface_action(metamodel_id = mm.id, debounce = False)
        logger.info('Adding result_update_interface_action to prequeue_action_user: %s', action)
        prequeue_patch.append(
            json.dumps(action.as_dict())
        )

    rval['selected_configuration'] = json.dumps(selected_configuration)
    rval['configurations'] = configurations
    rval['input_container_children'] = inputs
    rval['generic_text_children'] = text_values
    rval['trigger_values'] = [datetime.datetime.now().timestamp()] * len(trigger_ids)
    rval['prequeue_action_user'] = prequeue_patch
    
    return rval

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

def update_dsa_boundsinputs(
    dsa_input_change_trigger,
    selected_configuration,
    bounds_container_ids,
    dsa_input_element_ids,
    app
):
    rval: MutableSequence[list[Any]] = [
        [no_update] * len(bounds_container_ids),
        [no_update] * len(dsa_input_element_ids)
    ]

    if dsa_input_change_trigger is None:
        return tuple(rval)
    
    if len(bounds_container_ids) == 0 and len(dsa_input_element_ids) == 0:
        return tuple(rval)
    
    mm = None
    
    selected_configuration = json.loads(selected_configuration)
    logger.info('updating dsa bounds after dsa input change')

    for change_list in dsa_input_change_trigger: # As we have the page wildcard in the callback signature, we have a list of lists
        if isinstance(change_list, list):
            for dic in change_list:
                dic_l = json.loads(dic)
                if dic_l.get('bounds_type_change'):
                    if dic_l.get('metamodel_id') == selected_configuration.get('metamodel_id'):
                        for i, bnd_id in enumerate(bounds_container_ids):
                            if bnd_id['section'] == dic_l['section'] and bnd_id['key'] == dic_l['key'] and bnd_id['subindex'] == dic_l['subindex']:
                                if mm is None:
                                    mm = app.metamodels.get(dic_l.get('metamodel_id'))
                                varid =  dic_l['section']+'.'+dic_l['key']+'.'+str(dic_l['subindex'])
                                var = mm.variables.get(varid)
                                if var is not None:
                                    rval[0][i] = var_dc.create_dsa_bounds_inputs_scalar(var.dsa_bounds_type, var)
                elif dic_l.get('selected_status_change'):
                    if dic_l.get('metamodel_id') == selected_configuration.get('metamodel_id'):
                        for i, el_id in enumerate(dsa_input_element_ids):
                            if el_id['section'] == dic_l['section'] and el_id['key'] == dic_l['key'] and el_id['subindex'] == dic_l['subindex']:
                                if mm is None:
                                    mm = app.metamodels.get(dic_l.get('metamodel_id'))
                                varid =  dic_l['section']+'.'+dic_l['key']+'.'+str(dic_l['subindex'])
                                var = mm.variables.get(varid)
                                if var is not None:
                                    if var.dsa_selected:
                                        cn = 'dsa-input-single-value-block'
                                    else:
                                        cn = 'dsa-input-single-value-block deselected'
                                    rval[1][i] = cn

        else: # Force update all bounds
            if mm is None:
                    mm = app.metamodels.get(selected_configuration.get('metamodel_id'))
            for i, hdr_id in enumerate(bounds_container_ids):
                varid =  hdr_id['section']+'.'+hdr_id['key']+'.'+str(hdr_id['subindex'])
                var = mm.variables.get(varid)
                if var is not None:
                    rval[0][i] = var_dc.create_dsa_bounds_inputs_scalar(var.dsa_bounds_type, var)
            for i, el_id in enumerate(dsa_input_element_ids):
                varid =  el_id['section']+'.'+el_id['key']+'.'+str(el_id['subindex'])
                var = mm.variables.get(varid)
                if var is not None:
                    if var.dsa_selected:
                        cn = 'dsa-input-single-value-block'
                    else:
                        cn = 'dsa-input-single-value-block deselected'
                    rval[1][i] = cn
    
    return rval

def update_headers_dsa_inputs(
    dsa_input_change_trigger,
    selected_configuration,
    header_ids,
    app
):
    rval: list[Any] = [no_update] * len(header_ids)
    if len(header_ids) == 0:
        return rval
    if dsa_input_change_trigger is None:
        return rval
    
    mm = None
    
    selected_configuration = json.loads(selected_configuration)
    logger.info('updating headers after dsa input change')
    
    for change_list in dsa_input_change_trigger: # As we have the page wildcard in the callback signature, we have a list of lists
        if isinstance(change_list, list):
            for dic in change_list:
                dic_l = json.loads(dic)
                if dic_l.get('metamodel_id') == selected_configuration.get('metamodel_id'):
                    for i, hdr_id in enumerate(header_ids):
                        if hdr_id['section'] == dic_l['section'] and hdr_id['key'] == dic_l['key'] and hdr_id['subindex'] == dic_l['subindex']:
                            if mm is None:
                                mm = app.metamodels.get(dic_l.get('metamodel_id'))
                            varid =  dic_l['section']+'.'+dic_l['key']+'.'+str(dic_l['subindex'])
                            var = mm.variables.get(varid)
                            if var is not None:
                                rval[i] = var_dc.create_dsa_header(var)
        else: # Force update all headers
            for i, hdr_id in enumerate(header_ids):
                if mm is None:
                    mm = app.metamodels.get(selected_configuration.get('metamodel_id'))
                varid =  hdr_id['section']+'.'+hdr_id['key']+'.'+str(hdr_id['subindex'])
                var = mm.variables.get(varid)
                if var is not None:
                    rval[i] = var_dc.create_dsa_header(var)
    
    return rval

def update_headers_psa_inputs(
    psa_input_change_trigger,
    selected_configuration,
    header_ids,
    app
):
    rval: list[Any] = [no_update] * len(header_ids)
    if len(header_ids) == 0:
        return rval
    if psa_input_change_trigger is None:
        return rval
    
    mm = None
    
    selected_configuration = json.loads(selected_configuration)
    logger.info('updating headers after psa input change')
    
    for change_list in psa_input_change_trigger: # As we have the page wildcard in the callback signature, we have a list of lists
        if isinstance(change_list, list):
            for dic in change_list:
                dic_l = json.loads(dic)
                if dic_l.get('metamodel_id') == selected_configuration.get('metamodel_id'):
                    for i, hdr_id in enumerate(header_ids):
                        if hdr_id['section'] == dic_l['section'] and hdr_id['key'] == dic_l['key'] and hdr_id['subindex'] == dic_l['subindex']:
                            if mm is None:
                                mm = app.metamodels.get(dic_l.get('metamodel_id'))
                            varid =  dic_l['section']+'.'+dic_l['key']+'.'+str(dic_l['subindex'])
                            var = mm.variables.get(varid)
                            if var is not None:
                                rval[i] = var_dc.create_psa_header(var)
        else: # Force update all headers
            for i, hdr_id in enumerate(header_ids):
                if mm is None:
                    mm = app.metamodels.get(selected_configuration.get('metamodel_id'))
                varid =  hdr_id['section']+'.'+hdr_id['key']+'.'+str(hdr_id['subindex'])
                var = mm.variables.get(varid)
                if var is not None:
                    rval[i] = var_dc.create_psa_header(var)
    
    return rval

def update_psa_inputs_status(
    psa_input_change_trigger,
    selected_configuration,
    psa_input_element_ids,
    app
):
    if len(psa_input_element_ids) == 0:
        return []
    
    rval: list[Any] = [no_update] * len(psa_input_element_ids)

    if psa_input_change_trigger is None:
        return rval
    
    mm = None
    
    selected_configuration = json.loads(selected_configuration)

    for change_list in psa_input_change_trigger: # As we have the page wildcard in the callback signature, we have a list of lists
        if isinstance(change_list, list):
            for dic in change_list:
                dic_l = json.loads(dic)
                if dic_l.get('selected_status_change'):
                    if dic_l.get('metamodel_id') == selected_configuration.get('metamodel_id'):
                        for i, el_id in enumerate(psa_input_element_ids):
                            if el_id['section'] == dic_l['section'] and el_id['key'] == dic_l['key'] and el_id['subindex'] == dic_l['subindex']:
                                if mm is None:
                                    mm = app.metamodels.get(dic_l.get('metamodel_id'))
                                varid =  dic_l['section']+'.'+dic_l['key']+'.'+str(dic_l['subindex'])
                                var = mm.variables.get(varid)
                                if var is not None:
                                    if var.psa_selected:
                                        cn = 'psa-input-single-value-block'
                                    else:
                                        cn = 'psa-input-single-value-block deselected'
                                    rval[i] = cn

        else: # Force update all bounds
            if mm is None:
                    mm = app.metamodels.get(selected_configuration.get('metamodel_id'))
           
            for i, el_id in enumerate(psa_input_element_ids):
                varid =  el_id['section']+'.'+el_id['key']+'.'+str(el_id['subindex'])
                var = mm.variables.get(varid)
                if var is not None:
                    if var.psa_selected:
                        cn = 'psa-input-single-value-block'
                    else:
                        cn = 'psa-input-single-value-block deselected'
                    rval[i] = cn
    
    return rval
