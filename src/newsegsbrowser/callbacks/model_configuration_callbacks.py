"""

Functions:
- add_initial_callbacks
- add_model_to_interface_callbacks
- add_feedback_callbacks
- add_interface_to_model_callbacks
"""

import datetime
import json
import logging
from typing import Any, Sequence, cast

from dash import ALL, NoUpdate, ctx, Dash, Input, Output, Patch, State, no_update
from dash import clientside_callback, ClientsideFunction
import numpy as np
from useful_types import SequenceNotStr

from newsegsbrowser import common as browser
from newsegsbrowser.callbacks import callbacks_map
from newsegsbrowser.callbacks.locks import ok_run_model, ok_run_finance
from newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

logger = logging.getLogger(__name__)

SYNC_DEBOUNCE_SECONDS = 0.1

def add_initial_callbacks(app: Dash):
    """
    Functions which are triggered immediately after page load.
    """

    # Logic for controlling the results drawer in a vertical view
    clientside_callback(
        ClientsideFunction(
            namespace = 'clientside',
            function_name = 'attach_drawer'
        ),
        Output({'type': 'post-drawer-attach', 'page': ALL}, 'children'),
        
        Input({'type' : 'onload-div', 'selected_model': ALL, 'page_type': ALL}, 'children')
    )

    @app.callback(
        Output({'type' : 'firstload-config-watcher', 'selected_model': ALL, 'page_type': ALL}, 'data'),
        
        Input({'type' : 'onload-div', 'selected_model': ALL, 'page_type': ALL}, 'children'),
        State({'type' : 'onload-div', 'selected_model': ALL, 'page_type': ALL}, 'id'),
    )
    def sync_config_init(_, config_watcher_ids):
        """
        Trigger any initial actions after a page load
        """
        logger.info('Model configuration onload div constructed.')
        return [datetime.datetime.now().timestamp()] * len(config_watcher_ids)
    
    return app

