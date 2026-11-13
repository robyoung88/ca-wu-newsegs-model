"""Callbacks which result in processing being undertaken: creating requests from user actions, starting them and following their progress.
"""
import logging
import threading
logger = logging.getLogger(__name__)

import copy
import json
import pickle

from typing import Any, Optional, Sequence

from dash import ALL, Input, NoUpdate, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import sqlalchemy as sa
import zmq

from config import settings
from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestCancelledError, RequestHandlerInterface
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelapp import registers
from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db_jobs import is_retryable, prevent_request_retry, set_status_completed
from newsegsmodelapp.backend.worker import set_status_failed
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash


DISPATCHSERVER = settings['DISPATCHSERVERS'][1]#'zmq-dispatcher'#
FRONTENDPORT = settings['FRONTENDPORT']


def send_to_dispatcher(
    payload,
    server_address: Optional[str] = None,
    frontend_port: Optional[str] = None
):
    """Send a request to the dispatcher over ZeroMQ, and wait for its reply.

    Retries up to `retries` times if the dispatcher does not reply within the timeout.

    Args:
        payload: The request to send after pickling.
    """
    server_address = DISPATCHSERVER if server_address is None else server_address
    frontend_port = FRONTENDPORT if frontend_port is None else frontend_port

    def _reconnect(sock: zmq.Socket):
        sock.connect(f'tcp://{server_address}:{frontend_port}')

    context = zmq.Context()
    socket = context.socket(zmq.DEALER)
    socket.setsockopt(zmq.LINGER, -1)

    _reconnect(socket)

    payload_bytes = pickle.dumps(payload)

    socket.send_multipart([b"", payload_bytes])

    # Immediately close; do not block, waiting for a synchronous reply
    socket.close()

def _local_run_any(
    runner, request, engine, project_provider, results_provider
):
    try:
        job_id, job_exists = generate_claim_ticket(engine, request)
    except RequestCancelledError:
        logger.info('Request ID = %d; is has been cancelled prior to run', request.request_id)
        return None
    if job_exists:
        logger.info('Request ID = %d; is being fulfilled by an existing Run ID = %d', request.request_id, job_id)
    try:
        rq = copy.copy(request)
        rq.run_id = job_id
        is_ok = runner(
            rq,
            project_provider,
            results_provider,
            job_id,
            lambda x,y,z: None,
            lambda: False
        )

        set_status_completed(engine, job_id)
        return job_id
    except Exception as e:
        logger.exception('Local run Run ID: %d; has failed with exception', job_id, exc_info = True)
        if not is_retryable(e):
            prevent_request_retry(engine, request.request_id)
        set_status_failed(engine, job_id, str(e))
        return job_id

def local_run_procedure(
    procedure_name: str, 
    request: registers.RunRequest, 
    engine: sa.Engine,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface
):
    """Run a registered run procedure in the app process, instead of in a worker.

    Used for requests that are not background procedures. Logs an exception and returns None if the procedure is not registered.

    Args:
        procedure_name: Name of the procedure to run.
        request: The request which triggered the procedure.
        engine: SQLAlchemy engine.
        project_provider: Provider of projects, metamodels and variables.
        results_provider: Provider of results.

    Returns:
        The status message of the procedure.
    """
    runner = registers.RUN_PROCEDURE_REGISTER.get(procedure_name)
    if runner is None:
        logger.exception('Runner not found in RUN_PROCEDURE_REGISTER for procedure name: %s', procedure_name)
        return None
    
    return _local_run_any(
        runner, request, engine,
        project_provider, results_provider
    )

