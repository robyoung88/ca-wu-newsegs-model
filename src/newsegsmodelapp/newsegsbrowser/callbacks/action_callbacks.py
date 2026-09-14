"""Callbacks resulting in some processing being undertaken."""

import json
from typing import Any

from dash import ALL, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate
import zmq

from config import settings
from newsegsmodelapp import registers
from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.worker import _set_status_completed, _set_status_failed
from newsegsmodelapp.dash_extension import NewsegsDash

DISPATCHSERVER = 'zmq-dispatcher'#settings['DISPATCHSERVERS'][0]
FRONTENDPORT = settings['FRONTENDPORT']

def send_to_dispatcher(payload) -> dict:
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.connect(f'tcp://{DISPATCHSERVER}:{FRONTENDPORT}')

    socket.send_pyobj(payload)

    return socket.recv_pyobj()

def add_action_callbacks(app: NewsegsDash):
    @app.callback(
        Output({'type': 'postaction-trigger', 'purpose': ALL, 'section': ALL}, 'data'),
        Output('progress-poll-interval', 'disabled'),
        Output('ongoing-actions', 'data'),

        Input({'type': 'action-button', 'purpose': ALL, 'section': ALL,}, 'n_clicks'),
        Input({'type': 'postaction-trigger', 'purpose': ALL, 'section': ALL}, 'data'),
        Input('progress-poll-interval', 'n_intervals'),

        State('ongoing-actions', 'data'),
        State({'type': 'postaction-trigger', 'purpose': ALL, 'section': ALL}, 'id'),
        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def manage_actions(
        action_button_clicks,
        postaction_trigger_data,
        poll_intervals,

        ongoing_actions,
        postaction_trigger_ids,
        active_project_id,
    ):
        trigger_id = ctx.triggered_id
        if trigger_id is None:
            raise PreventUpdate

        postaction_trigger_returns: list[Any] = [no_update] * len(postaction_trigger_ids)

        if not isinstance(trigger_id, str):
            # An action button or postaction trigger
            match trigger_id.get('type'):
                case 'action-button':
                    action_type = trigger_id.get('purpose')
                case 'postaction-trigger':
                    action_type = 
            if action_type in registers.RUN_REQUEST_REGISTER:
                get_rr = registers.RUN_REQUEST_REGISTER[action_type]

                proj = app.project_provider.get_project(active_project_id)
                engine = db.get_engine()
                request = get_rr(proj, engine)
                if not request.background_procedure:
                    runner = registers.RUN_PROCEDURE_REGISTER.get(action_type)
                    if runner is None:
                        raise PreventUpdate
                    
                    job_id = generate_claim_ticket(engine, request)
                    try:
                        is_ok = runner(
                            request,
                            app.project_provider,
                            app.results_provider,
                            job_id,
                            lambda x,y,z: None,
                            lambda: False
                        )

                        _set_status_completed(engine, job_id)
                    except Exception as e:
                        _set_status_failed(engine, job_id, str(e))

                    for idx, id in enumerate(postaction_trigger_ids):
                        if id.get('purpose') == action_type:
                            postaction_trigger_returns[idx] = [json.dumps(request.as_dict())]
                else:
                    run_info = send_to_dispatcher(request)
                    ongoing_actions.append(run_info.get('job_id'))

        



