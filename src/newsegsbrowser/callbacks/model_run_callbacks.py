"""

Functions:
- add_model_run_callbacks
- add_finance_run_callbacks
"""
import datetime
import json
import logging
from typing import cast

from dash import ctx, Dash, Input, no_update, Output, State

from newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodel.newsegsmodel import NewsegsModel

logger = logging.getLogger(__name__)

RUN_DEBOUNCE_SECONDS = 1.0
FINANCE_DEBOUNCE_SECONDS = 0.5

def add_model_run_callbacks(app: Dash):
    """
    Callbacks which handle model running
    """

    @app.callback(
        Output('queue-model-run', 'data'),
        Output('dispatchitem-model-run', 'data'),
        Output('interval-model-run', 'disabled'),
        Input('prequeue-model-run', 'data'),
        Input('interval-model-run', 'n_intervals'),
        State('latch-model-run-global', 'data'),
        State('queue-model-run', 'data'),
        prevent_initial_call = True
    )
    def queueman_model_run(
        prequeue_model_run,
        interval_model_run,
        latch_model_run_global,
        queue_model_run
    ):
        """
        Receives and dispatches model runs.

        On receiving (a) model run request(s) through the prequeue, will add 
        it/them to the end of the model run queue, after popping out any 
        existing requests for those models to run.
        The queue is then iterated through. If the model is permitted to be
        run (no latches apply) then it shall be removed from the queue and
        dispatched.
        The interval-model-run is enabled if the queue is not empty, forcing a
        re-fire of this callback every second until the queue is cleared.
        """
        if not queue_model_run:
            queue_model_run = []
        
        if ctx.triggered_id == 'prequeue-model-run':
            requests = prequeue_model_run
            if isinstance(requests, list):
                for model_id in [json.loads(x)['model_id'] for x in requests]:
                    remove_indexes = [
                        i for i, x in enumerate(queue_model_run) 
                        if json.loads(x)['model_id'] == model_id
                    ]
                    remove_indexes.sort(reverse=True) 
                    if remove_indexes:
                        for i in remove_indexes:
                            queue_model_run.pop(i)
                queue_model_run += requests
            else:
                model_id = json.loads(requests)['model_id']
                remove_indexes = [
                    i for i, x in enumerate(queue_model_run)
                    if json.loads(x)['model_id'] == model_id
                ]
                remove_indexes.sort(reverse = True)
                if remove_indexes:
                    for i in remove_indexes:
                        queue_model_run.pop(i)
                queue_model_run.append(requests)
        
        # Hope that this can be interpreted as a bool
        if latch_model_run_global is None:
            latch_model_run_global = True

        nowtime = datetime.datetime.now().timestamp()

        if latch_model_run_global:
            for i, request in enumerate(queue_model_run):
                request_l = json.loads(request)
                if nowtime - request_l['time'] > RUN_DEBOUNCE_SECONDS:
                    # There are no conditions, so we automatically run the first model
                    dispatch_request = queue_model_run.pop(i)
                    logger.info('model run dispatched: %s', dispatch_request)
                    return (
                        queue_model_run,
                        dispatch_request,
                        len(queue_model_run) == 0
                    )
        
        return (
            queue_model_run,
            no_update,
            len(queue_model_run) == 0
        )
    
    @app.callback(
        #Output('latch-models-checkedout', 'data', allow_duplicate = True),
        Output('latch-model-run-global', 'data', allow_duplicate = True),
        Output('trigger-model-run', 'data'),
        Input('dispatchitem-model-run', 'data'),
        #State('latch-models-checkedout', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_model_run(
        dispatchitem_model_run,
        #latch_models_checkedout,
    ):
        """
        Handle a model run request.

        When a model run request gets this far, it has been cleared for running
        (i.e. it has passed any latches). It can therefore be synchronised to 
        the cache, soft-locked for configuration updates by adding it to the
        checked-out list, and the trigger for the background model run can be 
        fired.
        """
        NUP = (
            #no_update, 
            no_update, 
            no_update
        )

        if dispatchitem_model_run is None:
            return NUP
        
        model_run = json.loads(dispatchitem_model_run)

        # No plan to handle a list of requests here
        if isinstance(model_run, list):
            raise TypeError('Cannot handle a list of model run requests.')
        
        #if latch_models_checkedout is None:
        #    latch_models_checkedout = set() # Empty set, not dict
        #else:
        #    latch_models_checkedout = set(latch_models_checkedout)        

        app.model_to_cache(model_run['model_id'])
        mdl = cast(NewsegsModel, app.models.get(model_run['model_id']))
        if mdl is None:
            logger.warning('model to be run not found: %s')
        else:
            mdl.checked_out = True

        #latch_models_checkedout.add(model_run['model_id'])

        logging.info('model dispatched to run: %s', model_run)

        return (
            #list(latch_models_checkedout),
            False,
            dispatchitem_model_run,
        )
    
    # The actual run has to go in the main app.py to prevent issues with the bcm accessing cache
    
    @app.callback(
        Output('trigger-postprocess-model-run', 'data', allow_duplicate = True),
        #Output('latch-models-checkedout', 'data', allow_duplicate = True),
        Output('latch-model-run-global', 'data', allow_duplicate = True),
        Input('trigger-post-model-run', 'data'),
        #State('latch-models-checkedout', 'data'),
        prevent_initial_call = True
    )
    def receiver_model_run(
        trigger_post_model_run,
        #latch_models_checkedout
    ):
        """
        After a (background) model run completes, resync the local model.
        """
        model_run = json.loads(trigger_post_model_run)
        model_id = model_run['model_id']
        
        # Sync with background cache
        app.models[model_id] = app.model_from_cache(model_id)
        # The synced model should have checked_out = False
        if app.models[model_id].checked_out:
            raise ValueError(f'model should not be checked out: {model_id}')
        # Reattach to metamodel
        mm = cast(NewsegsMetaModel, app.metamodels.get(model_run['metamodel_id']))
        mm.reattach_model(app.models)
        
        # Clear model for editing
        #latch_models_checkedout = set(latch_models_checkedout)
        #latch_models_checkedout.remove(model_id)

        logging.info('model run completed: %s', model_run)

        return (
            trigger_post_model_run,
            #list(latch_models_checkedout),
            True,
        )

    return app

