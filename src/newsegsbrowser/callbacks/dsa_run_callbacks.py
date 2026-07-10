"""
Callbacks for handling DSA runs
"""
import json
import logging

from dash import ALL, Dash, Input, Output, State, no_update, Patch, ctx
import dash_ag_grid as dag

from newsegsbrowser import common as browser

logger = logging.getLogger(__name__)

def add_dsa_run_callbacks(app: Dash):

    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'dsa-run-confirm'},
                    'is_open'
                )
            }
        },
        inputs = {
            'dsa_run_button': {
                'n_clicks': Input({'type': 'dsa-run-button', 'page': ALL}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-button', 'page': ALL, 'key': 'dsa-run-confirm'},
                    'n_clicks'
                )
                
            },
            'dsa_prerun_button': {
                'n_clicks': Input({'type': 'dsa-prerun-button', 'page': ALL}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'dsa-run-confirm'},
                    'id'
                )
            }
        }
    )
    def confirm_dsa_run(
        dsa_run_button,
        modal_close_button,
        dsa_prerun_button,
        modal,
    ):
        n_modals = len(modal['ids'])
        if n_modals == 0:
            return dict(modal = dict(is_opens = []))
        trig_id = ctx.triggered_id
        if trig_id is None:
            return dict(modal = dict(is_opens = [no_update] * n_modals))
        
        if trig_id.get('type') == 'dsa-prerun-button':
            return dict(modal = dict(is_opens = [True] * n_modals))
        else:
            return dict(modal = dict(is_opens = [False] * n_modals))
    
    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),
        
        Input({'type': 'dsa-run-button', 'page': ALL}, 'n_clicks'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def start_dsa_run(n_clicks, selected_configuration):
        if n_clicks is None:
            return no_update
        
        if selected_configuration is None:
            return no_update
        selected_configuration = json.loads(selected_configuration)
        
        request_ = browser.dsa_run_request(
            metamodel_id = selected_configuration.get('metamodel_id'),
            debounce = False
        )
        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(
                request_.as_dict()
            )
        )
        logger.info('Adding dsa request to prequeue-action-user: %s', request_)

        return prequeue_patch
    
    return app
