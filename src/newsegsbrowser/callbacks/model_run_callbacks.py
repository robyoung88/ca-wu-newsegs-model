"""

Functions:
- add_model_run_callbacks
- add_finance_run_callbacks
"""
import datetime
import json
import logging
from typing import Any, cast

from dash import ALL, NoUpdate, ctx, Dash, Input, no_update, Output, State

from newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodel.newsegsmodel import NewsegsModel
from newsegsbrowser.postprocess import postprocess_utils

logger = logging.getLogger(__name__)

RUN_DEBOUNCE_SECONDS = 1.0
FINANCE_DEBOUNCE_SECONDS = 0.5
METAMODEL_PROCESS_DEBOUNCE_SECONDS = 1.0

def add_model_run_callbacks(app: Dash):
    """
    Callbacks which handle model running
    """

    @app.callback(
        Output('prequeue-model-run', 'data', allow_duplicate = True),
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
        
        logger.info('processing model queue, triggered by %s', ctx.triggered_id)

        if ctx.triggered_id == 'prequeue-model-run':
            requests = prequeue_model_run
            if not isinstance(requests, list):
                requests = [requests]

            # Remove any existing requests relating to this model
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
        
        # Hope that this can be interpreted as a bool
        if latch_model_run_global is None:
            latch_model_run_global = True

        nowtime = datetime.datetime.now().timestamp()

        logger.info('%s models are in queue', len(queue_model_run))
        logger.info('latch_model_run_global is %s', latch_model_run_global)

        if latch_model_run_global:
            for i, request in enumerate(queue_model_run):
                request_l = json.loads(request)
                logger.info('checking if model %s should be run', request_l['model_id'])
                if nowtime - request_l['time'] > RUN_DEBOUNCE_SECONDS:
                    mdl = app.models.get(request_l['model_id'])
                    if not mdl.checked_out:
                        mdl.checked_out = True
                        dispatch_request = queue_model_run.pop(i)
                        logger.info('model run dispatched: %s', dispatch_request)
                        return (
                            [], # consume prequeue
                            queue_model_run,
                            dispatch_request,
                            len(queue_model_run) == 0
                        )
                    else:
                        logger.info('model %s is checked out', request_l['model_id'])    
                else:
                    logger.info('debounce has not expired for model %s', request_l['model_id'])
        
        return (
            [],
            queue_model_run,
            no_update,
            len(queue_model_run) == 0
        )
    
    @app.callback(
        Output('trigger-model-run', 'data'),
        Output('latch-model-run-global', 'data', allow_duplicate = True),
        
        Input('dispatchitem-model-run', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_model_run(
        dispatchitem_model_run,
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
            no_update, 
            no_update
        )

        if dispatchitem_model_run is None:
            return NUP
        
        model_run = json.loads(dispatchitem_model_run)

        # No plan to handle a list of requests here
        if isinstance(model_run, list):
            raise TypeError('Cannot handle a list of model run requests.')

        mdl = cast(NewsegsModel, app.models.get(model_run['model_id']))
        if mdl is None:
            logger.warning('model to be run not found: %s')
            return (
                no_update,
                True
            )
        
        mdl.checked_out = False
        app.model_to_cache(model_run['model_id'])
        mdl.checked_out = True

        logging.info('model dispatched to run: %s', model_run)

        return (
            dispatchitem_model_run,
            False
        )
    
    # The actual run has to go in the main app.py to prevent issues with the bcm accessing cache
    
    @app.callback(
        Output('trigger-postprocess-model-run', 'data', allow_duplicate = True),
        Output('latch-model-run-global', 'data', allow_duplicate = True),

        Input('trigger-post-model-run', 'data'),
        prevent_initial_call = True
    )
    def receiver_model_run(
        trigger_post_model_run,
    ):
        """
        After a (background) model run completes, resync the local model.
        """
        model_run = json.loads(trigger_post_model_run)
        model_id = model_run['model_id']

        logging.info('resyncing model after run completed: %s', model_run)
        
        # Sync with background cache
        app.models[model_id] = app.model_from_cache(model_id)
        # The synced model should have checked_out = False
        if app.models[model_id].checked_out:
            raise ValueError(f'model should not be checked out: {model_id}')
        
        # Reattach to metamodel
        mm = cast(NewsegsMetaModel, app.metamodels.get(model_run['metamodel_id']))
        mm.reattach_model(app.models)

        logging.info('model run resync completed: %s', model_run)

        return (
            trigger_post_model_run,
            True,
        )

    return app

def add_finance_run_callbacks(app: Dash):
    """
    Callbacks which handle finance running
    """

    @app.callback(
        Output('prequeue-finance-run', 'data', allow_duplicate = True),
        Output('queue-finance-run', 'data'),
        Output('dispatchitem-finance-run', 'data'),
        Output('interval-finance-run', 'disabled'),

        Input('prequeue-finance-run', 'data'),
        Input('interval-finance-run', 'n_intervals'),
        State('latch-finance-run-global', 'data'),
        State('queue-finance-run', 'data'),
        prevent_initial_call = True,
    )
    def queueman_finance_run(
        prequeue_finance_run,
        interval_finance_run,
        latch_finance_run_global,
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

        logger.info('processing finance queue, triggered by %s', ctx.triggered_id)
        
        if ctx.triggered_id == 'prequeue-finance-run':
            requests = prequeue_finance_run

            if not isinstance(requests, list):
                requests = [requests]
            
            # Remove any existing requests related to this finance
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

        # Hope that this can be interpreted as a bool
        if latch_finance_run_global is None:
            latch_finance_run_global = True
        
        nowtime = datetime.datetime.now().timestamp()

        logger.info('%s finances are in queue', len(queue_finance_run))
        logger.info('latch_finance_run_global is %s', latch_finance_run_global)

        if latch_finance_run_global:
            for i, request in enumerate(queue_finance_run):
                request_l = json.loads(request)
                logger.info('checking if finance %s should be run', request_l['finance_id'])
                if nowtime - request_l['time'] > FINANCE_DEBOUNCE_SECONDS:
                    # Cannot run if model is checked out
                    mdl = app.models.get(request_l['model_id'])
                    if mdl is None:
                        raise ValueError(f'model {request_l['model_id']} not found')
                    fnc = app.finances.get(request_l['finance_id'])
                    if not mdl.checked_out and not fnc.checked_out:
                        fnc.checked_out = True
                        dispatch_request = queue_finance_run.pop(i)

                        return (
                            [], # consume prequeue
                            queue_finance_run,
                            dispatch_request,
                            len(queue_finance_run) == 0
                        )
                    else:
                        logger.info('model is checked out (%s) or finance is checked out (%s) for finance %s', mdl.checked_out, fnc.checked_out, request_l['finance_id'])
                else:
                    logger.info('debounce has not expired for finance %s', request_l['finance_id'])
            
        return (
            [], # consume prequeue
            queue_finance_run,
            no_update,
            len(queue_finance_run) == 0
        )
    
    @app.callback(
        Output('trigger-finance-run', 'data'),
        Output('latch-finance-run-global', 'data', allow_duplicate = True),

        Input('dispatchitem-finance-run', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_finance_run(
        dispatchitem_finance_run,
    ):
        """
        Handle a finance run request.

        When a finance run request gets this far, it has been cleared for
        running (i.e. it has passed any latches). It can therefore be
        synchronised to the cache, soft-locked for configuration updates
        by adding it to the checked-out list, and the trigger of the background
        finance run can be fired.
        """
        NUP = no_update, no_update

        if dispatchitem_finance_run is None:
            return NUP
        
        finance_run = json.loads(dispatchitem_finance_run)

        if isinstance(finance_run, list):
            raise TypeError('Cannot handle a list of finance run requests')
        
        # Model is synced to cache, but no need to lock
        app.model_to_cache(finance_run['model_id'])

        app.finances.get(finance_run['finance_id']).checked_out = False
        app.finance_to_cache(finance_run['finance_id'])
        app.finances.get(finance_run['finance_id']).checked_out = True
        
        logging.info('finance dispatched to run: %s', finance_run)

        return(
            dispatchitem_finance_run,
            False,
        )

    @app.callback(
        Output('trigger-postprocess-finance-run', 'data', allow_duplicate = True),
        Output('latch-finance-run-global', 'data', allow_duplicate = True),

        Input('trigger-post-finance-run', 'data'),
        prevent_initial_call = True
    )
    def receiver_finance_run(
        trigger_post_finance_run,
    ):
        """
        After a (background) finance run completes, resync the local finance.
        """
        finance_run = json.loads(trigger_post_finance_run)
        finance_id = finance_run['finance_id']

        logging.info('resyncing finance after run completed: %s', finance_run)

        # Sync with background cache
        app.finances[finance_id] = app.finance_from_cache(finance_id)
        # The synced finance should have checked_out = False
        if app.finances[finance_id].checked_out:
            raise ValueError(f'finance should not be checked out: {finance_id}')
        
        # Ensure model is correct
        # However, do not go through the standard accessor
        # to avoid dirtying the finance
        app.finances[finance_id].set_model(
            app.models.get(finance_run['model_id']), 
            False
        )
        mm = cast(NewsegsMetaModel, app.metamodels.get(finance_run['metamodel_id']))
        mm.reattach_finance(app.finances)

        logging.info('finance run resync completed: %s', finance_run)

        return (
            trigger_post_finance_run,
            True,
        )

    # handling of arbitrary metamodel processes, assumed to take place in a background
    # process
    @app.callback(
        Output('prequeue-metamodel-process', 'data', allow_duplicate = True),
        Output('queue-metamodel-process', 'data'),
        Output('dispatchitem-metamodel-process', 'data'),
        Output('interval-metamodel-process', 'disabled'),

        Input('prequeue-metamodel-process', 'data'),
        Input('interval-metamodel-process', 'n_intervals'),
        State('latch-metamodel-process-global', 'data'),
        State('queue-metamodel-process', 'data'),

        prevent_initial_call = True
    )
    def queueman_metamodel_processs(
        prequeue_metamodel_process,
        interval_metamodel_process,
        latch_metamodel_process,
        queue_metamodel_process,
    ):
        """
        Receives and dispatches arbitrary metamodel processes.
        """
        if not queue_metamodel_process:
            queue_metamodel_process = []
        
        logger.info('processing metamodel queue, triggered by %s', ctx.triggered_id)

        if ctx.triggered_id == 'prequeue-metamodel-process':
            requests = prequeue_metamodel_process
            if not isinstance(requests, list):
                requests = [requests]

            # For the moment, assume that any new metamodel request will
            # replace any equivalents
            requests_dejson = [json.loads(x) for x in requests]
            
            for req in requests_dejson:
                queue_dejson = [json.loads(x) for x in queue_metamodel_process]
                remove_indexes = [
                    i for i, x in enumerate(queue_dejson)
                    if x['metamodel_id'] == req['metamodel_id'] and x['type'] == req['type']
                ]
                remove_indexes.sort(reverse = True)
                if remove_indexes:
                    for i in remove_indexes:
                        queue_metamodel_process.pop(i)
            queue_metamodel_process += requests

        if latch_metamodel_process is None:
            latch_metamodel_process = True
        
        nowtime = datetime.datetime.now().timestamp()

        logger.info('%s processes are in queue', len(queue_metamodel_process))
        logger.info('latch_metamodel_process_global is %s', latch_metamodel_process)

        if latch_metamodel_process:
            for i, request in enumerate(queue_metamodel_process):
                request_l = json.loads(request)
                logger.info('checking if metamodel %s should be run', request_l['metamodel_id'])
                if nowtime - request_l['time'] > METAMODEL_PROCESS_DEBOUNCE_SECONDS:
                    mm_id = request_l['metamodel_id']
                    mm = app.metamodels.get(mm_id)
                    if not mm.model.checked_out and not mm.finance.checked_out and not mm.checked_out:
                        # Check out before starting the callback chain
                        mm.model.checked_out = True
                        mm.finance.checked_out = True
                        mm.checked_out = True
                        dispatch_request = queue_metamodel_process.pop(i)
                        logger.info('metamodel process dispatched: %s', dispatch_request)
                        return (
                            [], # consume prequeue
                            queue_metamodel_process,
                            dispatch_request,
                            len(queue_metamodel_process) == 0
                        )
                    else:
                        logger.info('Metamodel or child is checked out: %s', request_l['metamodel_id'])
                else:
                    logger.info('debounce has not expired for metamodel %s', request_l['metamodel_id'])
        
        return (
            [],
            queue_metamodel_process,
            no_update,
            len(queue_metamodel_process) == 0
        )

    @app.callback(
        Output('trigger-metamodel-process', 'data'),
        Output('latch-metamodel-process-global', 'data', allow_duplicate = True),

        Input('dispatchitem-metamodel-process', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_metamodel_process(
        dispatchitem_metamodel_process,
    ):
        """
        Handle a metamodel process request
        """
        NUP = (
            no_update,
            no_update
        )

        if dispatchitem_metamodel_process is None:
            return NUP
        
        metamodel_process = json.loads(dispatchitem_metamodel_process)

        # No plan to handle a list or requests here
        if isinstance(metamodel_process, list):
            raise TypeError('Cannot handle a list of metamodel processes')
        
        mm = cast(NewsegsMetaModel, app.metamodels.get(metamodel_process['metamodel_id']))
        if mm is None:
            logger.warning('metamodel to process not found: %s', metamodel_process['metamodel_id'])
            return (
                no_update,
                True,
            )
        
        mm.checked_out = False
        mm.model.checked_out = False
        mm.finance.checked_out = False
        app.metamodel_to_cache(metamodel_process['metamodel_id'])
        app.model_to_cache(mm.model.id)
        app.finance_to_cache(mm.finance.id)
        mm.checked_out = True
        mm.model.checked_out = True
        mm.finance.checked_out = True

        logging.info('metamodel dispatched to process: %s', metamodel_process)

        return (
            dispatchitem_metamodel_process,
            False
        )
    
    # See app.py for the run logic

    @app.callback(
        Output('trigger-postprocess-metamodel-process', 'data', allow_duplicate = True),
        Output('latch-metamodel-process-global', 'data', allow_duplicate = True),

        Input('trigger-post-metamodel-process', 'data'),
        prevent_initial_call = True
    )
    def receiver_metamodel_process(
        trigger_post_metamodel_process,
    ):
        process_request = json.loads(trigger_post_metamodel_process)
        mm = app.metamodel_from_cache(process_request.get('metamodel_id'), 'cache')
        app.metamodels[mm.id] = mm
        app.models[mm.model.id] = mm.model
        app.finances[mm.finance.id] = mm.finance

        logging.info('resyncing metamodel after process completed: %s', process_request)

        match process_request['type']:
            case 'dsa-run-request':
                dsa_result_id = postprocess_utils.get_dsa_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES['dsa_results'],
                    mm.id
                )
                app.results[dsa_result_id] = app.cache[dsa_result_id]
        
        return (
            trigger_post_metamodel_process,
            True,
        )
    
    @app.callback(
        Output({'type': 'trigger', 'page': ALL, 'key': ALL}, 'data'),
        
        Input('trigger-postprocess-metamodel-process', 'data'),
        State({'type': 'trigger', 'page': ALL, 'key': ALL}, 'id'),
        prevent_initial_call = True
    )
    def dispatch_metamodel_postprocess(
        trigger_postprocess_metamodel_process,
        trigger_ids
    ):
        rval: list[Any] = [no_update] * len(trigger_ids)
        if not isinstance(trigger_postprocess_metamodel_process, list):
            trigger_postprocess_metamodel_process = [trigger_postprocess_metamodel_process]
        
        for process_str in trigger_postprocess_metamodel_process:
            process = json.loads(process_str)
            match process['type']:
                case 'dsa-run-request':
                    for i, trigger_id in enumerate(trigger_ids):
                        if trigger_id['key'] == 'dsa-run-postprocess':
                            if isinstance(rval[i], NoUpdate):
                                rval[i] = []
                            rval[i].append(process_str)
        
        return rval
    
    return app