def add_finance_run_callbacks(app: Dash):
    """
    Callbacks which handle finance running
    """

    @app.callback(
        Output('queue-finance-run', 'data'),
        Output('dispatchitem-finance-run', 'data'),
        Output('interval-finance-run', 'disabled'),
        Input('prequeue-finance-run', 'data'),
        Input('interval-finance-run', 'n_intervals'),
        #State('latch-models-checkedout', 'data'),
        State('queue-finance-run', 'data'),
        prevent_initial_call = True,
    )
    def queueman_finance_run(
        prequeue_finance_run,
        interval_finance_run,
        #latch_models_checkedout,
        queue_finance_run
    ):
        """
        Receives and dispatches finance runs.

        On receiving (a) finance run request(s) through the prequeue, adds
        it/them to the end of the finance run queue, after popping out any
        existing requests for that finance to run.
        The queue is then iterated through. If the finance is permitted to
        be run (no latches apply) then it shall be removed from the queue
        and dispatched.
        The interval-finance-fun is enabled if the queue is not empty, forcing
        a re-fire of this callback every second until the queue is cleared.
        """
        if not queue_finance_run:
            queue_finance_run = []
        
        if ctx.triggered_id == 'prequeue-finance-run':
            requests = prequeue_finance_run
            if isinstance(requests, list):
                for finance_id in [json.loads(x)['finance_id'] for x in requests]:
                    remove_indexes = [
                        i for i, x in enumerate(queue_finance_run)
                        if json.loads(x)['finance_id']  == finance_id
                    ]
                    remove_indexes.sort(reverse = True)
                    if remove_indexes:
                        for i in remove_indexes:
                            queue_finance_run.pop(i)
                queue_finance_run += requests
            else:
                finance_id = json.loads(requests)['finance_id']
                remove_indexes = [
                    i for i, x in enumerate(queue_finance_run)
                    if json.loads(x)['finance_id']  == finance_id
                ]
                remove_indexes.sort(reverse = True)
                if remove_indexes:
                    for i in remove_indexes:
                        queue_finance_run.pop(i)
                queue_finance_run.append(requests)

        #if latch_models_checkedout is None:
        #    latch_models_checkedout = set()
        #else:
        #    latch_models_checkedout = set(latch_models_checkedout)
        
        nowtime = datetime.datetime.now().timestamp()

        for i, request in enumerate(queue_finance_run):
            request_l = json.loads(request)
            if nowtime - request_l['time'] > FINANCE_DEBOUNCE_SECONDS:
                # Cannot run if model is checked out
                mdl = app.models.get(request_l['model_id'])
                if mdl is None:
                    raise ValueError(f'model {request_l['model_id']} not found')
                fnc = app.finances.get(request_l['finance_id'])
                if not mdl.checked_out and not fnc.checked_out:
                    dispatch_request = queue_finance_run.pop(i)

                    return (
                        queue_finance_run,
                        dispatch_request,
                        len(queue_finance_run) == 0
                    )
        
        return (
            queue_finance_run,
            no_update,
            len(queue_finance_run) == 0
        )
    
    @app.callback(
        #Output('latch-finances-checkedout', 'data', allow_duplicate = True),
        Output('latch-finance-run-global', 'data', allow_duplicate = True),
        Output('trigger-finance-run', 'data'),
        Input('dispatchitem-finance-run', 'data'),
        State('latch-finances-checkedout', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_finance_run(
        dispatchitem_finance_run,
        latch_finances_checkedout
    ):
        """
        Handle a finance run request.

        When a finance run request gets this far, it has been cleared for
        running (i.e. it has passed any latches). It can therefore be
        synchronised to the cache, soft-locked for configuration updates
        by adding it to the checked-out list, and the trigger of the background
        finance run can be fired.
        """
        NUP = no_update, no_update, no_update

        if dispatchitem_finance_run is None:
            return NUP
        
        finance_run = json.loads(dispatchitem_finance_run)

        if isinstance(finance_run, list):
            raise TypeError('Cannot handle a list of finance run requests')
        
        #if latch_finances_checkedout is None:
        #    latch_finances_checkedout = set()
        #else:
        #    latch_finances_checkedout = set(latch_finances_checkedout)
        
        # Model is synced to cache, but no need to lock
        app.model_to_cache(finance_run['model_id'])

        app.finance_to_cache(finance_run['finance_id'])
        app.finances.get(finance_run['finance_id']).checked_out = True
        #latch_finances_checkedout.add(finance_run['finance_id'])

        logging.info('finance dispatched to run: %s', finance_run)

        return(
            #list(latch_finances_checkedout),
            False,
            dispatchitem_finance_run
        )

    @app.callback(
        Output('trigger-postprocess-finance-run', 'data', allow_duplicate = True),
        #Output('latch-finances-checkedout', 'data', allow_duplicate = True),
        Output('latch-finance-run-global', 'data', allow_duplicate = True),
        Input('trigger-post-finance-run', 'data'),
        #State('latch-finances-checkedout', 'data'),
        prevent_initial_call = True
    )
    def receiver_finance_run(
        trigger_post_finance_run,
        #latch_finances_checkedout
    ):
        """
        After a (background) finance run completes, resync the local finance.
        """
        finance_run = json.loads(trigger_post_finance_run)
        finance_id = finance_run['finance_id']

        # Sync with background cache
        app.finances[finance_id] = app.finance_from_cache(finance_id)
        # Ensure model is correct
        # However, do not go through the standard accessor
        # to avoid dirtying the finance
        app.finances[finance_id].set_model(
            app.models.get(finance_run['model_id']), 
            False
        )
        mm = cast(NewsegsMetaModel, app.metamodels.get(finance_run['metamodel_id']))
        mm.reattach_finance(app.finances)

        # Clear finance for editing
        #latch_finances_checkedout = set(latch_finances_checkedout)
        #latch_finances_checkedout.remove(finance_id)

        logging.info('finance run completed: %s', finance_run)

        return (
            trigger_post_finance_run,
            #list(latch_finances_checkedout),
            True,
        )
    
    return app