def add_model_to_interface_callbacks(app: Dash):
    """
    Callbacks for passing model configuration data to the interface
    """

    # Trigger on first load, whenever a configuration is changed extrinsically
    # (i.e. loaded, duplicated) and whenever the selected configuration is
    # changed.
    @app.callback(
        Output('store-selected-configuration', 'data', allow_duplicate = True),
        Output('store-configurations', 'data', allow_duplicate = True),
        Output({'type': 'input-container', 'supersection': ALL, 'section': ALL}, 'children'),
        Output({'type': 'generic_text', 'section': ALL, 'key': ALL}, 'children'),
        Output({'type': 'trigger', 'page': ALL, 'key': ALL}, 'data', allow_duplicate = True),
        Output('prequeue-action-user', 'data', allow_duplicate = True),

        Input({'type' : 'firstload-config-watcher', 'selected_model': ALL, 'page_type': ALL}, 'data'),
        Input('store-selected-configuration', 'data'),
        Input('store-configurations', 'data'),

        State({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'id'),
        State({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'data'),

        State({'type': 'input-container', 'supersection': ALL, 'section': ALL}, 'id'),
        State({'type': 'generic_text', 'section': ALL, 'key': ALL}, 'id'),
        State({'type': 'trigger', 'page': ALL, 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_config(
        firstload_config_watcher,
        store_selected_configuration,
        store_configurations,

        prequeue_lock_ids,
        prequeue_lock_values,

        input_containers,
        generic_text_ids,
        trigger_ids,
        selected_model
    ):
        logger.info('sync_config triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_config'](
            firstload_config_watcher,
            store_selected_configuration,
            store_configurations,

            prequeue_lock_ids,
            prequeue_lock_values,

            input_containers,
            generic_text_ids,
            trigger_ids,
            app
        )
    
    # Updates to inputs based on config
    @app.callback(
        Output('site-location', 'data', allow_duplicate = True),
        
        Input('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_loc_inputs_to_store(
        selected_configuration,
        selected_model
    ):
        logger.info('sync_loc_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_loc_inputs_to_store'](
            selected_configuration,
            app
        )
    
    
    @app.callback(
        Output({'type':'dsa-bounds-inputcontainer', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'children'),
        Output({'type':'dsa-input-element', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'className'),

        Input({'type': 'trigger', 'page': ALL, 'key': 'dsa_input_change'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type':'dsa-bounds-inputcontainer', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'id'),
        State({'type':'dsa-input-element', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_dsa_bounds_inputs(
        dsa_input_change_trigger,
        selected_configuration,
        bounds_container_ids,
        dsa_input_element_ids,
        selected_model
    ):
        logger.info('update_dsa_bounds_inputs triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_dsa_boundsinputs'](
            dsa_input_change_trigger,
            selected_configuration,
            bounds_container_ids,
            dsa_input_element_ids,
            app
        )
    
    @app.callback(
        Output({'type':'psa-input-element', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'className'),

        Input({'type': 'trigger', 'page': ALL, 'key': 'psa_input_change'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type':'psa-input-element', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_psa_inputs_status(
        psa_input_change_trigger,
        selected_configuration,
        psa_input_element_ids,
        selected_model,
    ):
        logger.info('update_psa_inputs_status triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_psa_inputs_status'](
            psa_input_change_trigger,
            selected_configuration,
            psa_input_element_ids,
            app
        )
    
    return app
    
def add_feedback_callbacks(app):
    """
    Callbacks for updating feedback elements given current configuration
    """

    @app.callback(
        Output({'type': 'input-header', 'section': 'model-config', 'key': ALL}, 'children'),
        
        Input({'type': 'trigger', 'page': ALL, 'key': 'model-config'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type': 'input-header', 'section': 'model-config', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_headers_model_config(
        model_config_trigger,
        selected_configuration,
        header_ids,
        selected_model
    ):
        logger.info('update_headers_model_config triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_headers_model_config'](
            model_config_trigger,
            selected_configuration,
            header_ids,
            app
        )
    
    # Trigger on both model and finance config updates
    @app.callback(
        Output({'type': 'input-header', 'section': 'finance-config', 'key': ALL}, 'children'),
        
        Input({'type': 'trigger', 'page': ALL, 'key': 'finance-config'}, 'data'),
        Input({'type': 'trigger', 'page': ALL, 'key': 'model-config'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type': 'input-header', 'section': 'finance-config', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_headers_finance_config(
        finance_config_trigger,
        model_config_trigger,
        selected_configuration,
        header_ids,
        selected_model
    ):
        logger.info('update_headers_finance_config triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_headers_finance_config'](
            finance_config_trigger,
            selected_configuration,
            header_ids,
            app
        )
    
    @app.callback(
        Output({'type':'dsa-input-header', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'children'),

        Input({'type': 'trigger', 'page': ALL, 'key': 'dsa_input_change'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type':'dsa-input-header', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_headers_dsa_inputs(
        dsa_input_change_trigger,
        selected_configuration,
        header_ids,
        selected_model
    ):
        logger.info('update_headers_dsa_inputs triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_headers_dsa_inputs'](
            dsa_input_change_trigger,
            selected_configuration,
            header_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'psa-input-header', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'children'),

        Input({'type': 'trigger', 'page': ALL, 'key': 'psa_input_change'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type':'psa-input-header', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_headers_psa_inputs(
        psa_input_change_trigger,
        selected_configuration,
        header_ids,
        selected_model
    ):
        logger.info('update_headers_psa_inputs triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_headers_psa_inputs'](
            psa_input_change_trigger,
            selected_configuration,
            header_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'feedback-graph', 'section': 'feedback', 'key': ALL}, 'figure'),
        
        Input({'type': 'trigger', 'page': ALL, 'key': 'model-config'}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type': 'feedback-graph', 'section': 'feedback', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_feedback_graphs(
        model_config_trigger,
        selected_configuration,
        figure_ids,
        selected_model
    ):
        logger.info('update_feedback_graphs triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_feedback_graphs'](
            model_config_trigger,
            selected_configuration,
            figure_ids,
            app
        )

    return app



def add_interface_to_model_callbacks(app):
    """
    Callbacks for when a user changes a model or finance config input.
    """

    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        
        Output({'type': 'input-model-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),
        Output({'type': 'input-finance-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),
        
        Output({'type': 'input-model-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'invalid'),
        Output({'type': 'input-finance-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'invalid'),
        
        Output({'type': 'trigger', 'page': ALL, 'key': 'model-config'}, 'data', allow_duplicate = True),
        Output({'type': 'trigger', 'page': ALL, 'key': 'finance-config'}, 'data', allow_duplicate = True),

        Input({'type': 'input-model-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),
        Input({'type': 'input-finance-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),

        State('store-selected-configuration', 'data'),

        State({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'id'),
        State({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'data'),

        State({'type': 'input-model-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'id'),
        State({'type': 'input-finance-config', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'id'),
        State({'type': 'trigger', 'page': ALL, 'key': 'model-config'}, 'id'),
        State({'type': 'trigger', 'page': ALL, 'key': 'finance-config'}, 'id'),
        
        prevent_initial_call=True
    )
    def interface_update_config(
        inputs_model,
        inputs_finance,

        selected_config,

        prequeue_lock_ids,
        prequeue_lock_values,

        model_input_ids,
        finance_input_ids,
        model_config_trigger_ids,
        finance_config_trigger_ids,
    ):
        """
        Add model configuration update events to the user action prequeue.

        May be fired before the queuemanager absorbs the prequeue, so needs
        to ensure that the prequeue is appended, not overwritten.
        In future, we may see if we can do this with a Patch - not sure how the
        data are held, and it may be that we can just append a list rather than
        full json deserialise/serialise.
        """
        NUP = (
            no_update, # prequeue-action-user patch
            [no_update] * len(model_input_ids), # model input values
            [no_update] * len(finance_input_ids), # finance input values
            [no_update] * len(model_input_ids), # model input invalid
            [no_update] * len(finance_input_ids), # finance input invalid
            [no_update] * len(model_config_trigger_ids), # trigger model config
            [no_update] * len(finance_config_trigger_ids), # trigger finance config
        )
        
        selected_mm = json.loads(selected_config).get('metamodel_id', None)
        if selected_mm is None:
            return NUP
        selected_mm = cast(NewsegsMetaModel, app.metamodels.get(selected_mm))
        if selected_mm is None:
            return NUP

        selected_model = json.loads(selected_config).get('model_id', None)
        if selected_model is None:
            return NUP
        selected_finance = json.loads(selected_config).get('finance_id', None)

        #if prequeue is None:
        #    prequeue = []
        prequeue_patch = Patch()
        prequeue = []

        #l1 = len(prequeue)
        
        logger.info('configuration input field changed')

        model_changed = False
        finance_changed = False

        rval: list[Any] = list(NUP)

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']
            update_ok, deterministic_changed, dsa_changed, psa_changed, raw_params = selected_mm.update_variable_from_interface(
                pid['section'], pid['key'], pid['subindex'], pid['parameter_index'], pid['vector_location'], val
            )
            match pid['type']:
                case 'input-model-config':
                    for i, id in enumerate(model_input_ids):
                        if (
                            id['section'] == pid['section']
                            and id['key'] == pid['key']
                            and id['subindex'] == pid['subindex']
                        ):
                            # Set model input invalid if bad update
                            if id['parameter_index'] == pid['parameter_index'] and id['vector_location'] == pid['vector_location']:
                                rval[3][i] = not(update_ok)  # type: ignore
                            
                            # Feed back the current parameters. This is necessary in case e.g. setting the mean required a change in the SD to make the distribution tractable.
                            pi = id['parameter_index']
                            new_param = raw_params[pi]
                            if not isinstance(new_param, np.ndarray):
                                rval[1][i] = new_param # type: ignore
                            else:
                                vi = id['vector_location']
                                new_val = new_param.flat[vi]
                                rval[1][i] = new_val # type: ignore
                    
                    if deterministic_changed:
                        #if ok_run_model(prequeue_lock_ids, prequeue_lock_values):
                        model_changed = True
                        prequeue.append(
                            json.dumps(
                                browser.model_interface_action(
                                    metamodel_id = selected_mm.id,
                                    **pid
                                )
                            )
                        )
                        rval[5] = [datetime.datetime.now().timestamp()] * len(model_config_trigger_ids)
                case 'input-finance-config':
                    for i, id in enumerate(finance_input_ids):
                        if (
                            id['section'] == pid['section']
                            and id['key'] == pid['key']
                            and id['subindex'] == pid['subindex']
                        ):
                            if id['parameter_index'] == pid['parameter_index'] and id['vector_location'] == pid['vector_location']:
                                rval[4][i] = not(update_ok)  # type: ignore
                            pi = id['parameter_index']
                            new_param = raw_params[pi]
                            if not isinstance(new_param, np.ndarray):
                                rval[2][i] = new_param # type: ignore
                            else:
                                vi = id['vector_location']
                                new_val = new_param.flat[vi]
                                rval[2][i] = new_val # type: ignore

                    if deterministic_changed:
                        # Need to check if model results are available
                        # If not, add a model run and allow that to trigger
                        # finance
                        if not hasattr(selected_mm.model, '_cs_result'):
                            prequeue.append(
                                json.dumps(
                                    browser.model_interface_action(
                                        metamodel_id = selected_mm.id,
                                        **pid
                                    )
                                )
                            )
                        else:
                            #if ok_run_finance(prequeue_lock_ids, prequeue_lock_values):
                            prequeue.append(
                                json.dumps(
                                    browser.finance_interface_action(
                                            metamodel_id = selected_mm.id,
                                            **pid
                                        )
                                )
                            )
                        rval[6] = [datetime.datetime.now().timestamp()] * len(finance_config_trigger_ids)
                case _:
                    raise ValueError('Triggered by an unknown input type %s', pid['type'])
            if dsa_changed:
                prequeue.append(
                    json.dumps(
                        browser.dsa_impacting_interface_action(
                            metamodel_id = selected_mm.id,
                            **pid
                        )
                    )
                )
            if psa_changed:
                prequeue.append(
                    json.dumps(
                        browser.psa_impacting_interface_action(
                            metamodel_id=selected_mm.id,
                            **pid
                        )
                    )
                )
        l2 = len(prequeue)

        if not prequeue:
            return NUP

        if model_changed and finance_changed:
            logger.info('model and finance configuration changes have added %d items to prequeue, which is now %d items long', l2, l2)
        elif model_changed:
            logger.info('model configuration changes have added %d items to prequeue, which is now %d items long', l2, l2)
        elif finance_changed:
            logger.info('finance configuration changes have added %d items to prequeue, which is now %d items long', l2, l2)
            for item in prequeue:
                logger.info(str(item))
        else:
            logger.info('no changes to prequeue, which is %d items long', l2)   
        
        prequeue_patch.extend(prequeue)
        rval[0] = prequeue_patch # type: ignore
        return tuple(rval)
    
    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        Output({'type':'input-dsabound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),
        Output({'type':'input-dsabound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),

        Input({'type': 'toggle-dsa-variable', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'value'),
        Input({'type': 'dropdown-dsaboundtype', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'value'),
        Input({'type':'input-dsabound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),
        Input({'type':'input-dsabound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'value'),
        
        State('store-selected-configuration', 'data'),
        State({'type':'input-dsabound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'id'),
        State({'type':'input-dsabound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL}, 'id'),
        prevent_initial_call = True
    )
    def interface_update_dsa(
        toggle_dsa_variable,
        dsaboundtype_dropdown_value,
        dsabound_lower,
        dsabound_upper,
        selected_config,
        dsabound_lower_ids,
        dsabound_upper_ids,
    ):
        """
        Handle a change to DSA-specific interface components.
        """
        rval = [
            no_update, # prequeue-action-user
            [no_update] * len(dsabound_lower_ids),
            [no_update] * len(dsabound_upper_ids),
        ]

        RVAL_INDICES = {
            'prequeue': 0,
            'dsabound_lower': 1,
            'dsabound_upper': 2,
        }

        if selected_config is None:
            return tuple(rval)
        selected_config = json.loads(selected_config)
        mm = cast(NewsegsMetaModel, app.metamodels.get(selected_config.get('metamodel_id')))
        if mm is None:
            return tuple(rval)
        
        prequeue_patch = Patch()
        logger.info('dsa input field changed')

        forward_prequeue = False

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']

            varid = pid['section']+'.'+pid['key']+'.'+str(pid['subindex'])
            var = mm.variables.get(varid)
            if var is None:
                continue

            match pid['type']:
                case 'dropdown-dsaboundtype':
                    if not val == var.dsa_bounds_type:
                        var.dsa_bounds_type = val
                        dsa_lower, dsa_upper = var.distribution.dsa_auto_values(var)
                        var.dsa_lower = dsa_lower
                        var.dsa_upper = dsa_upper

                        for i, bound_id in enumerate(dsabound_lower_ids):
                            if bound_id['section'] == pid['section'] and bound_id['key'] == pid['key'] and bound_id['subindex'] == pid['subindex']:
                                rval[RVAL_INDICES['dsabound_lower']][i] = dsa_lower
                        for i, bound_id in enumerate(dsabound_upper_ids):
                            if bound_id['section'] == pid['section'] and bound_id['key'] == pid['key'] and bound_id['subindex'] == pid['subindex']:
                                rval[RVAL_INDICES['dsabound_upper']][i] = dsa_upper
                        prequeue_patch.append(
                            json.dumps(
                                browser.dsa_impacting_interface_action(
                                    metamodel_id = mm.id,
                                    bounds_type_change = True,
                                    **pid
                                )
                            )
                        )
                        forward_prequeue = True
                case 'input-dsabound-lower':
                    if val is None:
                        continue
                    if not val == var.dsa_lower:
                        var.dsa_lower = val
                        prequeue_patch.append(
                            json.dumps(
                                browser.dsa_impacting_interface_action(
                                    metamodel_id = mm.id,
                                    **pid
                                )
                            )
                        )
                        forward_prequeue = True
                case 'input_dsabound-upper':
                    if val is None:
                        continue
                    if not val == var.dsa_upper:
                        var.dsa_upper = val
                        prequeue_patch.append(
                            json.dumps(
                                browser.dsa_impacting_interface_action(
                                    metamodel_id = mm.id,
                                    **pid
                                )
                            )
                        )
                        forward_prequeue = True
                case 'toggle-dsa-variable':
                    if val is None:
                        continue
                    if not val == var.dsa_selected:
                        var.dsa_selected = val
                        prequeue_patch.append(
                            json.dumps(
                                browser.dsa_impacting_interface_action(
                                    metamodel_id = mm.id,
                                    selected_status_change = True,
                                    **pid
                                )
                            )
                        )
                        forward_prequeue = True
        
        if forward_prequeue:
            rval[RVAL_INDICES['prequeue']] = prequeue_patch

        return tuple(rval)

    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),

        Input({'type': 'toggle-psa-variable', 'section': ALL, 'key': ALL, 'subindex': ALL}, 'value'),
        
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def interface_update_psa(
        toggle_psa_variable,
        selected_config,
    ):
        """
        Handle a change to PSA-specific interface components.
        """
        rval = no_update # prequeue-action-user

        if selected_config is None:
            return rval
        
        selected_config = json.loads(selected_config)
        mm = cast(NewsegsMetaModel, app.metamodels.get(selected_config.get('metamodel_id')))
        if mm is None:
            return rval
        
        prequeue_patch = Patch()
        logger.info('psa input field changed')

        forward_prequeue = False

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']

            varid = pid['section']+'.'+pid['key']+'.'+str(pid['subindex'])
            var = mm.variables.get(varid)
            if var is None:
                continue

            match pid['type']:
                case 'toggle-psa-variable':
                    if val is None:
                        continue
                    if not val == var.psa_selected:
                        var.psa_selected = val
                        prequeue_patch.append(
                            json.dumps(
                                browser.psa_impacting_interface_action(
                                    metamodel_id = mm.id,
                                    selected_status_change = True,
                                    **pid
                                )
                            )
                        )
                        forward_prequeue = True
        
        if forward_prequeue:
            rval = prequeue_patch

        return rval
    
    def find_matching_actions(
        queue_action_user: list[str],
        action: dict[str, Any],
        i: int,
        type_: str | SequenceNotStr[str],
        filter = lambda x, y: x['metamodel_id'] == y['metamodel_id']
    ) -> list[str]:
        """
        Removes matching items from queue_action_user and returns as dispatch_actions list
        """
        action_indexes = [i]
        j = i + 1
        if j < len(queue_action_user):
            for j in range(j, len(queue_action_user)):
                act_j = json.loads(queue_action_user[j])
                if act_j['type'] == type_:
                    if filter(act_j, action):
                        action_indexes.append(j)
        action_indexes.reverse()
        dispatch_actions = [queue_action_user.pop(x) for x in action_indexes]
        dispatch_actions.reverse
        return dispatch_actions

    @app.callback(
        output = dict(
            prequeue_action_user = Output('prequeue-action-user', 'data', allow_duplicate = True),
            
            prequeue_model_run = Output('prequeue-model-run', 'data', allow_duplicate = True),
            prequeue_finance_run = Output('prequeue-finance-run', 'data', allow_duplicate = True),
            prequeue_metamodel_process = Output('prequeue-metamodel-process', 'data', allow_duplicate = True),

            trigger_postprocess_model_run = Output('trigger-postprocess-model-run', 'data', allow_duplicate = True),
            trigger_postprocess_finance_run = Output('trigger-postprocess-finance-run', 'data', allow_duplicate = True),

            dispatchitem_action_user = Output('dispatchitem-action-user', 'data'),
            interval_action_user = Output('interval-action-user', 'disabled'),
        ),

        inputs = dict(
            prequeue_action_user = Input('prequeue-action-user', 'data'),
            interval_action_user = Input('interval-action-user', 'n_intervals'),

        ),

        state = dict(
            prequeue_lock_ids = State(
                {'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL},
                'id'
            ),
            prequeue_lock_values = State(
                {'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL},
                'data'
            ),
        ),
        prevent_initial_call = True
    )
    def queueman_action_user(
        prequeue_action_user, 
        interval_action_user,

        prequeue_lock_ids,
        prequeue_lock_values,
    ):
        """
        Receives and dispatches user actions.

        On receiving an action through the prequeue, will add it to the end
        of the action queue.
        If the action overrides any queued action, the queued action will
        be removed.
        The queue is then iterated through. If the action is permitted to
        be dispatched, it shall be removed from the queue and dispatched.
        A change to the latch conditions or a trigger through the postdispatch-trigger
        will result in the queue being run through again.
        """
        # if not queue_action_user:
        #     queue_action_user = []

        logger.info('processing user action queue, triggered by: %s', ctx.triggered_id)

        rval: dict[str, Any] = dict(
            prequeue_action_user = no_update,

            prequeue_model_run = no_update,
            prequeue_finance_run = no_update,
            prequeue_metamodel_process = no_update,

            trigger_postprocess_model_run = no_update,
            trigger_postprocess_finance_run = no_update,

            dispatchitem_action_user = no_update,
            interval_action_user = no_update
        )

        queue_action_user = app.sts.get('queue-action-user')
        if queue_action_user is None:
            app.sts['queue-action-user'] = []
            queue_action_user = app.sts.get('queue-action-user')
        
        if ctx.triggered_id == 'prequeue-action-user':
            action = prequeue_action_user
            
            if isinstance(action, list):
                logger.info('handling %d user actions', len(action))
                queue_action_user += action
            else:
                logger.info('handling single user action')
                queue_action_user.append(action)
            
            # TODO: Rationalise queue

        nowtime = datetime.datetime.now().timestamp()

        # As there are multiple exits from this function, it is not as trivial to ensure that
        # we avoid overwriting a dispatch. 
        # May need to re-write the flow again.
        #app_dispatch = app.sts.get('dispatchitem-action-user')

        # Loop through action queue
        for i, action_json in enumerate(queue_action_user):
            action = json.loads(action_json)
            match action['type']:
                case 'model_config_interface_update':
                    if (nowtime - action['time']) > SYNC_DEBOUNCE_SECONDS:
                        mm = cast(NewsegsMetaModel, app.metamodels.get(action['metamodel_id']))
                        logger.info('Checking if model %s is checked out: %s', mm.model.id, mm.model.checked_out)
                        if not mm.model.checked_out:
                            # Have a positive dispatch - find other appropriate actions

                            # NB - this function has side effect of popping matches from queue_action_user
                            dispatch_actions = find_matching_actions(
                                queue_action_user,
                                action,
                                i,
                                'model_config_interface_update'
                            )
                            logger.info('dispatching %d model config interface actions', len(dispatch_actions))

                            # Might as well carry them out here
                            # By definition, if we have got this far then the parameter change has impacted
                            # the deterministic value and the model parameterisation will have changed. A
                            # run should therefore be queued.
                            synced = []
                            for action in dispatch_actions:
                                action = json.loads(action)
                                varid = action['section'] + "." + action['key'] + "." + str(action['subindex'])
                                if varid not in synced:
                                    mm.update_model_from_variable_deterministic(
                                        action['section'],
                                        action['key'],
                                        action['subindex']
                                    )
                                    synced.append(varid)

                            if ok_run_model(prequeue_lock_ids, prequeue_lock_values):
                                r_model_run_request = browser.model_run_request(mm.id, mm.model.id)
                                model_prequeue_patch = Patch()
                                model_prequeue_patch.append(json.dumps(r_model_run_request))

                                logger.info('Adding a run request for %s', mm.model.id)

                                # Do nothing with dispatch_actions
                                rval['prequeue_model_run'] = model_prequeue_patch
                            
                            rval['interval_action_user'] = len(queue_action_user) == 0
                            return rval

                case 'finance_config_interface_update':
                    if (nowtime - action['time']) > SYNC_DEBOUNCE_SECONDS:
                        mm = cast(NewsegsMetaModel, app.metamodels.get(action['metamodel_id']))
                        logger.info('Checking if finance %s is checked out: %s', mm.finance.id, mm.finance.checked_out)
                        if not mm.finance.checked_out:

                            # NB - this function has side effect of popping matches from queue_action_user
                            dispatch_actions = find_matching_actions(
                                queue_action_user,
                                action,
                                i,
                                'finance_config_interface_update'
                            )
                            logger.info('dispatching %d finance config interface actions', len(dispatch_actions))

                            # Might as well carry them out here
                            # By definition, if we have got this far then the parameter change has impacted
                            # the deterministic value and the model parameterisation will have changed. A
                            # run should therefore be queued.
                            synced = []
                            for action in dispatch_actions:
                                action = json.loads(action)
                                varid = action['section'] + "." + action['key'] + "." + str(action['subindex'])
                                if varid not in synced:
                                    mm.update_model_from_variable_deterministic(
                                        action['section'],
                                        action['key'],
                                        action['subindex']
                                    )
                                    synced.append(varid)

                            if ok_run_finance(prequeue_lock_ids, prequeue_lock_values):
                                r_finance_run_request = browser.finance_run_request(mm.id, mm.finance.id, mm.model.id)
                                finance_prequeue_patch = Patch()
                                finance_prequeue_patch.append(json.dumps(r_finance_run_request))

                                logger.info('Adding a finance run request for %s', mm.finance.id)

                                # Do nothing with dispatch_actions
                                rval['prequeue_finance_run'] = finance_prequeue_patch
                            
                            rval['interval_action_user'] = len(queue_action_user) == 0
                            return rval
                        
                case 'model_run_interface_request':
                    # No debounce on a model run request
                    mm = cast(NewsegsMetaModel, app.metamodels.get(action['metamodel_id']))
                    if mm is None:
                        raise ValueError(f'metamodel {action['metamodel_id']} could not be recovered.')
                    if not mm.model.checked_out:

                        # NB - this function has side effect of popping matches from queue_action_user
                        dispatch_actions = find_matching_actions(
                            queue_action_user,
                            action,
                            i,
                            'model_run_interface_request'
                        )
                        logger.info('dispatching %d model run interface requests', len(dispatch_actions))

                        if ok_run_model(prequeue_lock_ids, prequeue_lock_values):

                            # Nothing to do but to make the request with the first action
                            r_model_run_request = browser.model_run_request(mm.id, mm.model.id)
                            model_prequeue_patch = Patch()
                            model_prequeue_patch.append(json.dumps(r_model_run_request))

                            logger.info('Adding a run request for %s', mm.model.id)
                            
                            # Do nothing with dispatch_actions
                            rval['prequeue_model_run'] = model_prequeue_patch
                        
                        rval['interval_action_user'] = len(queue_action_user) == 0
                        return rval
                
                case 'result_update_interface_request':
                    mm = cast(NewsegsMetaModel, app.metamodels.get(action['metamodel_id']))
                    if mm is None:
                        raise ValueError(f'metamodel {action['metamodel_id']} could not be recovered.')
                    if not mm.model.checked_out and not mm.finance.checked_out:
                        dispatch_actions = find_matching_actions(
                            queue_action_user,
                            action,
                            i,
                            'result_update_interface_request'
                        )
                        logger.info('dispatching %d result update interface requests', len(dispatch_actions))

                        mrr = browser.model_run_request(
                            mm.id,
                            mm.model.id,
                            mm.model.last_run
                        )
                        frr = browser.finance_run_request(
                            mm.id,
                            mm.finance.id,
                            mm.model.id,
                            mm.finance.last_run
                        )

                        rval['trigger_postprocess_model_run'] = mrr
                        rval['trigger_postprocess_finance_run'] = frr
                        rval['interval_action_user'] = len(queue_action_user) == 0 
                        return rval

                case 'dsa_impacting_interface_action':
                    # Simply dispatch this onwards for the dispatcher to handle
                    # - We don't want to over-clutter the interface for the queue
                    # manager.
                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'dsa_impacting_interface_action'
                    )
                    rval['dispatchitem_action_user'] = dispatch_actions

                case 'psa_impacting_interface_action':
                    # As per DSA impacting actions, simply dispatch
                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'psa_impacting_interface_action'
                    )
                    rval['dispatchitem_action_user'] = dispatch_actions

                case 'dsa-run-request':
                    mm = cast(NewsegsMetaModel, app.metamodels.get(action['metamodel_id']))
                    if mm.model.checked_out or mm.finance.checked_out:
                        continue

                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'dsa-run-request'
                    )
                    logger.info('dispatching %d dsa run requests', len(dispatch_actions))

                    # Requests go straight out to the metamodel process
                    metamodel_prequeue_patch = Patch()
                    metamodel_prequeue_patch.append(dispatch_actions[0])

                    rval['prequeue_metamodel_process'] = metamodel_prequeue_patch
                    rval['interval_action_user'] = len(queue_action_user) == 0
                    return rval
                
                case 'psa-run-request':
                    mm = cast(NewsegsMetaModel, app.metamodels.get(action['metamodel_id']))
                    if mm.model.checked_out or mm.finance.checked_out:
                        continue

                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'psa-run-request'
                    )
                    logger.info('dispatching %d psa run requests', len(dispatch_actions))

                    # Requests go straight out to the metamodel process
                    metamodel_prequeue_patch = Patch()
                    metamodel_prequeue_patch.append(dispatch_actions[0])

                    rval['prequeue_metamodel_process'] = metamodel_prequeue_patch
                    rval['interval_action_user'] = len(queue_action_user) == 0
                    return rval

                case _:
                    raise ValueError(f'action type not recognised: {action['type']}')
        
        rval['interval_action_user'] = len(queue_action_user) == 0
        return rval
    
    @app.callback(
        Output({'type': 'trigger', 'page': ALL, 'key': ALL}, 'data', allow_duplicate = True),

        Input('dispatchitem-action-user', 'data'),
        State({'type': 'trigger', 'page': ALL, 'key': ALL}, 'id'),
        prevent_initial_call = True
    )
    def dispatcher_action_user(
        dispatchitems,
        trigger_ids
    ):
        """
        Acts as a simple postman; goes through the list of triggers it has
        access to, and checks them against the dispatchitems. It gathers up
        matching items, and then puts them in the data for the appropriate
        trigger.
        Callbacks watching for specific triggers (i.e. without the wildcard 
        'key') are expected to pick up from here and complete the action.
        """
        if trigger_ids is None:
            return 
        rval: NoUpdate|list[Any] = [no_update] * len(trigger_ids)

        for i, trig_id in enumerate(trigger_ids):
            for itm in dispatchitems:
                if trig_id['key'] == json.loads(itm).get('action_key', 'None'):
                    if isinstance(rval[i], NoUpdate):
                        rval[i] = []
                    rval[i].append(itm)
                    logger.info('adding %s to %s', itm, trig_id)

        return tuple(rval)

    return app
