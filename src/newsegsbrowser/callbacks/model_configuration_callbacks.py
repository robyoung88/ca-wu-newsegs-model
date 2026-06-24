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
from typing import Any, cast

from dash import ALL, NoUpdate, ctx, Dash, Input, Output, Patch, State, no_update
from dash import clientside_callback, ClientsideFunction
import numpy as np
from useful_types import SequenceNotStr

from newsegsbrowser import common as browser
from newsegsbrowser.callbacks import callbacks_map
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
        Output('post-drawer-attach', 'children'),
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
        Output({'type': 'trigger', 'page': ALL, 'key': ALL}, 'data', allow_duplicate = True),
        Output('prequeue-action-user', 'data', allow_duplicate = True),

        Input({'type' : 'firstload-config-watcher', 'selected_model': ALL, 'page_type': ALL}, 'data'),
        Input('store-selected-configuration', 'data'),
        Input('store-configurations', 'data'),
        State({'type': 'input-container', 'supersection': ALL, 'section': ALL}, 'id'),
        State({'type': 'trigger', 'page': ALL, 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_config(
        firstload_config_watcher,
        store_selected_configuration,
        store_configurations,
        input_containers,
        trigger_ids,
        selected_model
    ):
        logger.info('sync_config triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_config'](
            firstload_config_watcher,
            store_selected_configuration,
            store_configurations,
            input_containers,
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
        Input({'type': 'trigger', 'page': ALL, 'key': ALL}, 'data'),
        State('store-selected-configuration', 'data'),
        State({'type': 'input-header', 'section': 'finance-config', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_headers_finance_config(
        finance_config_trigger,
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
        #Input('model-config','data'), # Trying to suppress circular callbacks

        State('store-selected-configuration', 'data'),
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
            update_ok, deterministic_changed, raw_params = selected_mm.update_variable_from_interface(
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
                            if id['parameter_index'] == pid['parameter_index'] and id['vector_location'] == pid['vector_location']:
                                rval[3][i] = not(update_ok)  # type: ignore
                            pi = id['parameter_index']
                            new_param = raw_params[pi]
                            if not isinstance(new_param, np.ndarray):
                                rval[1][i] = new_param # type: ignore
                            else:
                                vi = id['vector_location']
                                new_val = new_param.flat[vi]
                                rval[1][i] = new_val # type: ignore
                    
                    if deterministic_changed:
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

        if l2 == l1:
            return NUP
        
        return prequeue
    
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
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        Output('queue-action-user', 'data'),
        Output('prequeue-model-run', 'data', allow_duplicate = True),
        Output('prequeue-finance-run', 'data', allow_duplicate = True),
        Output('trigger-postprocess-model-run', 'data', allow_duplicate = True),
        Output('trigger-postprocess-finance-run', 'data', allow_duplicate = True),
        #Output('dispatchitem-action-user', 'data'),
        Output('interval-action-user', 'disabled'),

        Input('prequeue-action-user', 'data'),
        Input('interval-action-user', 'n_intervals'),
        State('queue-action-user', 'data'),
        prevent_initial_call = True
    )
    def queueman_action_user(
        prequeue_action_user, 
        interval_action_user,
        queue_action_user,
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
        if not queue_action_user:
            queue_action_user = []

        logger.info('processing user action queue, triggered by: %s', ctx.triggered_id)
        
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

        rval = [
            [], # The prequeue is consumed
            queue_action_user,

            no_update, # run prequeues
            no_update,
            
            no_update, # postprocess triggers
            no_update,

            len(queue_action_user) == 0 # Disable Interval
        ]

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

                            r_model_run_request = browser.model_run_request(mm.id, mm.model.id)
                            model_prequeue_patch = Patch()
                            model_prequeue_patch.append(json.dumps(r_model_run_request))

                            logger.info('Adding a run request for %s', mm.model.id)

                            rval[2] = model_prequeue_patch
                            rval[1] = queue_action_user
                            rval[-1] = len(queue_action_user) == 0 # Disable Interval
                            return tuple(rval)

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

                            r_finance_run_request = browser.finance_run_request(mm.id, mm.finance.id, mm.model.id)
                            finance_prequeue_patch = Patch()
                            finance_prequeue_patch.append(json.dumps(r_finance_run_request))

                            logger.info('Adding a finance run request for %s', mm.finance.id)

                            rval[3] = finance_prequeue_patch
                            rval[1] = queue_action_user
                            rval[-1] = len(queue_action_user) == 0 # Disable Interval
                            return tuple(rval)
                        
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

                        # Nothing to do but to make the request with the first action
                        r_model_run_request = browser.model_run_request(mm.id, mm.model.id)
                        model_prequeue_patch = Patch()
                        model_prequeue_patch.append(json.dumps(r_model_run_request))

                        logger.info('Adding a run request for %s', mm.model.id)
                        
                        rval[2] = model_prequeue_patch
                        rval[1] = queue_action_user
                        rval[-1] = len(queue_action_user) == 0 # Disable Interval
                        return tuple(rval)
                
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

                        rval[4] = mrr
                        rval[5] = frr
                        rval[1] = queue_action_user
                        rval[-1] = len(queue_action_user) == 0 # Disable Interval
                        return tuple(rval)
                    
                case _:
                    raise ValueError(f'action type not recognised: {action['type']}')
        
        # Fall-through - do not update dispatchitem-action-user
        rval[1] = queue_action_user
        rval[-1] = len(queue_action_user) == 0 # Disable Interval
        return tuple(rval)
    
    return app
