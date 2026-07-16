"""

Functions:
- add_model_run_callbacks
- add_finance_run_callbacks
"""
import datetime
import json
import logging
import time
from typing import Any, cast

from dash import ALL, NoUpdate, Patch, ctx, Dash, Input, no_update, Output, State, html

from newsegsbrowser import icons
import newsegsbrowser.common as browser
from newsegsbrowser.callbacks.locks import ok_run_model
from newsegsfinance.newsegsfinance import NewsegsFinance
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
        Output('dispatchitem-model-run', 'data', allow_duplicate = False),
        Output('prequeue-model-run', 'data', allow_duplicate = True),
        Output('interval-model-run', 'disabled'),
        Output({
            'type': 'lock', 
            'target': 'model-run', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),

        Input('prequeue-model-run', 'data'),
        Input('interval-model-run', 'n_intervals'),

        State({'type': 'lock', 'target': 'model-run', 'stage': 'dispatch', 'key': ALL}, 'data'),
        State('dispatchitem-model-run', 'data'),
        prevent_initial_call = True
    )
    def queueman_model_run(
        prequeue_model_run,
        interval_model_run,
        model_run_dispatch_lock_values,
        dispatch_status,
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
        
        logger.info('processing model queue, triggered by %s, %s', ctx.triggered_id, datetime.datetime.now())
        
        # If a prequeue-model-run trigger falls on the heels of
        # interval-model-run, this can result in the State of queue-model-run
        # being stale. This being the case, we will actually use
        # the short-term-store (sts) of the app for our queue
        queue_model_run = app.sts.get('queue-model-run')
        if queue_model_run is None:
            app.sts['queue-model-run'] = []
            queue_model_run = app.sts.get('queue-model-run')

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

        nowtime = time.time()
        
        #logger.info('%s models are in queue', len(queue_model_run))
        logger.info('current model run queue: %s', queue_model_run)

        app_dispatch_key = 'dispatchitem-model-run'
        app_dispatch = app.sts.get(app_dispatch_key)
        if app_dispatch is not None and app_dispatch != dispatch_status:
            logger.info('Early exit from model queue manager to avoid overwriting dispatch item')
            return (
                app_dispatch,
                [],
                len(queue_model_run) == 0,
                False,
            )

        ok_run = True
        for lock_ in model_run_dispatch_lock_values:
            ok_run = ok_run and lock_
        
        logger.info('model run dispatch locks are %s', ok_run)

        if ok_run:
            for i, request in enumerate(queue_model_run):
                request_l = json.loads(request)
                logger.info('checking if model %s should be run', request_l['model_id'])
                if not(request_l['debounce']) or nowtime - request_l['time'] > RUN_DEBOUNCE_SECONDS:
                    mdl = app.models[request_l['model_id']]
                    if not mdl.checked_out:
                        dispatch_request = queue_model_run.pop(i)
                        dr_dict = json.loads(dispatch_request)
                        if not dr_dict.get('force') and not mdl.dirty:
                            logger.info('Removing from model run queue: %s - model is clean', dispatch_request)
                            return (
                                no_update,
                                [],
                                len(queue_model_run) == 0,
                                True,
                            )
                        
                        logger.info('checking out model: %s', mdl.id)
                        mdl.checked_out = True
                        logger.info('model run dispatched: %s, %s', dispatch_request, datetime.datetime.now())
                        app.sts[app_dispatch_key] = dispatch_request
                        return (
                            dispatch_request,
                            [], # consume prequeue
                            len(queue_model_run) == 0,
                            False,
                        )
                    else:
                        logger.info('model %s is checked out', request_l['model_id'])    
                else:
                    logger.info('debounce has not expired for model %s', request_l['model_id'])
        
        return (
            no_update,
            [],
            len(queue_model_run) == 0,
            no_update
        )
    
    @app.callback(
        Output({'type': 'background-callback-call', 'target': 'model-run'}, 'data'),
        Output('background_process_heartbeat', 'disabled', allow_duplicate = True),
        
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
        NUP = no_update, no_update

        logger.info('dispatcher_model_run triggered at %s with payload %s', datetime.datetime.now(), dispatchitem_model_run)

        if dispatchitem_model_run is None:
            return NUP
        
        if isinstance(dispatchitem_model_run, list):
            raise TypeError('Can only handle a single model run at a time, got list length %s', len(dispatchitem_model_run))
        
        model_run = json.loads(dispatchitem_model_run)

        logger.info('model to dispatch is %s', model_run['model_id'])

        mdl = cast(NewsegsModel, app.models[model_run['model_id']])
        
        logger.info('checking in model before dispatch: %s, %s', mdl.id, datetime.datetime.now())
        mdl.checked_out = False
        app.model_to_cache(model_run['model_id'])
        logger.info('checking out model after dispatch: %s, %s', mdl.id, datetime.datetime.now())
        mdl.checked_out = True

        logging.info('model dispatched to run: %s', model_run)

        n_bgp = app.sts.get('n_bgp', 0)
        app.sts['n_bgp'] = n_bgp + 1

        return dispatchitem_model_run, False
        
    
    # The actual run has to go in the main app.py to prevent issues with the bcm accessing cache
    
    @app.callback(
        Output('trigger-postprocess-model-run', 'data', allow_duplicate = True),
        Output({
            'type': 'lock', 
            'target': 'model-run', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),
        Output('background_process_heartbeat', 'disabled', allow_duplicate = True),

        Input({'type': 'background-callback-return', 'target': 'model-run'}, 'data'),
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
        logger.info('checking in model after resync - %s', model_id)
        # The synced model should have checked_out = False
        if app.models[model_id].checked_out:
            logger.error('model should not be checked out: %s', model_id)
            raise ValueError(f'model should not be checked out: {model_id}')
        
        # Reattach to metamodel
        mm = cast(NewsegsMetaModel, app.metamodels.get(model_run['metamodel_id']))
        mm.reattach_model(app.models)

        # TODO: Handle failures of model run

        logging.info('model run resync completed: %s', model_run)

        n_bgp = max(0, app.sts.get('n_bgp', 0) - 1)
        app.sts['n_bgp'] = n_bgp
        
        return (
            trigger_post_model_run,
            True,
            n_bgp == 0
        )

    return app

def add_finance_run_callbacks(app: Dash):
    """
    Callbacks which handle finance running
    """

    @app.callback(
        Output('prequeue-finance-run', 'data', allow_duplicate = True),
        Output('dispatchitem-finance-run', 'data'),
        Output('interval-finance-run', 'disabled'),
        Output({
            'type': 'lock', 
            'target': 'finance-run', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),

        Input('prequeue-finance-run', 'data'),
        Input('interval-finance-run', 'n_intervals'),

        State({'type': 'lock', 'target': 'finance-run', 'stage': 'dispatch', 'key': ALL}, 'data'),
        State('dispatchitem-finance-run', 'data'),
        prevent_initial_call = True,
    )
    def queueman_finance_run(
        prequeue_finance_run,
        interval_finance_run,
        finance_run_dispatch_lock_values,
        dispatch_status,
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

        logger.info('processing finance queue, triggered by %s, %s', ctx.triggered_id, datetime.datetime.now())
        
        queue_finance_run = app.sts.get('queue-finance-run')
        if queue_finance_run is None:
            app.sts['queue-finance-run'] = []
            queue_finance_run = app.sts.get('queue-finance-run')

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
        
        nowtime = time.time()

        #logger.info('%s finances are in queue', len(queue_finance_run))
        logger.info('current finance run queue: %s', queue_finance_run)

        app_dispatch_key = 'dispatchitem-finance-run'
        app_dispatch = app.sts.get(app_dispatch_key)
        if app_dispatch is not None and app_dispatch != dispatch_status:
            logger.info('Early exit from finance queue manager to avoid overwriting dispatch item')
            return (
                [],
                app_dispatch,
                len(queue_finance_run) == 0,
                False
            )

        ok_run = True
        for lock_ in finance_run_dispatch_lock_values:
            ok_run = ok_run and lock_
        
        logger.info('finance run dispatch locks are %s', ok_run)

        if ok_run:
            for i, request in enumerate(queue_finance_run):
                request_l = json.loads(request)
                logger.info('checking if finance %s should be run', request_l['finance_id'])
                if not(request_l['debounce']) or nowtime - request_l['time'] > FINANCE_DEBOUNCE_SECONDS:
                    # Cannot run if model is checked out
                    mdl = app.models[request_l['model_id']]
                    fnc = app.finances[request_l['finance_id']]
                    if not mdl.checked_out and not fnc.checked_out:
                        dispatch_request = queue_finance_run.pop(i)
                        dr_dict = json.loads(dispatch_request)
                        if not dr_dict.get('force') and not fnc.dirty:
                            logger.info('Removing from finance run queue: %s - finance is clean', dispatch_request)
                            return (
                                [],
                                no_update,
                                len(queue_finance_run) == 0,
                                True,
                            )

                        logger.info('checking out finance: %s', fnc.id)
                        fnc.checked_out = True
                        
                        logger.info('finance run dispatched: %s, %s', dispatch_request, datetime.datetime.now())
                        app.sts[app_dispatch_key] = dispatch_request
                        return (
                            [], # consume prequeue
                            dispatch_request,
                            len(queue_finance_run) == 0,
                            False
                        )
                    else:
                        logger.info('model is checked out (%s) or finance is checked out (%s) for finance %s, model %s', mdl.checked_out, fnc.checked_out, request_l['finance_id'], mdl.id)
                else:
                    logger.info('debounce has not expired for finance %s', request_l['finance_id'])
            
        return (
            [], # consume prequeue
            no_update,
            len(queue_finance_run) == 0,
            no_update
        )
    
    @app.callback(
        Output({'type': 'background-callback-call', 'target': 'finance-run'}, 'data'),
        Output('background_process_heartbeat', 'disabled', allow_duplicate = True),

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

        logger.info('dispatcher_finance_run triggered at %s', datetime.datetime.now())

        if dispatchitem_finance_run is None:
            return NUP
        
        if isinstance(dispatchitem_finance_run, list):
            raise TypeError('Can only handle a single finance run at a time, got list length %s', len(dispatchitem_finance_run))
        
        finance_run = json.loads(dispatchitem_finance_run)
        
        # Model is synced to cache so finance can pick up, but no need to lock
        app.model_to_cache(finance_run['model_id'])

        fnc = cast(NewsegsFinance, app.finances[finance_run['finance_id']])

        logger.info('checking in finance before dispatch: %s', finance_run['finance_id'])
        fnc.checked_out = False
        app.finance_to_cache(finance_run['finance_id'])
        logger.info('checking out finance after dispatch: %s', finance_run['finance_id'])
        fnc.checked_out = True
        
        logging.info('finance dispatched to run: %s', finance_run)

        n_bgp = app.sts.get('n_bgp', 0)
        app.sts['n_bgp'] = n_bgp + 1

        return dispatchitem_finance_run, False
    
    # The actual run has to go in the main app.py to prevent issues with the bcm accessing cache

    @app.callback(
        Output('trigger-postprocess-finance-run', 'data', allow_duplicate = True),
        Output({
            'type': 'lock', 
            'target': 'finance-run', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),
        Output('background_process_heartbeat', 'disabled', allow_duplicate = True),

        Input({'type': 'background-callback-return', 'target': 'finance-run'}, 'data'),
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
        logger.info('checking in finance after resync - %s', finance_id)
        # The synced finance should have checked_out = False
        if app.finances[finance_id].checked_out:
            logger.error('finance should not be checked out: %s', finance_id)
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

        # TODO: Handle failures of finance run

        logging.info('finance run resync completed: %s', finance_run)

        n_bgp = max(0, app.sts.get('n_bgp', 0) - 1)
        app.sts['n_bgp'] = n_bgp

        return (
            trigger_post_finance_run,
            True,
            n_bgp == 0
        )

    # handling of arbitrary metamodel processes, assumed to take place in a background
    # process
    @app.callback(
        Output('dispatchitem-metamodel-process', 'data'),
        Output('prequeue-metamodel-process', 'data', allow_duplicate = True),
        Output('interval-metamodel-process', 'disabled'),
        Output({
            'type': 'lock', 
            'target': 'metamodel-process', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),

        Input('prequeue-metamodel-process', 'data'),
        Input('interval-metamodel-process', 'n_intervals'),

        State({'type': 'lock', 'target': 'metamodel-process', 'stage': 'dispatch', 'key': ALL}, 'data'),
        State('dispatchitem-metamodel-process', 'data'),

        prevent_initial_call = True
    )
    def queueman_metamodel_processs(
        prequeue_metamodel_process,
        interval_metamodel_process,
        metamodel_process_dispatch_lock_values,
        dispatch_status,
    ):
        """
        Receives and dispatches arbitrary metamodel processes.
        """
        
        logger.info('processing metamodel queue, triggered by %s', ctx.triggered_id)

        queue_metamodel_process = app.sts.get('queue-metamodel-process')
        if queue_metamodel_process is None:
            app.sts['queue-metamodel-process'] = []
            queue_metamodel_process = app.sts.get('queue-metamodel-process')

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
        
        nowtime = datetime.datetime.now().timestamp()

        logger.info('%s processes are in queue', len(queue_metamodel_process))

        app_dispatch_key = 'dispatchitem-metamodel-process'
        app_dispatch = app.sts.get(app_dispatch_key)
        if app_dispatch is not None and app_dispatch != dispatch_status:
            logger.info('Early exit from metamodel queue manager to avoid overwriting dispatch item')
            return (
                app_dispatch,
                [],
                len(queue_metamodel_process) == 0,
                False,
            )

        ok_run = True
        for lock_ in metamodel_process_dispatch_lock_values:
            ok_run = ok_run and lock_
        
        logger.info('metamodel process dispatch locks are %s', ok_run)

        if ok_run:
            for i, request in enumerate(queue_metamodel_process):
                request_l = json.loads(request)
                logger.info('checking if metamodel %s should be run', request_l['metamodel_id'])
                if not(request_l['debounce']) or nowtime - request_l['time'] > METAMODEL_PROCESS_DEBOUNCE_SECONDS:
                    mm_id = request_l['metamodel_id']
                    mm = app.metamodels[mm_id]
                    if not mm.model.checked_out and not mm.finance.checked_out and not mm.checked_out:
                        # Check out before starting the callback chain
                        logger.info('checking out model %s', mm.model.id)
                        mm.model.checked_out = True
                        logger.info('checking out finance %s', mm.finance.id)
                        mm.finance.checked_out = True
                        logger.info('checking out metamodel %s', mm.id)
                        mm.checked_out = True
                        dispatch_request = queue_metamodel_process.pop(i)
                        logger.info('metamodel process dispatched: %s', dispatch_request)
                        app.sts[app_dispatch_key] = dispatch_request
                        return (
                            dispatch_request,
                            [], # consume prequeue
                            len(queue_metamodel_process) == 0,
                            False
                        )
                    else:
                        logger.info('Metamodel or child is checked out: %s', request_l['metamodel_id'])
                else:
                    logger.info('debounce has not expired for metamodel %s', request_l['metamodel_id'])
        
        return (
            no_update,
            [],
            len(queue_metamodel_process) == 0,
            no_update
        )

    @app.callback(
        Output({'type': 'background-callback-call', 'target': 'metamodel-process'}, 'data'),
        Output('background_process_heartbeat', 'disabled', allow_duplicate = True),

        Input('dispatchitem-metamodel-process', 'data'),
        prevent_initial_call = True,
    )
    def dispatcher_metamodel_process(
        dispatchitem_metamodel_process,
    ):
        """
        Handle a metamodel process request
        """
        NUP =  no_update, no_update

        logger.info('dispatcher_metamodel_process triggered at %s', datetime.datetime.now())

        if dispatchitem_metamodel_process is None:
            return NUP
        
        if isinstance(dispatchitem_metamodel_process, list):
            raise TypeError('Can only handle a single metamodel process at a time, got list length %s', len(dispatchitem_metamodel_process))
        
        metamodel_process = json.loads(dispatchitem_metamodel_process)
        
        mm = cast(NewsegsMetaModel, app.metamodels[metamodel_process['metamodel_id']])
        
        logger.info('checking in metamodel prior to dispatch %s', mm.id)
        mm.checked_out = False
        logger.info('checking in model prior to dispatch %s', mm.model.id)
        mm.model.checked_out = False
        logger.info('checking in finance prior to dispatch %s', mm.finance.id)
        mm.finance.checked_out = False
        app.metamodel_to_cache(metamodel_process['metamodel_id'])
        app.model_to_cache(mm.model.id)
        app.finance_to_cache(mm.finance.id)
        mm.checked_out = True
        logger.info('checking out metamodel after dispatch %s', mm.id)
        mm.model.checked_out = True
        logger.info('checking out model after dispatch %s', mm.model.id)
        mm.finance.checked_out = True
        logger.info('checking out finance after dispatch %s', mm.finance.id)

        logger.info('metamodel dispatched to process: %s', metamodel_process)

        n_bgp = app.sts.get('n_bgp', 0)
        app.sts['n_bgp'] = n_bgp + 1

        return dispatchitem_metamodel_process, False
    
    # See app.py for the run logic

    @app.callback(
        Output('trigger-postprocess-metamodel-process', 'data', allow_duplicate = True),
        Output({
            'type': 'lock', 
            'target': 'metamodel-process', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),
        Output('background_process_heartbeat', 'disabled', allow_duplicate = True),

        Input({'type': 'background-callback-return', 'target': 'metamodel-process'}, 'data'),
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

        logger.info('checking in metamodel after process complete %s', mm.id)
        logger.info('checking in model after process complete %s', mm.model.id)
        logger.info('checking in finance after process complete %s', mm.finance.id)

        if app.metamodels[mm.id].checked_out:
            raise ValueError(f'metamodel should not be checked out: {mm.id}')
        if app.models[mm.model.id].checked_out:
            raise ValueError(f'model should not be checked out: {mm.model.id}')
        if app.finances[mm.finance.id].checked_out:
            raise ValueError(f'finance should not be checked out: {mm.finance.id}')

        logging.info('resyncing metamodel after process completed: %s', process_request)

        # TODO: Handle failures of process

        match process_request['type']:
            case 'dsa_run_request':
                dsa_result_id = postprocess_utils.get_dsa_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES['dsa_results'],
                    mm.id
                )
                app.results[dsa_result_id] = app.cache[dsa_result_id]
            case 'psa_run_request':
                psa_result_id = postprocess_utils.get_psa_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES['psa_results'],
                    mm.id
                )
                app.results[psa_result_id] = app.cache[psa_result_id]
        
        n_bgp = max(0, app.sts.get('n_bgp', 0) - 1)
        app.sts['n_bgp'] = n_bgp

        return (
            trigger_post_metamodel_process,
            True,
            n_bgp == 0
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
        if len(trigger_ids) == 0:
            return rval

        if not isinstance(trigger_postprocess_metamodel_process, list):
            trigger_postprocess_metamodel_process = [trigger_postprocess_metamodel_process]
        
        for process_str in trigger_postprocess_metamodel_process:
            process = json.loads(process_str)
            match process['type']:
                case 'dsa_run_request':
                    for i, trigger_id in enumerate(trigger_ids):
                        if trigger_id['key'] == 'dsa-run-postprocess':
                            if isinstance(rval[i], NoUpdate):
                                rval[i] = []
                            rval[i].append(process_str)
                case 'psa_run_request':
                    for i, trigger_id in enumerate(trigger_ids):
                        if trigger_id['key'] == 'psa-run-postprocess':
                            if isinstance(rval[i], NoUpdate):
                                rval[i] = []
                            rval[i].append(process_str)
        
        return rval
    
    # Handle autorun-btn clicks
    @app.callback(
        Output({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'data'),
        Output({'type': 'autorun-btn', 'page': ALL}, 'children'),
        Output({'type': 'autorun-btn', 'page': ALL}, 'color'),
        Output({'type': 'autorun-btn', 'page': ALL}, 'outline'),

        Output('prequeue-action-user', 'data', allow_duplicate = True),

        Input({'type': 'autorun-btn', 'page': ALL}, 'n_clicks'),
        
        State({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'id'),
        State({'type': 'lock', 'target': ALL, 'stage': 'prequeue', 'key': ALL}, 'data'),
        
        State('store-configurations', 'data'),
        prevent_initial_call = True
    )
    def toggle_autorun(
        btn_clicks,

        prequeue_lock_ids,
        prequeue_lock_values,
        
        configurations,
    ):
        if len(prequeue_lock_ids) == 0:
            return ([], [no_update]*len(btn_clicks), [no_update]*len(btn_clicks), [no_update]*len(btn_clicks), no_update)
        
        current_state = True
        for id, val in zip(prequeue_lock_ids, prequeue_lock_values):
            if id.get('key') == 'user-toggle' and id.get('target') == 'model-run':
                current_state = val
                break
        
        new_state = not(current_state)

        return_states = list(prequeue_lock_values)
        for idx, id in enumerate(prequeue_lock_ids):
            if id.get('key') == 'user-toggle':
                return_states[idx] = new_state
        
        button_content = [
            html.I(
                className = icons.get_icon(
                    'autorun-true' if new_state else 'autorun-false',
                    style_name = 'raw'
                ),
                style={'display': 'inline'}
            )
        ] * len(btn_clicks)
        button_color = [
            'primary' if new_state else 'secondary'
        ] * len(btn_clicks)
        button_outline = [
            not(new_state)
        ] * len(btn_clicks)

        prequeue = no_update
        if new_state:
            if ok_run_model(prequeue_lock_ids, return_states):
                prequeue = Patch()
                for config in configurations:
                    config = json.loads(config)
                    mdl = app.models.get(config.get('model_id'))
                    if mdl is not None:
                        if mdl.dirty:
                            action = browser.model_run_request(
                                metamodel_id = config.get('metamodel_id'),
                                model_id = config.get('model_id')
                            )
                            prequeue.append(
                                json.dumps(
                                    action.as_dict()
                                )
                            )
        
        return (return_states, button_content, button_color, button_outline, prequeue)
    
    return app
