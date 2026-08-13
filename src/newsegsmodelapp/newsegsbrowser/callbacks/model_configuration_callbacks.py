"""

Functions:
- add_initial_callbacks
- add_model_to_interface_callbacks
- add_feedback_callbacks
- add_interface_to_model_callbacks
"""

import copy
import datetime
import json
import logging
import time
from typing import Any, Sequence, cast

from dash import ALL, NoUpdate, ctx, Dash, Input, Output, Patch, State, no_update
from dash import clientside_callback, ClientsideFunction
import numpy as np
from useful_types import SequenceNotStr

from newsegsmodelapp.newsegsbrowser import common as browser
from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager
from newsegsmodelapp.newsegsbrowser.callbacks import callbacks_map
from newsegsmodelapp.newsegsbrowser.callbacks.locks import ok_run_model, ok_run_finance
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel, make_varid

logger = logging.getLogger(__name__)

SYNC_DEBOUNCE_SECONDS = 0.1

def add_initial_callbacks(app: Dash, acm: NewsegsBrowserCacheManager):
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

def add_model_to_interface_callbacks(app: Dash, acm: NewsegsBrowserCacheManager):
    """
    Callbacks for passing model configuration data to the interface
    """

    # Trigger on first load, whenever a configuration is changed extrinsically
    # (i.e. loaded, duplicated) and whenever the selected configuration is
    # changed.
    @app.callback(
        output = dict(
            selected_configuration = Output('store-selected-configuration', 'data', allow_duplicate = True),
            configurations = Output('store-configurations', 'data', allow_duplicate = True),
            
            input_container_children = Output(
                {'type': 'input-container', 'supersection': ALL, 'section': ALL},
                'children'
            ),
            metamodel_input_container_children = Output(
                {'type': 'metamodel-input-container', 'supersection': ALL, 'section': ALL},
                'children'
            ),
            generic_text_children = Output(
                {'type': 'generic_text', 'section': ALL, 'key': ALL},
                'children'
            ),
            trigger_values = Output(
                {'type': 'trigger', 'page': ALL, 'key': ALL},
                'data', 
                allow_duplicate = True
            ),
            config_name_inputs = dict(
                values = Output({'type':'config-name-input', 'index': ALL}, 'value')
            ),

            prequeue_action_user = Output('prequeue-action-user', 'data', allow_duplicate = True),
        ),

        inputs = dict(
            firstload_config_watchers = Input(
                {'type' : 'firstload-config-watcher', 'selected_model': ALL, 'page_type': ALL},
                'data'
            ),

            selected_configuration = Input('store-selected-configuration', 'data'),
            configurations = Input('store-configurations', 'data'),
        ),

        state = dict(
            prequeue_locks = dict(
                ids = State(
                    {'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL},
                    'id'
                ),
                values = State(
                    {'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL},
                    'data'
                ),
            ),

            input_container_ids = State(
                {'type': 'input-container', 'supersection': ALL, 'section': ALL},
                'id'
            ),

            metamodel_input_container_ids = State(
                {'type': 'metamodel-input-container', 'supersection': ALL, 'section': ALL},
                'id'
            ),

            generic_text_ids = State(
                {'type': 'generic_text', 'section': ALL, 'key': ALL},
                'id'
            ),

            trigger_ids = State(
                {'type': 'trigger', 'page': ALL, 'key': ALL},
                'id'
            ),

            config_name_inputs = dict(
                ids = State({'type':'config-name-input', 'index': ALL}, 'id'),
                values = State({'type':'config-name-input', 'index': ALL}, 'value'),
            ),

            selected_model = State('selected-model', 'data'),
        ),
        prevent_initial_call=True
    )
    def sync_config(
        firstload_config_watchers,
        selected_configuration,
        configurations,
        prequeue_locks,
        input_container_ids,
        metamodel_input_container_ids,
        generic_text_ids,
        trigger_ids,
        config_name_inputs,
        selected_model,
    ):
        logger.info('sync_config triggered by %s', ctx.triggered_id)
        null_rval: dict[str, Any] = dict(
            selected_configuration = no_update,
            configurations = no_update,

            input_container_children = [no_update] * len(input_container_ids),
            metamodel_input_container_children = [no_update] * len(metamodel_input_container_ids),
            generic_text_children = [no_update] * len(generic_text_ids),
            trigger_values = [no_update] * len(trigger_ids),
            config_name_inputs = dict(values=[no_update]*len(config_name_inputs['ids'])),

            prequeue_action_user = no_update
        )
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_config'](
            firstload_config_watchers,
            selected_configuration,
            configurations,
            prequeue_locks,
            input_container_ids,
            metamodel_input_container_ids,
            generic_text_ids,
            trigger_ids,
            config_name_inputs,
            null_rval,
            acm
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
        logger.info('sync_loc_inputs_to_store triggered by %s', ctx.triggered_id)
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_loc_inputs_to_store'](
            selected_configuration,
            acm
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
            acm
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
            acm
        )
    
    return app
    
def add_feedback_callbacks(app, acm: NewsegsBrowserCacheManager):
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
            acm
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
            acm
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
            acm
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
            acm
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
            acm
        )

    return app


