"""Callbacks resulting in some processing being undertaken."""

import copy
import json
import random
from typing import Any
import warnings

from dash import ALL, MATCH, Input, NoUpdate, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import sqlalchemy as sa
import zmq

from config import settings
from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestHandlerInterface
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelapp import registers
from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.worker import _set_status_completed, _set_status_failed
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash


DISPATCHSERVER = 'zmq-dispatcher'#settings['DISPATCHSERVERS'][0]
FRONTENDPORT = settings['FRONTENDPORT']

def send_to_dispatcher(payload) -> dict:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f'tcp://{DISPATCHSERVER}:{FRONTENDPORT}')

    socket.send_pyobj(payload)

    return socket.recv_pyobj()

def _local_run_any(
    runner, request, engine, project_provider, results_provider
):
    job_id = generate_claim_ticket(engine, request)
    try:
        is_ok = runner(
            request,
            project_provider,
            results_provider,
            job_id,
            lambda x,y,z: None,
            lambda: False
        )

        _set_status_completed(engine, job_id)
        return job_id
    except Exception as e:
        print(e)
        _set_status_failed(engine, job_id, str(e))
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

        # Input({
        #     'type': 'action-button', 'purpose': ALL, 
        #     'supersection': ALL, 'section': ALL,
        #     'key': ALL, 'subindex': ALL
        # }, 'n_clicks'),
        Input('trigger-check-requests', 'data'),
        # Input({
        #     'type': 'postaction-trigger', 'purpose': 'trigger',
        #     'supersection': 'global', 'section': ALL,
        #     'key': ALL, 'subindex': 0
        # }, 'data'), # Generally, this won't feature as won't be triggered by feedback. However, there are a few external loaders which may set the postprocess sequence running.
        Input('progress-poll-interval', 'n_intervals'),

        State('ongoing-actions', 'data'),
        State({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': ALL,
            'key': ALL, 'subindex': 0
        }, 'id'),
        State({
            'type': 'result-table-option', 'purpose': ALL,
            'supersection': ALL, 'section': ALL,
            'key': ALL, 'subindex': ALL
        }, 'value'),
        State({
            'type': 'result-table-option', 'purpose': ALL,
            'supersection': ALL, 'section': ALL,
            'key': ALL, 'subindex': ALL
        }, 'id'),
        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def manage_actions(
        #action_button_clicks,
        check_requests,
        #postaction_triggers,
        poll_intervals,

        ongoing_actions: list[int],
        postaction_trigger_ids,
        options: list,
        option_ids: list,
        active_project_id,
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

        # if not isinstance(trigger_id, str):
        #     # An action button or ???
        #     action_purpose = trigger_id.get('purpose')
        #     if action_purpose == 'request-process':
        #         # Handle new action creation.
        #         action_class = trigger_id.get('section')
        #         action_type = trigger_id.get('key')
        #         match trigger_id.get('type'):
        #             case 'action-button':
        #                 if not callback_utils.get_triggered_value():
        #                     raise PreventUpdate
        #                 print(f'handling action from {trigger_id.get('type')}: ', action_type)
        #                 config = {k: v for k,v in trigger_id.items()}
        #                 # Two ways of picking up configuration from result-table-option inputs:
        #                 # Their value, and their subindex.
        #                 for id, val in zip(option_ids, options):
        #                     if id['key'] == action_type:
        #                         config[id['purpose']] = val
        #                         config[id['purpose']+'_subindex'] = id['subindex']

        #                 run_id = spawn_job(
        #                     action_type, action_class, active_project_id, 
        #                     app.project_provider, app.results_provider, None,
        #                     config = config
        #                 )
        #                 if run_id:
        #                     ongoing_actions.append(run_id)
        #     elif action_purpose == 'trigger':
        #         # A postaction trigger from a non-feedback process
        #         requests = callback_utils.get_triggered_value()
        #         if not isinstance(requests, list):
        #             raise TypeError('postaction triggers should contain a list of jsonified requests - got {type(requests)}')
        #         for req_json in requests:
        #             req_data = json.loads(req_json)
        #             action_type = req_data['request_type']
        #             print(f'handling postaction from {trigger_id.get('type')}: ', action_type)
        #             new_actions = registers.POST_ACTION_REGISTER.get(action_type)
        #             if new_actions:
        #                 run_id = req_data.get('run_id', -random.randrange(1, 10000))
        #                 for run_procedure in new_actions.run_procedures:
        #                     # Prevent adding the same procedure twice in the same callback
        #                     spawn_id = (run_procedure, run_id)
        #                     if spawn_id in spawn_ids:
        #                         continue
        #                     spawn_ids.add(spawn_id)
                            
        #                     new_run_id = spawn_job(
        #                         run_procedure, 'run',
        #                         req_data['project_id'], 
        #                         app.project_provider, app.results_provider,
        #                         registers.RunRequest.from_dict(req_data)
        #                     )
        #                     if new_run_id:
        #                         spawned_actions.append(new_run_id)
        #                 for postproc_procedure in new_actions.postprocess_procedures:
        #                     # Prevent adding the same procedure twice in the same callback
        #                     spawn_id = (postproc_procedure[0], run_id)
        #                     if spawn_id in spawn_ids:
        #                         continue
        #                     spawn_ids.add(spawn_id)
        #                     new_run_id = spawn_job(
        #                         postproc_procedure[0], 'postprocess',
        #                         req_data['project_id'], 
        #                         app.project_provider, app.results_provider,
        #                         registers.RunRequest.from_dict(req_data)
        #                     )
        #                     if new_run_id:
        #                         spawned_actions.append(new_run_id)
        #                 for table_draw_procedure in new_actions.table_draw_artists:
        #                     # Prevent adding the same procedure twice in the same callback
        #                     spawn_id = (table_draw_procedure[0], run_id)
        #                     if spawn_id in spawn_ids:
        #                         continue
        #                     spawn_ids.add(spawn_id)
        #                     new_run_id = spawn_job(
        #                         table_draw_procedure[0], 'tabledraw',
        #                         req_data['project_id'], 
        #                         app.project_provider, app.results_provider,
        #                         registers.RunRequest.from_dict(req_data)
        #                     )
        #                     if new_run_id:
        #                         spawned_actions.append(new_run_id)
                    
        # Check on ongoing actions
        if ongoing_actions:
            check_job_stmt = (
                sa.select(
                    tbls.runs.c.run_id,
                    tbls.runs.c.status,
                ).where(tbls.runs.c.run_id.in_(ongoing_actions))
            )

            with db.get_engine().connect() as conn:
                job_statuses = conn.execute(check_job_stmt).fetchall()

            if not job_statuses:
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
                        with db.get_engine().begin() as conn:
                            conn.execute(
                                sa.update(tbls.runs)
                                .values(children_spawned = True)
                                .where(tbls.runs.c.run_id.in_(completed_actions))
                            )
                        
                        ongoing_actions.remove(run_id)

                # By doing this once-through, we are forcing only one layer of child processes to get triggered 
                # - provided that the interval brings us back fast enough, this is a reasonable compromise to 
                # keep responsiveness.
                ongoing_actions.extend(spawned_actions)        

        return (
            postaction_trigger_returns,
            ongoing_actions,
            len(ongoing_actions) == 0,
        )

    # Loading overlays
    @app.callback(
        Output({'type': 'results-container', 'supersection': ALL, 'section': ALL}, 'data-status'),
        Input('progress-poll-interval', 'n_intervals'),
        State({'type': 'results-container', 'supersection': ALL, 'section': ALL}, 'id'),
        prevent_initial_call = True
    )
    def set_loading_overlay(n_intervals, container_ids):
        # Can switch to a MATCH if we don't want to cover all results.
        stmt = (
            sa.select(tbls.runs.c.status)
            .where(tbls.runs.c.status == 'CALCULATING')
        )

        with db.get_engine().connect() as conn:
            row = conn.execute(stmt).fetchone()

            if not row:
                return ['IDLE'] * len(container_ids)
            return ['CALCULATING'] * len(container_ids)
        