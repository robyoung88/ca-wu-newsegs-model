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

from dash import ALL, ctx, Dash, Input, Output, Patch, State, no_update
from dash import clientside_callback, ClientsideFunction

from newsegsbrowser import common as browser
from newsegsbrowser.callbacks import callbacks_map

logger = logging.getLogger(__name__)

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
        Input('onload-div', 'children')
    )

    @app.callback(
        Output('firstload-config-watcher', 'data'),
        Input('onload-div', 'children')
    )
    def sync_config_init(_):
        """
        Trigger any initial actions after a page load
        """
        logger.info('Model configuration onload div constructed.')
        return datetime.datetime.now().timestamp()
    
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
        Output('model-config', 'data', allow_duplicate=True),
        Output('finance-config', 'data', allow_duplicate=True),
        Input('firstload-config-watcher', 'data'),
        Input('store-selected-configuration', 'data'),
        Input('store-configurations', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_config(
        firstload_config_watcher,
        store_selected_configuration,
        store_configurations,
        selected_model
    ):
        logger.info('sync_config triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_config'](
            firstload_config_watcher,
            store_selected_configuration,
            store_configurations,
            app
        )
    
    # Updates to inputs based on config
    @app.callback(
        Output('site-location', 'data', allow_duplicate = True),
        Input('model-config', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_loc_inputs_to_store(
        mcfg,
        selected_model
    ):
        logger.info('sync_loc_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_loc_inputs_to_store'](
            mcfg,
            app
        )
    
    @app.callback(
        Output({'type': 'input-header', 'section': 'model-config', 'key': 'gen-smry'}, 'children'),
        Output({'type': 'input-model-config', 'section': 'gen_input', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        State({'type': 'input-model-config', 'section': 'gen_input', 'key': ALL}, 'value'),
        State({'type': 'input-model-config', 'section': 'gen_input', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_gen_inputs_to_store(
        mcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_gen_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_gen_inputs_to_store'](
            mcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'input-header', 'section': 'model-config', 'key': 'stor-smry'}, 'children'),
        Output({'type': 'input-model-config', 'section': 'stor_input', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        State({'type': 'input-model-config', 'section': 'stor_input', 'key': ALL}, 'value'),
        State({'type': 'input-model-config', 'section': 'stor_input', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_stor_inputs_to_store(
        mcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_stor_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_stor_inputs_to_store'](
            mcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'input-header', 'section': 'model-config', 'key': 'bc-smry'}, 'children'),
        Output({'type': 'input-model-config', 'section': 'bc_input', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        State({'type': 'input-model-config', 'section': 'bc_input', 'key': ALL}, 'value'),
        State({'type': 'input-model-config', 'section': 'bc_input', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_bc_inputs_to_store(
        mcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_bc_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_bc_inputs_to_store'](
            mcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'input-header', 'section': 'model-config', 'key': 'dc-smry'}, 'children'),
        Output({'type': 'input-model-config', 'section': 'dc_input', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        State({'type': 'input-model-config', 'section': 'dc_input', 'key': ALL}, 'value'),
        State({'type': 'input-model-config', 'section': 'dc_input', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_dc_inputs_to_store(
        mcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_dc_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_dc_inputs_to_store'](
            mcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'input-header', 'section': 'model-config', 'key': 'mc-smry'}, 'children'),
        Output({'type': 'input-model-config', 'section': 'mc_input', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        State({'type': 'input-model-config', 'section': 'mc_input', 'key': ALL}, 'value'),
        State({'type': 'input-model-config', 'section': 'mc_input', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_mc_inputs_to_store(
        mcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_mc_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_mc_inputs_to_store'](
            mcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    ##### FINANCE ######
    
    # The finance configuration is essentially monolithic - a "unit_costs"
    # dictionary holds most information, and the discount rates are at top
    # level. This may prove to be restrictive, but we shall work with it 
    # for now.
    @app.callback(
        Output({'type': 'input-header', 'section': 'finance-config', 'key': 'cost-gen-smry'}, 'children'),
        Output({'type': 'input-header', 'section': 'finance-config', 'key': 'cost-stor-smry'}, 'children'),
        Output({'type': 'input-header', 'section': 'finance-config', 'key': 'cost-sales-smry'}, 'children'),
        Output({'type': 'input-header', 'section': 'finance-config', 'key': 'cost-import-smry'}, 'children'),
        Output({'type': 'input-finance-config', 'section': 'unit_costs', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        Input('finance-config', 'data'),
        State({'type': 'input-finance-config', 'section': 'unit_costs', 'key': ALL}, 'value'),
        State({'type': 'input-finance-config', 'section': 'unit_costs', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_unit_cost_inputs_to_store(
        mcfg, 
        fcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_unit_cost_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_unit_cost_inputs_to_store'](
            mcfg,
            fcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'input-header', 'section': 'finance-config', 'key': 'fnc-smry'}, 'children'),
        Output({'type': 'input-finance-config', 'section': 'None', 'key': ALL}, 'value'),
        Input('model-config', 'data'),
        Input('finance-config', 'data'),
        State({'type': 'input-finance-config', 'section': 'None', 'key': ALL}, 'value'),
        State({'type': 'input-finance-config', 'section': 'None', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_fnc_inputs_to_store(
        mcfg,
        fcfg,
        current_input_values,
        current_input_ids,
        selected_model
    ):
        logger.info('sync_fnc_inputs_to_store triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_fnc_inputs_to_store'](
            mcfg,
            fcfg,
            current_input_values,
            current_input_ids,
            app
        )
    
    return app
    
def add_feedback_callbacks(app):
    """
    Callbacks for updating feedback elements given current configuration
    """
    
    @app.callback(
        Output({'type': 'feedback-graph', 'section': 'feedback', 'key': ALL}, 'figure'),
        Input('model-config', 'data'),
        State({'type': 'feedback-graph', 'section': 'feedback', 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def update_feedback_graphs(
        mcfg,
        figure_ids,
        selected_model
    ):
        logger.info('update_feedback_graphs triggered.')
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_feedback_graphs'](
            mcfg,
            figure_ids,
            app
        )

    return app 

def add_interface_to_model_callbacks(app):
    """
    Callbacks for when a user changes a model or finance config input.
    """

    @app.callback(
        Output('prequeue-action-user', 'data'),
        Input({'type': 'input-model-config', 'section': ALL, 'key': ALL}, 'value'),
        Input({'type': 'input-finance-config', 'section': ALL, 'key': ALL}, 'value'),
        #Input('model-config','data'), # Trying to suppress circular callbacks
        #State('prequeue-action-user', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def interface_update_config(
        inputs_model,
        inputs_finance,
        #model_config,
        #prequeue,
        selected_config
    ):
        """
        Add model configuration update events to the user action prequeue.

        May be fired before the queuemanager absorbs the prequeue, so needs
        to ensure that the prequeue is appended, not overwritten.
        In future, we may see if we can do this with a Patch - not sure how the
        data are held, and it may be that we can just append a list rather than
        full json deserialise/serialise.
        """
        NUP = no_update

        if ctx.triggered_id == 'model-config':
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

        trig = ctx.triggered
        for prop in trig:
            pid = json.loads(prop['prop_id'].rstrip('.value'))
            val = prop['value']
            match pid['type']:
                case 'input-model-config':
                    model_changed = True
                    prequeue.append(
                        json.dumps(
                            browser.model_interface_action(
                                model_id = selected_model,
                                input_key = pid['key'],
                                input_value = val,
                                key_section = pid['section']
                            )
                        )
                    )
                case 'input-finance-config':
                    finance_changed = True
                    prequeue.append(
                        json.dumps(
                            browser.finance_interface_action(
                                finance_id = selected_finance,
                                input_key = pid['key'],
                                input_value = val,
                                key_section = pid['section']
                            )
                        )
                    )
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
        else:
            logger.info('no changes to prequeue, which is %d items long', l2)   
        
        prequeue_patch.extend(prequeue)
        return prequeue_patch

        if l2 == l1:
            return NUP
        
        return prequeue

    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        Output('queue-action-user', 'data'),
        Output('dispatchitem-action-user', 'data'),
        Output('interval-action-user', 'disabled'),
        Input('prequeue-action-user', 'data'),
        Input('interval-action-user', 'n_intervals'),
        State('latch-models-checkedout', 'data'),
        State('queue-action-user', 'data'),
        prevent_initial_call = True
    )
    def queueman_action_user(
        prequeue_action_user, 
        interval_action_user,
        latch_models_checkedout,
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

        logger.info('queueman_action_user triggered by: %s', ctx.triggered_id)
        
        if ctx.triggered_id == 'prequeue-action-user':
            action = prequeue_action_user
            
            if isinstance(action, list):
                logger.info('handling %d user actions', len(action))
                queue_action_user += action
            else:
                logger.info('handling single user action')
                queue_action_user.append(action)
            
            # TODO: Rationalise queue
        
        if latch_models_checkedout is None:
            latch_models_checkedout = set()
        else:
            latch_models_checkedout = set(latch_models_checkedout)

        # Loop through action queue
        for i, action_json in enumerate(queue_action_user):
            action = json.loads(action_json)
            match action['type']:
                case 'model_config_interface_update':
                    if action['model_id'] not in latch_models_checkedout:
                        # Have a positive dispatch
                        # Find other appropriate actions
                        action_indexes = [i]
                        j = i + 1
                        if j < len(queue_action_user):
                            for j in range(i + 1, len(queue_action_user)):
                                act_j = json.loads(queue_action_user[j])
                                if (
                                    act_j['type'] == 'model_config_interface_update'
                                    and act_j['model_id'] == action['model_id']
                                ):
                                    action_indexes.append(j)
                        action_indexes.reverse()
                        dispatch_actions = [queue_action_user.pop(x) for x in action_indexes]
                        dispatch_actions.reverse()

                        logger.info('dispatching %d model config interface actions', len(dispatch_actions))

                        return (
                            [], # The prequeue is consumed
                            queue_action_user,
                            dispatch_actions,
                            len(queue_action_user) == 0 # Disable Interval
                        )
                case 'finance_config_interface_update':
                    # Currently, have no latches in place for finance.
                    # Will go here when defined.

                    # Collate actions relating to this finance
                    action_indexes = [i]
                    j = i + 1
                    if j < len(queue_action_user):
                        for j in range(i + 1, len(queue_action_user)):
                            act_j = json.loads(queue_action_user[j])
                            if (
                                act_j['type'] == 'finance_config_interface_update'
                                and act_j['finance_id'] == action['finance_id']
                            ):
                                action_indexes.append(j)
                    action_indexes.reverse()
                    dispatch_actions = [queue_action_user.pop(x) for x in action_indexes]
                    dispatch_actions.reverse()

                    logger.info('dispatching %d finance config interface actions', len(dispatch_actions))

                    return (
                        [], # The prequeue is consumed
                        queue_action_user,
                        dispatch_actions,
                        len(queue_action_user) == 0 # Disable Interval
                    )
                case _:
                    raise ValueError(f'action type not recognised: {action['type']}')
        
        # Fall-through - do not update dispatchitem-action-user
        return (
            None, # The prequeue is consumed
            queue_action_user,
            no_update,
            len(queue_action_user) == 0 # Disable Interval
        )
    
    @app.callback(
        Output('store-model-interface-configurations', 'data', allow_duplicate = True),
        Output('store-finance-interface-configurations', 'data', allow_duplicate = True),
        Output('model-config', 'data'),
        Output('finance-config', 'data'),
        Output('prequeue-model-run', 'data'),
        Output('prequeue-finance-run', 'data'),
        Output('trigger-postprocess-model-run', 'data', allow_duplicate = True),
        Output('trigger-postprocess-finance-run', 'data', allow_duplicate = True),
        Input('dispatchitem-action-user', 'data'),
        State('store-model-interface-configurations', 'data'),
        State('store-finance-interface-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def dispatcher_action_user(
        dispatchitem_action_user,
        store_model_interface_configurations,
        store_finance_interface_configurations,
        store_selected_configuration,
        selected_model,
    ):
        """
        Handle a user action.

        When a user action gets this far, it has been cleared for actioning
        (i.e. it has passed any latches). This means that if it is a local 
        model configuration change, that may now be applied into the local
        configuration dictionary and the local copy of the model updated.
        If we have a change to a model, then it will be necessary to queue
        the model for running.
        To allow processing of the queue efficiently, the dispatchitem-action-user
        may be a list of actions for a single model, finance, or configuration.
        All updates should be applied prior to the model run request being
        sent.
        """
        logger.info('dispatcher_action_user triggered')
        return callbacks_map.CALLBACKS_MAP[selected_model]['dispatcher_action_user'](
            dispatchitem_action_user,
            store_model_interface_configurations,
            store_finance_interface_configurations,
            store_selected_configuration,
            app
        )
    
    return app