def local_run_postprocess(
    procedure_name: str, 
    request: registers.RunRequest, 
    engine: sa.Engine,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface
):
    """Run a registered postprocess procedure in the app process, instead of in a worker.

    Logs an exception and returns None if the procedure is not registered.

    Args:
        procedure_name: Name of the procedure to run.
        request: The request which triggered the procedure.
        engine: SQLAlchemy engine.
        project_provider: Provider of projects, metamodels and variables.
        results_provider: Provider of results.

    Returns:
        The status message of the procedure.
    """
    runner = registers.get_postprocess_procedure(procedure_name, request)
    if runner is None:
        logger.exception('Runner not found in POSTPROCESS_PROCEDURE_REGISTER for procedure name: %s', procedure_name)
        return None

    return _local_run_any(
        runner, request, engine,
        project_provider, results_provider
    )

def local_run_table_draw(
    procedure_name: str, 
    request: registers.RunRequest, 
    engine: sa.Engine,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface
):
    """Run a registered table draw procedure in the app process, instead of in a worker.

    Logs an exception and returns None if the procedure is not registered.

    Args:
        procedure_name: Name of the procedure to run.
        request: The request which triggered the procedure.
        engine: SQLAlchemy engine.
        project_provider: Provider of projects, metamodels and variables.
        results_provider: Provider of results.

    Returns:
        The status message of the procedure.
    """
    runner = registers.get_table_draw(procedure_name, request)
    if runner is None:
        logger.exception('Runner not found in TABLE_DRAW_REGISTER for procedure name: %s', procedure_name)
        return None

    return _local_run_any(
        runner, request, engine,
        project_provider, results_provider
    )

def spawn_job(
    request: registers.RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface,
    request_handler: RequestHandlerInterface,
    server_address: Optional[str] = None,
    frontend_port: Optional[str] = None
) -> None:
    """Start the run of a request: send it to the dispatcher if it is a background procedure, otherwise run it in the app.

    If the dispatcher refuses a background request its run id is cleared and its status is not changed.

    Args:
        request: The request which triggered the procedure.
        project_provider: Provider of projects, metamodels and variables.
        results_provider: Provider of results.
        server_address: (optional) address of the zmq broker
        frontend_port: (optional) frontend port of the zmq proxy

    Returns:
        The id of the run, or None if the request was not started.
    """
    logger.info(
        'Spawning Run for Request ID %d; Type: %s;',
        request.request_id, request.request_type
    )

    if request.background_procedure:
        # Mark the request as sent immediately before sending - do not wait until after in case
        # we have contention with the worker picking it up

        server_address = DISPATCHSERVER if server_address is None else server_address
        frontend_port = FRONTENDPORT if frontend_port is None else frontend_port
        
        request_handler.set_request_status(
            request.request_id,
            'AWAITING WORKER',
        )
        send_to_dispatcher(request, server_address, frontend_port)

        return None

    else:
        match request.request_class:
            case 'run':
                local_run = local_run_procedure
            case 'postprocess':
                local_run = local_run_postprocess
            case 'tabledraw':
                local_run = local_run_table_draw
            case _:
                return None

        logger.info(
            'Local initiation of procedure %s for Request ID = %d; Triggering Request ID = %d',
            request.request_type, request.request_id,
            request.trigger_request_id
        )
        run_id = local_run(
            request.request_type, request, db.get_engine(writer = True),
            project_provider,
            results_provider
        )
        if run_id is None:
            logger.warning(
                'Local failure of procedure %s for Request ID = %d; Triggering Request ID = %d',
                request.request_type, request.request_id,
                request.trigger_request_id
            )
        else:
            logger.info(
                'Local completion of procedure %s for Request ID = %d; Run ID = %d, Triggering Request ID = %d',
                request.request_type, request.request_id,
                run_id, request.trigger_request_id
            )
            request.run_id = run_id
            # Only mark as PROCESSING, as the completed run needs handling before FULFILLED
            request.status = 'PROCESSING'
        return 

