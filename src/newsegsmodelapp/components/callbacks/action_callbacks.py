"""Callbacks resulting in some processing being undertaken."""

import copy
import json
import pickle

import sys
import time
from typing import Any

from dash import ALL, Input, NoUpdate, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError
import zmq

from config import settings
from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestHandlerInterface
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelapp import registers
from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.worker import set_status_completed, set_status_failed
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash


DISPATCHSERVER = settings['DISPATCHSERVERS'][1]#'zmq-dispatcher'#
FRONTENDPORT = settings['FRONTENDPORT']
REQUEST_RETRIES = 4


def send_to_dispatcher(payload, retries: int = REQUEST_RETRIES) -> dict:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)

    #socket.setsockopt(zmq.RCVTIMEO, settings.get('JOB_DISPATCH_TIMEOUT_MS', -1))
    socket.connect(f'tcp://{DISPATCHSERVER}:{FRONTENDPORT}')

    poll = zmq.Poller()
    poll.register(socket, zmq.POLLIN)
    
    payload_bytes = pickle.dumps(payload)

    retries_left = retries
    while retries_left:
        socket.send(payload_bytes)

        expect_reply = True
        try:
            while expect_reply:
                socks = dict(poll.poll(settings.get('JOB_DISPATCH_TIMEOUT_MS', -1)))
                if socks.get(socket) == zmq.POLLIN:
                    reply_bytes = socket.recv()
                    if not reply_bytes:
                        break
                    expect_reply = False
                else:
                    print('No response from job server, retrying...')
                    # Socket is confused. Close and remove it.
                    socket.setsockopt(zmq.LINGER, 0)
                    socket.close()
                    poll.unregister(socket)
                    retries_left -= 1
                    if retries_left == 0:
                        raise ValueError('Job dispatch timed out.')
                    socket = context.socket(zmq.REQ)
                    socket.connect(f'tcp://{DISPATCHSERVER}:{FRONTENDPORT}')
                    poll.register(socket, zmq.POLLIN)
                    socket.send(payload_bytes)
        finally:
            socket.close()
            poll.unregister(socket)
            context.term()

        if not expect_reply:
            break

    # try:
    #     reply_bytes = socket.recv()
    # except zmq.Again:
    #     raise ValueError('Job dispatch timed out.')
    # finally:
    #     socket.close()
    #     context.term()

    reply_data = pickle.loads(reply_bytes)

    return reply_data

def _local_run_any(
    runner, request, engine, project_provider, results_provider
):
    job_id = generate_claim_ticket(engine, request)
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
        print(e)
        set_status_failed(engine, job_id, str(e))
        return job_id

def local_run_procedure(
    procedure_name: str, 
    request: registers.RunRequest, 
    engine: sa.Engine,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface
):
    runner = registers.RUN_PROCEDURE_REGISTER.get(procedure_name)
    if runner is None:
        print(f'runner not found for {procedure_name}')
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
    runner = registers.get_postprocess_procedure(procedure_name, request)
    if runner is None:
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
    runner = registers.get_table_draw(procedure_name, request)
    if runner is None:
        return None

    return _local_run_any(
        runner, request, engine,
        project_provider, results_provider
    )

def spawn_job(
    request: registers.RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface,
) -> int | None:
    print(f'spawning job type {request.request_type} for request {request.request_id}')

    if request.background_procedure:
        run_info = send_to_dispatcher(request)
        print(f'created background job {run_info["job_id"]}')
        return run_info['job_id']
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
            
        run_id = local_run(
            request.request_type, request, db.get_engine(),
            project_provider,
            results_provider
        )
        if run_id is None:
            print(f'Failed run - {request.request_type} {request.request_id}')
        else:
            print(f'Success - {request.request_type} {request.request_id}')
        return run_id