def add_interface_to_model_callbacks(app, acm: NewsegsBrowserCacheManager):
    """
    Callbacks for when a user changes a model or finance config input.
    """

    _MESSAGES = {
        'deterministic_changed': 'Model input parameters have been modified',
        'dsa_changed': 'DSA not run for current parameters',
        'psa_changed': 'PSA not run for current parameters',
    }

    @app.callback(
        output = dict(
            prequeue_action_user = Output('prequeue-action-user', 'data', allow_duplicate = True),

            config_inputs = dict(
                model = dict(
                    values = Output(
                        {'type': 'input-model-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'value'
                    ),
                    invalids = Output(
                        {'type': 'input-model-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'invalid', allow_duplicate = True
                    ),
                ),
                finance = dict(
                    values = Output(
                        {'type': 'input-finance-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'value', allow_duplicate = True
                    ),
                    invalids = Output(
                        {'type': 'input-finance-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'invalid'
                    ),
                )
            ),
            config_triggers = dict(
                model = dict(
                    values = Output(
                        {'type': 'trigger', 'page': ALL, 'key': 'model-config'},
                        'data',
                        allow_duplicate = True
                    )
                ),
                finance = dict(
                    values = Output(
                        {'type': 'trigger', 'page': ALL, 'key': 'finance-config'},
                        'data',
                        allow_duplicate = True
                    ),
                )
            ),
            result_indicator_values = dict(
                bars = Output(
                    {'type': 'resize-handle', 'page': ALL},
                    'className',
                    allow_duplicate = True,
                ),
                tooltips = Output(
                    {'type': 'result-tooltip', 'page': ALL},
                    'children',
                    allow_duplicate = True,
                )
            ),
        ),

        inputs = dict(
            config_inputs = dict(
                model = dict(
                    ids = State(
                        {'type': 'input-model-config', 'section': ALL, 'key': ALL,
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'id'
                    ),
                    values = Input(
                        {'type': 'input-model-config', 'section': ALL, 'key': ALL,
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'value'
                    ),
                ),
                finance = dict(
                    ids = State(
                        {'type': 'input-finance-config', 'section': ALL, 'key': ALL,
                         'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'id'
                    ),
                    values = Input(
                        {'type': 'input-finance-config', 'section': ALL, 'key': ALL,
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'value'
                    ),
                )
            ),
            locks = dict(
                ids = State(
                    {'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL},
                    'id'
                ),
                values = State(
                    {'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL},
                    'data'
                ),
            )
        ),

        state = dict(
            config_triggers = dict(
                model = dict(
                    ids = State(
                        {'type': 'trigger', 'page': ALL, 'key': 'model-config'},
                        'id'
                    ),
                ),
                finance = dict(
                    ids = State(
                        {'type': 'trigger', 'page': ALL, 'key': 'finance-config'},
                        'id'
                    ),
                ),
            ),

            result_indicator_ids = dict(
                bars = State(
                    {'type': 'resize-handle', 'page': ALL},
                    'id'
                ),
                tooltips = State(
                    {'type': 'result-tooltip', 'page': ALL},
                    'id'
                ),
            ),

            selected_configuration = State('store-selected-configuration', 'data'),
        ),

        prevent_initial_call=True
    )
    def interface_update_config(
        config_inputs,
        locks,
        config_triggers,
        selected_configuration,
        result_indicator_ids,
    ):
        """
        Add model configuration update events to the user action prequeue.

        May be fired before the queuemanager absorbs the prequeue, so needs
        to ensure that the prequeue is appended, not overwritten.
        In future, we may see if we can do this with a Patch - not sure how the
        data are held, and it may be that we can just append a list rather than
        full json deserialise/serialise.
        """
        rval: dict[str, Any] = dict(
            prequeue_action_user = no_update,

            config_inputs = dict(
                model = dict(
                    values = [no_update] * len(config_inputs['model']['ids']),
                    invalids = [no_update] * len(config_inputs['model']['ids']),
                ),
                finance = dict(
                    values = [no_update] * len(config_inputs['finance']['ids']),
                    invalids = [no_update] * len(config_inputs['finance']['ids']),
                )
            ),

            config_triggers = dict(
                model = dict(
                    values = [no_update] * len(config_triggers['model']['ids'])
                ),
                finance = dict(
                    values = [no_update] * len(config_triggers['finance']['ids'])
                )
            ),
            
            result_indicator_values = dict(
                bars = [no_update] * len(result_indicator_ids['bars']),
                tooltips = [no_update] * len(result_indicator_ids['tooltips']),
            ),
        )
        
        selected_configuration = json.loads(selected_configuration)
        selected_mm = selected_configuration.get('metamodel_id')
        if selected_mm is None:
            return rval
        selected_mm = cast(NewsegsMetaModel, acm.metamodels.get(selected_mm))
        if selected_mm is None:
            return rval

        prequeue_patch = Patch()
        prequeue = []
        
        logger.info('configuration input field changed')

        model_changed = False
        finance_changed = False

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']
            update_ok, deterministic_changed, dsa_changed, psa_changed, raw_params = selected_mm.update_variable_from_interface(
                pid['section'], pid['key'], pid['subindex'], pid['parameter_index'], pid['vector_location'], val
            )

            actargs = pid.copy()
            actargs.pop('type', None)

            match pid['type']:
                case 'input-model-config':
                    for i, id in enumerate(config_inputs['model']['ids']):
                        if (
                            id['section'] == pid['section']
                            and id['key'] == pid['key']
                            and id['subindex'] == pid['subindex']
                        ):
                            # Set model input invalid if bad update
                            if (
                                id['parameter_index'] == pid['parameter_index'] 
                                and id['vector_location'] == pid['vector_location']
                            ):
                                rval['config_inputs']['model']['invalids'][i] = not(update_ok)
                            
                            # Feed back the current parameters. This is necessary in case e.g. setting the mean required a change in the SD to make the distribution tractable.
                            pi = id['parameter_index']
                            new_param = raw_params[pi]
                            if not isinstance(new_param, np.ndarray):
                                rval['config_inputs']['model']['values'][i] = new_param
                            else:
                                vi = id['vector_location']
                                new_val = new_param.flat[vi]
                                rval['config_inputs']['model']['values'][i] = new_val
                    
                    if deterministic_changed:
                        print(f'CHANGED - {pid['section']}.{pid['key']}.{pid['subindex']} value - {val}')
                        
                        model_changed = True
                        action = browser.metamodel_variable_sync_action(
                            metamodel_id = selected_mm.id,
                            debounce = False,
                            **actargs
                        )
                        prequeue.append(
                            json.dumps(
                                action.as_dict()
                            )
                        )
                    
                        # Trigger a change on all pages
                        rval['config_triggers']['model']['values'] = (
                            [datetime.datetime.now().timestamp()] 
                            * len(config_triggers['model']['ids'])
                        )
                        # Indicate results invalid across all pages
                        rval['result_indicator_values']['bars'] = ['resize-handle resize-handle-warning'] * len(result_indicator_ids['bars'])
                        rval['result_indicator_values']['tooltips'] = [_MESSAGES.get('deterministic_changed')] * len(result_indicator_ids['tooltips'])
                case 'input-finance-config':
                    for i, id in enumerate(config_inputs['finance']['ids']):
                        if (
                            id['section'] == pid['section']
                            and id['key'] == pid['key']
                            and id['subindex'] == pid['subindex']
                        ):
                            # Set finance input invalid if bad update
                            if (
                                id['parameter_index'] == pid['parameter_index'] 
                                and id['vector_location'] == pid['vector_location']
                            ):
                                rval['config_inputs']['finance']['invalids'][i] = not(update_ok)
                            
                            # Feed back the current parameters. This is necessary in case e.g. setting the mean required a change in the SD to make the distribution tractable.
                            pi = id['parameter_index']
                            new_param = raw_params[pi]
                            if not isinstance(new_param, np.ndarray):
                                rval['config_inputs']['finance']['values'][i] = new_param
                            else:
                                vi = id['vector_location']
                                new_val = new_param.flat[vi]
                                rval['config_inputs']['finance']['values'][i] = new_val

                    if deterministic_changed:
                        print(f'CHANGED - {pid['section']}.{pid['key']}.{pid['subindex']} value - {val}')
                        # Need to check if model results are available
                        # If not, add a model run and allow that to trigger
                        # finance
                        action = browser.metamodel_variable_sync_action(
                            metamodel_id = selected_mm.id,
                            debounce = False,
                            **actargs
                        )
                        prequeue.append(
                            json.dumps(
                                action.as_dict()
                            )
                        )
                        
                        rval['config_triggers']['finance']['values'] = (
                            [datetime.datetime.now().timestamp()] 
                            * len(config_triggers['finance']['ids'])
                        )

                        # Indicate results invalid across all pages
                        rval['result_indicator_values']['bars'] = ['resize-handle resize-handle-warning'] * len(result_indicator_ids['bars'])
                        rval['result_indicator_values']['tooltips'] = [_MESSAGES.get('deterministic_changed')] * len(result_indicator_ids['tooltips'])
                case _:
                    raise ValueError('Triggered by an unknown input type %s', pid['type'])
                
            if dsa_changed:
                action = browser.dsa_impacting_interface_action(
                    metamodel_id = selected_mm.id,
                    **actargs
                )
                prequeue.append(
                    json.dumps(
                        action.as_dict()
                    )
                )

                # Indicate results invalid on dsa page
                for idx, barid in enumerate(result_indicator_ids['bars']):
                    if barid.get('page') == 'dsa':
                        rval['result_indicator_values']['bars'][idx] = 'resize-handle resize-handle-warning'
                for idx, ttid in enumerate(result_indicator_ids['tooltips']):
                    if ttid.get('page') == 'dsa':
                        rval['result_indicator_values']['tooltips'][idx] = _MESSAGES.get('dsa_changed')


            if psa_changed:
                action = browser.psa_impacting_interface_action(
                    metamodel_id = selected_mm.id,
                    **actargs
                )
                prequeue.append(
                    json.dumps(
                        action.as_dict()
                    )
                )

                # Indicate results invalid on psa page
                for idx, barid in enumerate(result_indicator_ids['bars']):
                    if barid.get('page') == 'psa':
                        rval['result_indicator_values']['bars'][idx] = 'resize-handle resize-handle-warning'
                for idx, ttid in enumerate(result_indicator_ids['tooltips']):
                    if ttid.get('page') == 'psa':
                        rval['result_indicator_values']['tooltips'][idx] = _MESSAGES.get('psa_changed')

        l2 = len(prequeue)

        if not prequeue:
            return rval

        if model_changed and finance_changed:
            logger.info('model and finance configuration changes have added %d items to prequeue, which is now %d items long', l2, l2)
        elif model_changed:
            logger.info('model configuration changes have added %d items to prequeue, which is now %d items long', l2, l2)
        elif finance_changed:
            logger.info('finance configuration changes have added %d items to prequeue, which is now %d items long', l2, l2)
            for item in prequeue:
                logger.info(str(item))
        else:
            logger.info('no changes to prequeue, which is %d items long: %s', l2, prequeue)   
        
        prequeue_patch.extend(prequeue)
        
        rval['prequeue_action_user'] = prequeue_patch
        return rval
    
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
        mm = cast(NewsegsMetaModel, acm.metamodels.get(selected_config.get('metamodel_id')))
        if mm is None:
            return tuple(rval)
        
        prequeue_patch = Patch()
        logger.info('dsa input field changed')

        forward_prequeue = False

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']

            varid = make_varid(**pid)
            var = mm.variables.get(varid)
            if var is None:
                continue

            actargs = pid.copy()
            actargs.pop('type', None)

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
                        
                        action = browser.dsa_impacting_interface_action(
                            metamodel_id = mm.id,
                            bounds_type_change = True,
                            **actargs
                        )
                        prequeue_patch.append(
                            json.dumps(
                                action.as_dict()
                            )
                        )
                        forward_prequeue = True
                case 'input-dsabound-lower':
                    if val is None:
                        continue
                    if not val == var.dsa_lower:
                        var.dsa_lower = val
                        action = browser.dsa_impacting_interface_action(
                            metamodel_id = mm.id,
                            **actargs
                        )
                        prequeue_patch.append(
                            json.dumps(
                                action.as_dict()
                            )
                        )
                        
                        forward_prequeue = True
                case 'input_dsabound-upper':
                    if val is None:
                        continue
                    if not val == var.dsa_upper:
                        var.dsa_upper = val

                        action = browser.dsa_impacting_interface_action(
                            metamodel_id = mm.id,
                            **actargs
                        )
                        prequeue_patch.append(
                            json.dumps(
                                action.as_dict()
                            )
                        )
                        forward_prequeue = True
                case 'toggle-dsa-variable':
                    if val is None:
                        continue
                    if not val == var.dsa_selected:
                        var.dsa_selected = val
                        action = browser.dsa_impacting_interface_action(
                            metamodel_id = mm.id,
                            selected_status_change = True
                            **actargs
                        )
                        prequeue_patch.append(
                            json.dumps(
                                action.as_dict()
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
        mm = cast(NewsegsMetaModel, acm.metamodels.get(selected_config.get('metamodel_id')))
        if mm is None:
            return rval
        
        prequeue_patch = Patch()
        logger.info('psa input field changed')

        forward_prequeue = False

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']

            varid = make_varid(**pid)
            var = mm.variables.get(varid)
            if var is None:
                continue

            actargs = pid.copy()
            actargs.pop('type', None)

            match pid['type']:
                case 'toggle-psa-variable':
                    if val is None:
                        continue
                    if not val == var.psa_selected:
                        var.psa_selected = val

                        action = browser.psa_impacting_interface_action(
                            metamodel_id = mm.id,
                            selected_status_change = True,
                            **actargs
                        )
                        prequeue_patch.append(
                            json.dumps(
                                action.as_dict()
                            )
                        )
                        
                        forward_prequeue = True
        
        if forward_prequeue:
            rval = prequeue_patch

        return rval

    #### Reset parameters #####
    @app.callback(
        output = dict(
            config_inputs = dict(
                model = dict(
                    values = Output(
                        {'type': 'input-model-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'value', allow_duplicate = True
                    ),
                ),
                finance = dict(
                    values = Output(
                        {'type': 'input-finance-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'value', allow_duplicate = True
                    ),
                )
            ),
        ),

        inputs = dict(
            reset_button = dict(
                n_clicks = Input(
                    {'type': 'value-reset-button', 'section': ALL, 'key': ALL, 
                    'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'n_clicks'
                ),
                ids = State(
                    {'type': 'value-reset-button', 'section': ALL, 'key': ALL, 
                    'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                )
            )
        ),

        state = dict(
            config_inputs = dict(
                model = dict(
                    ids = State(
                        {'type': 'input-model-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'id'
                    ),
                ),
                finance = dict(
                    ids = State(
                        {'type': 'input-finance-config', 'section': ALL, 'key': ALL, 
                        'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                        'id'
                    ),
                )
            ),
            selected_configuration = State('store-selected-configuration', 'data'),
        ),

        prevent_initial_call = True
    )
    def reset_parameter(
        reset_button,
        config_inputs,
        selected_configuration
    ):
        rval = dict(
            config_inputs = dict(
                model = dict(
                    values = [no_update] * len(config_inputs['model']['ids'])
                ),
                finance = dict(
                    values = [no_update] * len(config_inputs['finance']['ids'])
                ),
            )
        )
        val = browser.get_triggered_value()
        if val is None:
            return rval

        tid = cast(dict[str,Any], ctx.triggered_id)
        logger.info('resetting variable to default: %s', tid)

        mm = acm.metamodels.get(json.loads(selected_configuration).get('metamodel_id'))
        if mm is None:
            return rval
        varid = make_varid(**tid)
        var = mm.variables.get(varid)
        if var is None:
            return rval

        reset_value = var._default_parameters[tid.get('parameter_index', 0)]
        model_search_id = copy.copy(tid)
        model_search_id.update({'type': 'input-model-config'})
        finance_search_id = copy.copy(tid)
        finance_search_id.update({'type': 'input-finance-config'})
        did_update = (
            browser.update_return_list(
                model_search_id, reset_value, 
                config_inputs['model']['ids'], rval['config_inputs']['model']['values']
            ) or browser.update_return_list(
                finance_search_id, reset_value, 
                config_inputs['finance']['ids'], rval['config_inputs']['finance']['values']
            )
        )

        if not did_update:
            # We're assuming that an interface update will fire around to updating the metamodel
            # If there is no update, we must update the metamodel ourselves
            var.reset_parameters(tid.get('parameter_index', 0))

        return rval

    #### Set default #####
    @app.callback(
        inputs = dict(
            set_default_button = dict(
                n_clicks = Input(
                    {'type': 'value-set-default-button', 'section': ALL, 'key': ALL, 
                    'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'n_clicks'
                ),
                ids = State(
                    {'type': 'value-set-default-button', 'section': ALL, 'key': ALL, 
                    'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                )
            )
        ),

        state = dict(
            selected_configuration = State('store-selected-configuration', 'data'),
        ),

        prevent_initial_call = True
    )
    def set_default(
        set_default_button,
        selected_configuration
    ):
        rval = None
        val = browser.get_triggered_value()
        if val is None:
            return rval

        tid = cast(dict[str,Any], ctx.triggered_id)
        
        mm = acm.metamodels.get(json.loads(selected_configuration).get('metamodel_id'))
        if mm is None:
            return rval
        varid = make_varid(**tid)
        var = mm.variables.get(varid)
        if var is None:
            return rval

        logger.info('setting new default: %s', tid)
        var.replace_default_parameters()

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

            result_indicator_values = dict(
                bars = Output(
                    {'type': 'resize-handle', 'page': ALL},
                    'className'
                ),
                tooltips = Output(
                    {'type': 'result-tooltip', 'page': ALL},
                    'children'
                )
            ),

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
            result_indicator_ids = dict(
                bars = State(
                    {'type': 'resize-handle', 'page': ALL},
                    'id'
                ),
                tooltips = State(
                    {'type': 'result-tooltip', 'page': ALL},
                    'id'
                ),
            )
        ),
        prevent_initial_call = True
    )
    def queueman_action_user(
        prequeue_action_user, 
        interval_action_user,

        prequeue_lock_ids,
        prequeue_lock_values,
        result_indicator_ids,
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
        logger.info('processing user action queue, triggered by: %s', ctx.triggered_id)

        rval: dict[str, Any] = dict(
            prequeue_action_user = no_update,

            prequeue_model_run = no_update,
            prequeue_finance_run = no_update,
            prequeue_metamodel_process = no_update,

            trigger_postprocess_model_run = no_update,
            trigger_postprocess_finance_run = no_update,

            result_indicator_values = dict(
                bars = [no_update] * len(result_indicator_ids['bars']),
                tooltips = [no_update] * len(result_indicator_ids['tooltips']),
            ),

            dispatchitem_action_user = no_update,
            interval_action_user = no_update
        )

        queue_action_user = acm.sts.get('queue-action-user')
        if queue_action_user is None:
            acm.sts['queue-action-user'] = []
            queue_action_user = acm.sts['queue-action-user']

        if ctx.triggered_id == 'prequeue-action-user':
            action = prequeue_action_user
            
            if isinstance(action, list):
                logger.info('handling %d user actions: %s', len(action), action)
                queue_action_user += action
            else:
                logger.info('handling single user action')
                queue_action_user.append(action)
            
            # TODO: Rationalise queue
            rval['prequeue_action_user'] = []

        nowtime = time.time()

        # The actual dispatch queue is held in the sts to prevent overwrites
        dispatched_action_user = acm.sts.get('dispatched-action-user')
        if dispatched_action_user is None:
            acm.sts['dispatched-action-user'] = []
            dispatched_action_user = acm.sts['dispatched-action-user']

        # If the user action queue hasn't been handled, let's just trigger it again and wait until it is
        if len(dispatched_action_user) != 0:
            rval['dispatchitem_action_user'] = nowtime
            rval['interval_action_user'] = len(queue_action_user) == 0 
            return rval

        # As there are multiple exits from this function, it is not as trivial to ensure that
        # we avoid overwriting a dispatch. 
        # May need to re-write the flow again.
        #acm_dispatch = acm.sts.get('dispatchitem-action-user')

        # Loop through action queue
        for i, action_json in enumerate(queue_action_user):
            action = json.loads(action_json)
            logger.info('queueman_action_user processing action: %s', action)
            match action['type']:
                case 'metamodel_variable_sync_action':
                    if not(action['debounce']) or (nowtime - action['time']) > SYNC_DEBOUNCE_SECONDS:
                        mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
                        logger.info('Checking if model %s is checked out: %s', mm.model.id, mm.model.checked_out)
                        logger.info('Checking if finance %s is checked out: %s', mm.finance.id, mm.finance.checked_out)
                        if not mm.model.checked_out and not mm.finance.checked_out:
                            # NB - this function has side effect of popping matches from queue_action_user
                            dispatch_actions = find_matching_actions(
                                queue_action_user,
                                action,
                                i,
                                'metamodel_variable_sync_action'
                            )

                            # Only need to run from the first to ensure we get them all
                            models_affected = mm.sync_model_with_changed_variables_deterministic()
                            if 'model' in models_affected:
                                # Model will be dirty. If ok to, add to queue.
                                if ok_run_model(prequeue_lock_ids, prequeue_lock_values):
                                    r_model_run_request = browser.model_run_request(
                                        metamodel_id = mm.id, 
                                        model_id = mm.model.id
                                    )
                                    model_prequeue_patch = Patch()
                                    model_prequeue_patch.append(json.dumps(r_model_run_request.as_dict()))

                                    logger.info('queueman_action_user adding a model run request for %s', mm.model.id)
                                    rval['prequeue_model_run'] = model_prequeue_patch
                            elif 'finance' in models_affected:
                                if ok_run_finance(prequeue_lock_ids, prequeue_lock_values):
                                    r_finance_run_request = browser.finance_run_request(
                                        metamodel_id = mm.id,
                                        finance_id = mm.finance.id, 
                                        model_id = mm.model.id
                                    )
                                    finance_prequeue_patch = Patch()
                                    finance_prequeue_patch.append(json.dumps(r_finance_run_request.as_dict()))

                                    logger.info('queueman_action_user adding a finance run request for %s', mm.finance.id)
                                    rval['prequeue_finance_run'] = finance_prequeue_patch
                            
                            rval['interval_action_user'] = len(queue_action_user) == 0
                            return rval

                case 'model_config_interface_update':
                    logger.warning('model_config_interface_update - deprecated')
                    if not(action['debounce']) or (nowtime - action['time']) > SYNC_DEBOUNCE_SECONDS:
                        mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
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
                                varid = make_varid(**action)
                                if varid not in synced:
                                    mm.update_model_from_variable_deterministic(
                                        action['section'],
                                        action['key'],
                                        action['subindex']
                                    )
                                    synced.append(varid)

                            if ok_run_model(prequeue_lock_ids, prequeue_lock_values):
                                r_model_run_request = browser.model_run_request(
                                    metamodel_id = mm.id, 
                                    model_id = mm.model.id
                                )
                                model_prequeue_patch = Patch()
                                model_prequeue_patch.append(json.dumps(r_model_run_request.as_dict()))

                                logger.info('queueman_action_user adding a run request for %s', mm.model.id)

                                # Do nothing with dispatch_actions
                                rval['prequeue_model_run'] = model_prequeue_patch
                            
                            rval['interval_action_user'] = len(queue_action_user) == 0
                            return rval

                case 'finance_config_interface_update':
                    logger.warning('finance_config_interface_update - deprecated')
                    if not(action['debounce']) or (nowtime - action['time']) > SYNC_DEBOUNCE_SECONDS:
                        mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
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
                                varid = make_varid(**action)
                                if varid not in synced:
                                    mm.update_model_from_variable_deterministic(
                                        action['section'],
                                        action['key'],
                                        action['subindex']
                                    )
                                    synced.append(varid)

                            if ok_run_finance(prequeue_lock_ids, prequeue_lock_values):
                                r_finance_run_request = browser.finance_run_request(
                                    metamodel_id = mm.id,
                                    finance_id = mm.finance.id, 
                                    model_id = mm.model.id
                                )
                                finance_prequeue_patch = Patch()
                                finance_prequeue_patch.append(json.dumps(r_finance_run_request.as_dict()))

                                logger.info('queueman_action_user adding a finance run request for %s', mm.finance.id)

                                # Do nothing with dispatch_actions
                                rval['prequeue_finance_run'] = finance_prequeue_patch
                            
                            rval['interval_action_user'] = len(queue_action_user) == 0
                            return rval
                        
                case 'model_run_request':
                    # No debounce on a model run request
                    mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
                    if mm is None:
                        raise ValueError(f'metamodel {action['metamodel_id']} could not be recovered.')
                    if not mm.model.checked_out:

                        # NB - this function has side effect of popping matches from queue_action_user
                        dispatch_actions = find_matching_actions(
                            queue_action_user,
                            action,
                            i,
                            'model_run_request'
                        )
                        logger.info('dispatching %d model run requests', len(dispatch_actions))

                        if ok_run_model(prequeue_lock_ids, prequeue_lock_values):

                            # Nothing to do but to make the request with the first action
                            r_model_run_request = dispatch_actions[0] # browser.model_run_request(mm.id, mm.model.id)
                            model_prequeue_patch = Patch()
                            model_prequeue_patch.append(r_model_run_request)

                            logger.info('queueman_action_user adding a run request for %s', mm.model.id)
                            
                            # Do nothing with dispatch_actions
                            rval['prequeue_model_run'] = model_prequeue_patch
                        
                        rval['interval_action_user'] = len(queue_action_user) == 0
                        return rval
                
                case 'result_update_request':
                    mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
                    if mm is None:
                        raise ValueError(f'metamodel {action['metamodel_id']} could not be recovered.')
                    if not mm.model.checked_out and not mm.finance.checked_out:
                        dispatch_actions = find_matching_actions(
                            queue_action_user,
                            action,
                            i,
                            'result_update_request'
                        )
                        logger.info('queueman_action_user dispatching %d result update requests', len(dispatch_actions))

                        mrr = browser.model_run_request(
                            metamodel_id = mm.id,
                            model_id = mm.model.id,
                            time = mm.model.last_run,
                            debounce = False
                        )
                        frr = browser.finance_run_request(
                            metamodel_id = mm.id,
                            finance_id = mm.finance.id,
                            model_id = mm.model.id,
                            time = mm.finance.last_run,
                            debounce = False
                        )

                        rval['trigger_postprocess_model_run'] = json.dumps(mrr.as_dict())
                        rval['trigger_postprocess_finance_run'] = json.dumps(frr.as_dict())
                        rval['interval_action_user'] = len(queue_action_user) == 0 
                        return rval

                case 'dsa_impacting_interface_action':
                    # Simply dispatch this onwards for the dispatcher to handle
                    # - We don't want to over-clutter the interface for the queue
                    # manager.
                    
                    # Skip if the dispatch queue hasn't been handled yet
                    if len(dispatched_action_user) > 0:
                        logger.info('not dispatching dsa interface action as dispatch queue is: %s', dispatched_action_user)
                        rval['dispatchitem_action_user'] = datetime.datetime.now().timestamp()
                        continue

                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'dsa_impacting_interface_action'
                    )
                    dispatched_action_user.extend(dispatch_actions)
                    logger.info('dispatching %s dsa actions: %s', len(dispatch_actions), dispatch_actions)
                    rval['dispatchitem_action_user'] = datetime.datetime.now().timestamp()#dispatch_actions
                    rval['interval_action_user'] = len(queue_action_user) == 0
                    return rval

                case 'psa_impacting_interface_action':
                    # As per DSA impacting actions, simply dispatch

                    # Skip if the dispatch queue hasn't been handled yet
                    if len(dispatched_action_user) > 0:
                        logger.info('not dispatching psa interface action as dispatch queue is: %s', dispatched_action_user)
                        rval['dispatchitem_action_user'] = datetime.datetime.now().timestamp()
                        continue

                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'psa_impacting_interface_action'
                    )
                    dispatched_action_user.extend(dispatch_actions)
                    logger.info('dispatching psa actions: %s', dispatch_actions)
                    rval['dispatchitem_action_user'] = datetime.datetime.now().timestamp()#dispatch_actions
                    rval['interval_action_user'] = len(queue_action_user) == 0 
                    return rval

                case 'dsa_run_request':
                    mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
                    if mm.model.checked_out or mm.finance.checked_out:
                        continue

                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'dsa_run_request'
                    )
                    logger.info('dispatching %d dsa run requests', len(dispatch_actions))

                    # Requests go straight out to the metamodel process
                    metamodel_prequeue_patch = Patch()
                    metamodel_prequeue_patch.append(dispatch_actions[0])

                    rval['prequeue_metamodel_process'] = metamodel_prequeue_patch
                    rval['interval_action_user'] = len(queue_action_user) == 0
                    return rval
                
                case 'psa_run_request':
                    mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
                    if mm.model.checked_out or mm.finance.checked_out:
                        continue

                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'psa_run_request'
                    )
                    logger.info('dispatching %d psa run requests', len(dispatch_actions))

                    # Requests go straight out to the metamodel process
                    metamodel_prequeue_patch = Patch()
                    metamodel_prequeue_patch.append(dispatch_actions[0])

                    rval['prequeue_metamodel_process'] = metamodel_prequeue_patch
                    rval['interval_action_user'] = len(queue_action_user) == 0
                    return rval
                
                case 'optim_run_request':
                    mm = cast(NewsegsMetaModel, acm.metamodels.get(action['metamodel_id']))
                    if mm.model.checked_out or mm.finance.checked_out:
                        continue
                    dispatch_actions = find_matching_actions(
                        queue_action_user,
                        action,
                        i,
                        'optim_run_request'
                    )
                    logger.info('dispatching %d optim run requests', len(dispatch_actions))

                    # Requests go straight out to the metamodel process
                    metamodel_prequeue_patch = Patch()
                    metamodel_prequeue_patch.append(dispatch_actions[0])

                    rval['prequeue_metamodel_process'] = metamodel_prequeue_patch
                    rval['interval_action_user'] = len(queue_action_user) == 0
                    return rval

                case _:
                    raise ValueError(f'action type not recognised: {action['type']}')
            
            if not isinstance(rval['dispatchitem_action_user'], NoUpdate):
                # Exit now to ensure that only like actions are dispatched together
                rval['interval_action_user'] = len(queue_action_user) == 0
                return rval

        
        rval['interval_action_user'] = len(queue_action_user) == 0
        return rval
    
    @app.callback(
        Output({'type': 'trigger', 'page': ALL, 'key': ALL}, 'data', allow_duplicate = True),

        Input('dispatchitem-action-user', 'data'),
        State({'type': 'trigger', 'page': ALL, 'key': ALL}, 'id'),
        prevent_initial_call = True
    )
    def dispatcher_action_user(
        dispatchitem_trigger,
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

        # The actual dispatch queue is held in the sts to prevent overwrites
        dispatched_action_user = acm.sts.get('dispatched-action-user')
        if dispatched_action_user is None:
            acm.sts['dispatched-action-user'] = []
            dispatched_action_user = acm.sts['dispatched-action-user']

        for i, trig_id in enumerate(trigger_ids):
            for itm in dispatched_action_user:
                if trig_id['key'] == json.loads(itm).get('action_key', 'None'):
                    if isinstance(rval[i], NoUpdate):
                        rval[i] = []
                    rval[i].append(itm)
                    logger.info('adding %s to %s', itm, trig_id)
        
        dispatched_action_user.clear()

        return tuple(rval)

    return app