def generate_post_action_requests(
    original_request: registers.RunRequest | Sequence[registers.RunRequest],
    request_handler: RequestHandlerInterface,
    project_provider: NewsegsProjectProviderInterface,
    already_generated: set[tuple[str, int]] | None = None
) -> tuple[list[int], set[tuple[str, int]]]:
    """Generate requests for processes triggered by an action completion.
    
    Returns:
        list[int] - request_id of generated requests
        set[tuple[str,str]] - set of post-action requests already generated to prevent duplication.
    """
    request_ids = []
    r_already_generated = set() if already_generated is None else already_generated.copy()

    if not isinstance(original_request, registers.RunRequest):
        # For now, just recurse - can optimise number of writes later.
        for req in original_request:
            rids, r_already_generated = generate_post_action_requests(
                req,
                request_handler, project_provider, r_already_generated
            )
            request_ids.extend(rids)

        return request_ids, r_already_generated

    action_type = original_request.request_type
    orq_id = original_request.request_id
    proj_id = original_request.project_id

    new_actions = registers.POST_ACTION_REGISTER.get(action_type)

    if not new_actions:
        return request_ids, r_already_generated

    procclasslist = (
        ('run', new_actions.run_procedures),
        ('postprocess', [x[0] for x in new_actions.postprocess_procedures]),
        ('tabledraw', [x[0] for x in new_actions.table_draw_artists])
    )

    for procedure_class, procedure_list in procclasslist:
        for procedure in procedure_list:
            proc_id = (procedure, orq_id)
            if proc_id in r_already_generated:
                continue
            r_already_generated.add(proc_id)

            added_request = request_handler.add_request(
                procedure, proj_id, 
                project_provider, procedure_class,
                triggering_request = original_request,
            )

            request_ids.append(added_request.request_id)
            logger.info(
                'Added Postaction Child Request of Request ID = %d; Type = %s; Fulfilled by Run ID = %d; Child has Request ID = %d; Type = %s;',
                original_request.request_id, original_request.request_type, 
                original_request.run_id, request_ids[-1], 
                procedure
            )

    return request_ids, r_already_generated

def _get_run_statuses(
    ongoing_run_ids: list[str]
) -> dict[str, dict]:
    """Critical status for ongoing runs.

    Args:
        ongoing_run_ids: Ids of the runs.

    Returns:
        The status, progress and progress message of each of the runs, by run id.
    """
    stmt = (
        sa.select(
            tbls.runs.c.run_id,
            tbls.runs.c.status,
            tbls.runs.c.progress,
            tbls.runs.c.progress_message,
        )
        .where(tbls.runs.c.run_id.in_(ongoing_run_ids))
    )

    with read_transaction(db.get_engine()) as conn:
        result = conn.execute(stmt).fetchall()
    if not result:
        return {}
    return {x[0]: dict(x._mapping) for x in result}

def results_status(
    calculating: bool,
    failure_messages: Sequence[str],
    new_jobs: bool,
    progress_message: str | NoUpdate,
) -> tuple[str, str | NoUpdate, str | NoUpdate]:
    """The status of the results containers, and the title and subtitle of their overlay.

    While requests are active the containers are `CALCULATING`. Once none are, they are `FAILED` if
    any run of the batch was abandoned, showing why, or else `IDLE`.

    Args:
        calculating: Whether any request is active: being run, or waiting to be.
        failure_messages: Messages of the runs abandoned since the batch started.
        new_jobs: Whether new runs have been spawned.
        progress_message: Message of the progress of the runs underway.

    Returns:
        The status, title and subtitle.
    """
    if calculating:
        return 'CALCULATING', 'Computing...' if new_jobs else no_update, progress_message
    if failure_messages:
        title = 'A job failed' if len(failure_messages) == 1 else f'{len(failure_messages)} jobs failed'
        # Retries of the same request may fail in the same way
        return 'FAILED', title, ' | '.join(dict.fromkeys(failure_messages))
    return 'IDLE', no_update, progress_message