def generate_post_action_requests(
    original_request: registers.RunRequest,
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
    
            request_ids.append(
                request_handler.add_request(
                    procedure, proj_id, 
                    project_provider, procedure_class,
                    triggering_request = original_request,
                )
            )

    return request_ids, r_already_generated
    
def add_action_callbacks(app: NewsegsDash):
    @app.callback(
        Output({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': ALL,
            'key': ALL, 'subindex': 0
        }, 'data', allow_duplicate = True),
        Output('ongoing-actions', 'data'),
        Output('progress-poll-interval', 'disabled'),
        Output({'type': 'results-container', 'supersection': ALL, 'section': ALL}, 'data-status'),
        Output({'type': 'results-overlay-text', 'section': ALL, 'supersection': ALL}, 'children', allow_duplicate = True),
        Output({'type': 'results-progress-bar', 'section': ALL, 'supersection': ALL}, 'value'),
        Output({'type': 'results-overlay-subtext', 'section': ALL, 'supersection': ALL}, 'children'),

        Input('trigger-check-requests', 'data'),
        Input('progress-poll-interval', 'n_intervals'),

        State('ongoing-actions', 'data'),
        State({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': ALL,
            'key': ALL, 'subindex': 0
        }, 'id'),
        # State({
        #     'type': 'result-table-option', 'purpose': ALL,
        #     'supersection': ALL, 'section': ALL,
        #     'key': ALL, 'subindex': ALL
        # }, 'value'),
        # State({
        #     'type': 'result-table-option', 'purpose': ALL,
        #     'supersection': ALL, 'section': ALL,
        #     'key': ALL, 'subindex': ALL
        # }, 'id'),
        # State('active-project-id', 'data'),
        State({'type': 'results-container', 'supersection': ALL, 'section': ALL}, 'id'),
        prevent_initial_call = True
    )
    def manage_actions(
        check_requests,
        poll_intervals,

        ongoing_actions: list[int],
        postaction_trigger_ids,
        # options: list,
        # option_ids: list,
        # active_project_id,
        container_ids,
    ):
        trigger_id = ctx.triggered_id
        print(f'ACTION TRIGGERED BY {trigger_id}')
        if trigger_id is None or len(ctx.triggered) > 1:
            raise PreventUpdate
        if not isinstance(trigger_id, str) and trigger_id['type'] == 'action-button' and callback_utils.get_triggered_value() == 0:
            raise PreventUpdate
        postaction_trigger_returns: list[Any] = [no_update] * len(postaction_trigger_ids)
        failed_actions = []
        completed_actions = []
        spawned_actions = []
        spawn_ids: set[tuple] = set()
        new_jobs = False
        prog_ = no_update
        mess_ = no_update

        if isinstance(trigger_id, str):
            if trigger_id == 'trigger-check-requests':
                print('CHECKING NEW REQUESTS')
                new_requests = app.request_handler.get_new_requests()
                print(new_requests)
                for req in new_requests:
                    run_id = spawn_job(req, app.project_provider, app.results_provider)
                    if run_id:
                        ongoing_actions.append(run_id)
                        req.run_id = run_id
                        app.request_handler.mark_dispatched(req.request_id, req.run_id)
                        new_jobs = True
                    
        # Check on ongoing actions
        if ongoing_actions:
            check_job_stmt = (
                sa.select(
                    tbls.runs.c.run_id,
                    tbls.runs.c.status,
                    tbls.runs.c.progress,
                    tbls.runs.c.progress_message,
                ).where(tbls.runs.c.run_id.in_(ongoing_actions))
            )

            with db.get_engine().connect() as conn:
                job_statuses = conn.execute(check_job_stmt).fetchall()

            if not job_statuses:
                print('All jobs finished')
                ongoing_actions = []
            else:
                status_map = {x[0]: x[1] for x in job_statuses}
                for run_id in ongoing_actions:
                    
                    run_status = status_map.get(run_id, 'NOT_FOUND')
                    print(f'Checking run_id {run_id} with status {run_status}')
                    match run_status:
                        case 'NOT_FOUND':
                            failed_actions.append(run_id)
                        case 'SUCCESS':
                            completed_actions.append(run_id)
                        case 'FAILED':
                            failed_actions.append(run_id)

                if failed_actions:
                    print (f'{len(failed_actions)} actions have failed.')
                    failed_actions_stmt = (
                        sa.select(
                            tbls.requests.c.run_id,
                            tbls.requests.c.request_id,
                        )
                        .join(tbls.runs, tbls.requests.c.run_id == tbls.runs.c.run_id)
                        .where(sa.and_(
                            tbls.requests.c.run_id.in_(failed_actions),
                            sa.not_(tbls.runs.c.cancel_requested)
                            )
                        )
                    )
                    with db.get_engine().connect() as conn:
                        result = conn.execute(failed_actions_stmt)
                    run_to_request_map = dict(result.tuples().all())
                    for run_id, request_id in run_to_request_map.items():
                        do_retry = app.request_handler.increment_failure(request_id)
                        if do_retry:
                            failed_request = app.request_handler.get_request(request_id)
                            new_run_id = spawn_job(failed_request, app.project_provider, app.results_provider)
                            if new_run_id:
                                ongoing_actions.append(new_run_id)
                                failed_request.run_id = new_run_id
                                app.request_handler.mark_dispatched(
                                    failed_request.request_id, failed_request.run_id
                                )
                    
                    for run_id in failed_actions:
                        ongoing_actions.remove(run_id)

                if completed_actions:
                    completed_actions_stmt = (
                        sa.select(
                            tbls.runs.c.run_id,
                            tbls.runs.c.request_type,
                            tbls.runs.c.request_class,
                            tbls.runs.c.payload,
                            tbls.runs.c.project_id,
                            tbls.runs.c.children_spawned
                        )
                        .where(tbls.runs.c.run_id.in_(completed_actions))
                    )

                    with db.get_engine().connect() as conn:
                        result = conn.execute(completed_actions_stmt).fetchall()
                    completed_request_map = {
                        x[0]: {
                            'action_type': x[1], 
                            'action_class': x[2],
                            'payload': x[3], 
                            'project_id': x[4],
                            'children_spawned': x[5]
                        } for x in result
                    }
                    for run_id in completed_actions:
                        req_data = completed_request_map[run_id]
                        original_request = registers.RunRequest.from_dict(json.loads(req_data['payload']))
                        original_request.run_id = run_id
                        if not req_data['children_spawned']:
                            print(f'Handling the completion of job {run_id} of type {req_data["action_type"]} for project {req_data["project_id"]}')
                            action_type = req_data['action_type']
                            for idx, id in enumerate(postaction_trigger_ids):
                                if id['key'] == action_type:
                                    print(f'adding trigger for {action_type}')
                                    if isinstance(postaction_trigger_returns[idx], NoUpdate):
                                        postaction_trigger_returns[idx] = [req_data['payload']]
                                    else:
                                        postaction_trigger_returns[idx].append(req_data['payload'])

                            new_request_ids, spawn_ids = generate_post_action_requests(
                                original_request,
                                app.request_handler,
                                app.project_provider,
                                spawn_ids
                            )

                            for request_id in new_request_ids:
                                new_request = app.request_handler.get_request(request_id)
                                new_run_id = spawn_job(new_request, app.project_provider, app.results_provider)
                                if new_run_id:
                                    new_request.run_id = new_run_id
                                    app.request_handler.mark_dispatched(new_request.request_id, new_request.run_id)
                                    spawned_actions.append(new_run_id)
                            
                            app.request_handler.mark_completed(original_request.request_id)

                        n_retries = 5
                        success = False
                        while n_retries > 0 and not success:
                            try:
                                with db.get_engine().begin() as conn:
                                    conn.execute(
                                        sa.update(tbls.runs)
                                        .values(children_spawned = True)
                                        .where(tbls.runs.c.run_id.in_(completed_actions))
                                    )
                                    success = True
                            except OperationalError:
                                time.sleep(0.1)
                                n_retries -= 1
                        
                        ongoing_actions.remove(run_id)

                # By doing this once-through, we are forcing only one layer of child processes to get triggered 
                # - provided that the interval brings us back fast enough, this is a reasonable compromise to 
                # keep responsiveness.
                ongoing_actions.extend(spawned_actions)

            if ongoing_actions:
                progress_map = {x.run_id: {'progress': x.progress, 'message': x.progress_message} for x in job_statuses}

                ongoing_progress = {k: v for k, v in progress_map.items() if k in ongoing_actions}
                mess_ = f'{len(ongoing_progress)} jobs underway.\n'

                if len(ongoing_progress):

                    prog_ = 100. * sum([x['progress'] for x in ongoing_progress.values()]) / len(ongoing_progress)
                    mess_ += ' | '.join([x['message'] for x in ongoing_progress.values()])
                else:
                    prog_ = 0.

        new_jobs = new_jobs or len(spawned_actions)

        return (
            postaction_trigger_returns,
            ongoing_actions,
            len(ongoing_actions) == 0,
            (['CALCULATING'] if len(ongoing_actions) > 0 else ['IDLE']) * len(container_ids),
            (['Computing...'] if new_jobs else [no_update]) * len(container_ids),
            [prog_] * len(container_ids),
            [mess_] * len(container_ids),
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

        print ('Requesting cancel of all jobs.')

        cancel_all_jobs = (
            sa.update(tbls.runs)
            .where(tbls.runs.c.status.not_in(['SUCCESS', 'FAILED']))
            .values(cancel_requested = True)
        )

        with db.get_engine().begin() as conn:
            conn.execute(cancel_all_jobs)

        rval = callback_utils.create_noupdate_return()
        return ['Cancelling...'] * len(rval)
        