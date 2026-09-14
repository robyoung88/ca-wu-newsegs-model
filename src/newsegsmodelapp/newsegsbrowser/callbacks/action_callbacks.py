"""Callbacks resulting in some processing being undertaken."""

import copy
import json
from typing import Any
import warnings

from dash import ALL, Input, NoUpdate, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import sqlalchemy as sa
import zmq

from config import settings
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
    procedure_name: str,
    procedure_class: str,
    
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    results_provider: NewsegsResultProviderInterface,
    triggering_request: registers.RunRequest | None,

) -> int | None:
    print(f'spawning job type {procedure_name}')

    # 1. Make request
    match procedure_class:
        case 'run':
            get_req = registers.RUN_REQUEST_REGISTER[procedure_name]
            request = get_req(active_project_id, project_provider)
        case 'postprocess':
            if triggering_request is None:
                return None
            get_req = registers.POSTPROCESS_REQUEST_REGISTER.get(procedure_name)
            if get_req:
                request = get_req(triggering_request)
            else:
                request = triggering_request
        case 'tabledraw':
            if triggering_request is None:
                return None
            get_req = registers.TABLE_DRAW_REQUEST_REGISTER.get(procedure_name)
            if get_req:
                request = get_req(triggering_request)
            else:
                request = triggering_request
        case _:
            print(f'Procedure class not recognised: {procedure_class}')
            return None

    if request.background_procedure:
        run_info = send_to_dispatcher(request)
        return run_info['job_id']
    else:
        match procedure_class:
            case 'run':
                local_run = local_run_procedure    
            case 'postprocess':
                local_run = local_run_postprocess
            case 'tabledraw':
                local_run = local_run_table_draw
            case _:
                return None
            
        run_id = local_run(
            procedure_name, request, db.get_engine(),
            project_provider,
            results_provider
        )
        if run_id is None:
            print(f'Failed run - {procedure_name}')
        else:
            print(f'Success - {procedure_name}')
        return run_id
    
def add_action_callbacks(app: NewsegsDash):
    @app.callback(
        Output({'type': 'postaction-trigger', 'purpose': ALL, 'section': ALL}, 'data'),
        Output('ongoing-actions', 'data'),
        Output('progress-poll-interval', 'disabled'),

        Input({'type': 'action-button', 'purpose': ALL, 'section': ALL,}, 'n_clicks'),
        #Input({'type': 'postaction-trigger', 'purpose': ALL, 'section': ALL}, 'data'),
        Input('progress-poll-interval', 'n_intervals'),

        State('ongoing-actions', 'data'),
        State({'type': 'postaction-trigger', 'purpose': ALL, 'section': ALL}, 'id'),
        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def manage_actions(
        action_button_clicks,
        #postaction_trigger_data,
        poll_intervals,

        ongoing_actions: list[int],
        postaction_trigger_ids,
        active_project_id,
    ):
        trigger_id = ctx.triggered_id
        if trigger_id is None:
            raise PreventUpdate

        postaction_trigger_returns: list[Any] = [no_update] * len(postaction_trigger_ids)

        if not isinstance(trigger_id, str):
            # An action button or ???
            # Handle new action creation.
            action_type = trigger_id.get('purpose')
            action_class = trigger_id.get('section')
            match trigger_id.get('type'):
                case 'action-button':
                    if not callback_utils.get_triggered_value():
                        raise PreventUpdate
                    print('handling action from button: ', action_type)
                    run_id = spawn_job(action_type, action_class, active_project_id, app.project_provider, app.results_provider, None)
                    if run_id:
                        ongoing_actions.append(run_id)
                    

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
                failed_actions = []
                completed_actions = []
                spawned_actions = []
                spawn_ids: set[tuple] = set()
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
                    # TODO: Retry or otherwise deal with failure.
                    for run_id in failed_actions:
                        ongoing_actions.remove(run_id)
                if completed_actions:
                    completed_actions_stmt = (
                        sa.select(
                            tbls.runs.c.run_id,
                            tbls.runs.c.request_type,
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
                            'purpose': x[1], 
                            'payload': x[2], 
                            'project_id': x[3],
                            'children_spawned': x[4]
                        } for x in result
                    }
                    for run_id in completed_actions:
                        req_data = completed_request_map.get(run_id)
                        if req_data is not None and not req_data['children_spawned']:
                            print(f'Handling the completion of job {run_id} of type {req_data["purpose"]} for project {req_data["project_id"]}')
                            purpose = req_data['purpose']
                            for idx, id in enumerate(postaction_trigger_ids):
                                if id['purpose'] == purpose:
                                    if isinstance(postaction_trigger_returns[idx], NoUpdate):
                                        postaction_trigger_returns[idx] = [req_data['payload']]
                                    else:
                                        postaction_trigger_returns[idx].append(req_data['payload'])
                            new_actions = registers.POST_ACTION_REGISTER.get(purpose)
                            if new_actions:
                                for run_procedure in new_actions.run_procedures:
                                    # Prevent adding the same procedure twice in the same callback
                                    spawn_id = (run_procedure, run_id)
                                    if spawn_id in spawn_ids:
                                        continue
                                    spawn_ids.add(spawn_id)
                                    
                                    new_run_id = spawn_job(
                                        run_procedure, 'run',
                                        req_data['project_id'], 
                                        app.project_provider, app.results_provider,
                                        registers.RunRequest.from_dict(json.loads(req_data['payload']))
                                    )
                                    if new_run_id:
                                        spawned_actions.append(new_run_id)
                                for postproc_procedure in new_actions.postprocess_procedures:
                                    # Prevent adding the same procedure twice in the same callback
                                    spawn_id = (postproc_procedure[0], run_id)
                                    if spawn_id in spawn_ids:
                                        continue
                                    spawn_ids.add(spawn_id)
                                    new_run_id = spawn_job(
                                        postproc_procedure[0], 'postprocess',
                                        req_data['project_id'], 
                                        app.project_provider, app.results_provider,
                                        registers.RunRequest.from_dict(json.loads(req_data['payload']))
                                    )
                                    if new_run_id:
                                        spawned_actions.append(new_run_id)
                                for table_draw_procedure in new_actions.table_draw_artists:
                                    # Prevent adding the same procedure twice in the same callback
                                    spawn_id = (table_draw_procedure[0], run_id)
                                    if spawn_id in spawn_ids:
                                        continue
                                    spawn_ids.add(spawn_id)
                                    new_run_id = spawn_job(
                                        table_draw_procedure[0], 'tabledraw',
                                        req_data['project_id'], 
                                        app.project_provider, app.results_provider,
                                        registers.RunRequest.from_dict(json.loads(req_data['payload']))
                                    )
                                    if new_run_id:
                                        spawned_actions.append(new_run_id)
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