def add_action_callbacks(app: NewsegsDash):

    """Bind the callbacks which turn user actions into requests, start them, monitor their progress and trigger their post-actions.

    The callbacks create requests with the functions registered for the actions, start new requests with `spawn_job`, poll the state of active requests and respawn failed requests while retries remain.

    Args:
        app: The Dash app.
    """
    def _respawn_run_for_request(
        request: registers.RunRequest,
    ) -> int | None:
        do_retry = app.request_handler.increment_failure(request.request_id)
        if do_retry:
            logger.info(
                'Action Manager handling Request ID: %d; Type: %s; ' 
                'Child of Triggering Request ID = %d; as Failed Request, will spawn job.',
                request.request_id, request.request_type,
                request.trigger_request_id,
            )

            return spawn_job(request, app.project_provider, app.results_provider, app.request_handler)
        else:
            logger.warning(
                'Action Manager ABANDONING Request ID: %d; Type: %s; ' 
                'Child of Triggering Request ID = %d; as Failed Request, no more Retries.',
                request.request_id, request.request_type,
                request.trigger_request_id,
            )
        return -1

    action_manager_lock = threading.Lock()
    @app.callback(
        Output({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': ALL,
            'key': ALL, 'subindex': 0
        }, 'data', allow_duplicate = True),
        Output('ongoing-actions', 'data'),
        Output('failed-actions', 'data'),
        Output('progress-poll-interval', 'disabled'),
        Output({'type': 'results-container', 'supersection': ALL, 'section': ALL}, 'data-status'),
        Output({'type': 'results-overlay-text', 'section': ALL, 'supersection': ALL}, 'children', allow_duplicate = True),
        Output({'type': 'results-progress-bar', 'section': ALL, 'supersection': ALL}, 'value'),
        Output({'type': 'results-overlay-subtext', 'section': ALL, 'supersection': ALL}, 'children'),

        Input('trigger-check-requests', 'data'),
        Input('progress-poll-interval', 'n_intervals'),

        State('ongoing-actions', 'data'),
        State('failed-actions', 'data'),
        State({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': ALL,
            'key': ALL, 'subindex': 0
        }, 'id'),
        State({'type': 'results-container', 'supersection': ALL, 'section': ALL}, 'id'),
        prevent_initial_call = True
    )
    def manage_actions(
        check_requests,
        poll_intervals,

        ongoing_actions: list[int],
        failure_messages: list[str],
        postaction_trigger_ids,
        container_ids,
    ):
        haslock = action_manager_lock.acquire(blocking = False)
        if not haslock:
            raise PreventUpdate
        try:
            # Either trigger (a request, or the poll) asks for the same check, so it is run once whichever fire
            triggers = callback_utils.get_triggers()
            if not triggers:
                raise PreventUpdate
            logger.debug('Action manager triggered by %s', [x.id for x in triggers])
            logger.debug('Ongoing actions at start of manager are: %s', ongoing_actions)

            postaction_trigger_returns: list[Any] = [no_update] * len(postaction_trigger_ids)
            # A new batch of jobs, started with none underway, clears the failures of the last
            batch_starting = len(ongoing_actions) == 0
            ongoing_actions = set(ongoing_actions)
            failures_before = list(failure_messages or [])
            failure_messages = list(failures_before)
            failed_actions = []
            completed_actions = []
            spawned_actions = []
            spawn_ids: set[tuple] = set()
            new_jobs = False
            prog_ = no_update
            mess_ = no_update

            retry_spawns = False
            """Set if the callback needs to be fired again due to failed Run spawns.
            
            Needs to be set if there are requests left undispatched in the request handler.
            """

            request_list = app.request_handler.get_active_requests()
            new_requests = [x for x in request_list if x.status == 'AWAITING DISPATCH']

            for req in new_requests:
                logger.info(
                    'Action Manager handling Request ID = %d; Type = %s; as New Request, will spawn job.',
                    req.request_id, req.request_type
                )
                
                spawn_job(
                    req, 
                    app.project_provider, app.results_provider, app.request_handler
                )

            # These requests have not yet been picked up, and should be checked to see if it's worth
            # retrying
            slow_requests = app.request_handler.get_slow_requests()
            if slow_requests:
                for req in slow_requests:
                    logger.info(
                        'Action Manager handling Request ID = %d; Type = %s; as Slow Request, will spawn job.',
                        req.request_id, req.request_type
                    )
                    spawn_job(
                        req, 
                        app.project_provider, app.results_provider, app.request_handler
                    )          
            
            # Pull the active requests again, as spawning changes their statuses
            request_list = app.request_handler.get_active_requests()

            # Pull the run list from the request list - this should match the ongoing actions list
            ongoing_run_ids = [x.run_id for x in request_list if x.status == 'PROCESSING']

            if set(ongoing_run_ids) != ongoing_actions:
                s_req = set(ongoing_run_ids)
                s_actionlist = set(ongoing_actions)
                only_in_requests = s_req - s_actionlist
                only_in_actionlist = s_actionlist - s_req
                if only_in_requests:
                    logger.warning('Run IDs found only from Requests table: %s', only_in_requests)
                if only_in_actionlist:
                    logger.warning('Run IDs found only in triggering action list: %s', only_in_actionlist)
                logging.warning('Discrepancy in Run ID list will be resolved by using only that from requests.')

            if ongoing_run_ids:
                run_statuses = _get_run_statuses(ongoing_run_ids)

                completed_run_ids = [k for k, v in run_statuses.items() if v['status'] == 'SUCCESS']
                failed_run_ids = [k for k, v in run_statuses.items() if v['status'] == 'FAILED']

                missing_run_ids = set(ongoing_run_ids) - set(run_statuses.keys())
                if missing_run_ids:
                    logger.warning('Run IDs missing from run table, treating as failed: %s', missing_run_ids)
                    failed_run_ids.extend(list(missing_run_ids))

                if failed_run_ids:
                    failed_run_ids = set(failed_run_ids)
                    requests_with_failed_runs = [x for x in request_list if x.run_id in failed_run_ids]

                    for request in requests_with_failed_runs:
                        new_run_id = _respawn_run_for_request(request)
                        if new_run_id is None:
                            logger.warning(
                                'Unable to Spawn Run for Request ID = %d; Type = %s; '
                                'Should be retried on next run through.',
                                request.request_id, request.request_type
                            )

                            retry_spawns = True
                        
                        elif new_run_id >= 0:
                            logger.debug(
                                'Appending to ongoing actions: Newly spawned Run [Run ID = %d;] for Request ID = %d; Type = %s;',
                                new_run_id, request.request_id, request.request_type
                            )
        
                            ongoing_run_ids.append(new_run_id)
                            new_jobs = True
                        
                        else:
                            # Return of a negative indicates no more retries available;
                            # Request should already be marked as CANCELLED, so report the failure
                            message = run_statuses.get(request.run_id, {}).get('progress_message')
                            failure_messages.append(message or f'{request.request_type} failed without a message')

                    for run_id in failed_run_ids:
                        logger.debug('Removing Failed Run from list of ongoing actions: Run ID = %d;', run_id)
                        ongoing_run_ids.remove(run_id)

                if completed_run_ids:
                    require_child_requests = []

                    completed_run_ids = set(completed_run_ids)
                    requests_with_completed_runs = [x for x in request_list if x.run_id in completed_run_ids]

                    for request in requests_with_completed_runs:
                        run_status = run_statuses[request.run_id]

                        logger.info(
                            'Action Manager handling completion of Request ID = %d; Type = %s; as Completed Request due to Run ID = %d; will set triggers and create child requests.',
                            request.request_id, request.request_type, request.run_id,
                        )

                        # Set triggers: the request's own, and those of any other tables it drew, such as
                        # each configuration's tables drawn with a whole project's (#206)
                        sections_drawn = registers.get_table_sections_drawn(request.request_type)
                        for idx, id in enumerate(postaction_trigger_ids):
                            if id['key'] in sections_drawn:
                                logger.info('Setting postaction trigger: %s', id['key'])
                                if isinstance(postaction_trigger_returns[idx], NoUpdate):
                                    postaction_trigger_returns[idx] = [json.dumps(request.as_dict())]
                                else:
                                    postaction_trigger_returns[idx].append(json.dumps(request.as_dict()))

                        require_child_requests.append(request)

                    # Generate child requests
                    new_request_ids, spawn_ids = generate_post_action_requests(
                        require_child_requests,
                        app.request_handler,
                        app.project_provider,
                        spawn_ids
                    )

                    for request_id in new_request_ids:
                        new_request = app.request_handler.get_request(request_id)
                        logger.info(
                            'Action Manager handling Request ID: %d; Type: %s; as New Request (Child), will spawn job.',
                            new_request.request_id, new_request.request_type
                        )
                        spawn_job(new_request, app.project_provider, app.results_provider, app.request_handler)

                    logger.info(
                        'Action Manager marking Runs with Run IDs %s as having spawned all necessary children.',
                        completed_run_ids
                    )
                    set_status_completed(db.get_engine(writer = True), completed_run_ids)

                    # Now that Runs have been made safe, can mark the Requests as completed.
                    completed_request_ids = [x.request_id for x in requests_with_completed_runs]
                    app.request_handler.mark_completed(completed_request_ids)

                    for run_id in completed_run_ids:
                        logger.debug('Removing Completed Run from list of ongoing actions: Run ID = %d;', run_id)
                        ongoing_run_ids.remove(run_id)

                    # By doing this once-through, we are forcing only one layer of child processes to get triggered 
                    # - provided that the interval brings us back fast enough, this is a reasonable compromise to 
                    # keep responsiveness.
                    ongoing_run_ids.extend(spawned_actions)

                if ongoing_run_ids:
                    ongoing_progress_map = {k:v for k, v in run_statuses.items() if k in ongoing_run_ids}
                    progress_map = {x['run_id']: {'progress': x['progress'], 'message': x['progress_message']} for x in ongoing_progress_map.values()}

                    ongoing_progress = {k: v for k, v in progress_map.items() if k in ongoing_actions}
                    mess_ = f'{len(ongoing_progress)} jobs underway.\n'

                    if len(ongoing_progress):

                        prog_ = 100. * sum([x['progress'] for x in ongoing_progress.values()]) / len(ongoing_progress)
                        mess_ += ' | '.join([x['message'] for x in ongoing_progress.values() if x['message'] is not None])
                    else:
                        prog_ = 0.

            new_jobs = new_jobs or len(spawned_actions)
            if batch_starting and new_jobs:
                failure_messages = [m for m in failure_messages if m not in failures_before]

            logger.debug('Ongoing actions at end of manager are: %s', ongoing_run_ids)

            # Requests still active, read now that completed runs are handled: they include the children just
            # created, which have no run until a worker claims them. Polling must go on until none are left, or
            # the completion of the children is never handled and their own post-actions never start (#206).
            requests_active = retry_spawns or len(app.request_handler.get_active_requests()) > 0

        finally:
            action_manager_lock.release()

        status, title, subtitle = results_status(requests_active, failure_messages, new_jobs, mess_)
        return (
            postaction_trigger_returns,
            ongoing_run_ids,
            failure_messages,
            not requests_active,
            [status] * len(container_ids),
            [title] * len(container_ids),
            [prog_] * len(container_ids),
            [subtitle] * len(container_ids),
        )

    @app.callback(
        Output({'type': 'results-overlay-text', 'section': ALL, 'supersection': ALL}, 'children', allow_duplicate = True),
        Input({'type': 'cancel-job-button', 'section': ALL, 'supersection': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def cancel_job(n_clicks):
        clicks = callback_utils.get_triggered_value()
        if not clicks:
            raise PreventUpdate

        logger.warning('Requesting cancel of all jobs.')

        requests_cancelled = app.request_handler.cancel_requests()

        rval = callback_utils.create_noupdate_return()
        return [f'Cancelling {len(requests_cancelled)} requests...'] * len(rval)
        