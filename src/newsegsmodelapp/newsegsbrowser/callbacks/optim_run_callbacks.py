"""
Callbacks for handling optimisation requests
"""

import logging

from dash import ALL, Dash, Input, Output, State, ctx, no_update

logger = logging.getLogger(__name__)

def add_optim_run_callbacks(app: Dash):

    # Pre-run modal control
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'optim-run-confirm'},
                    'is_open'
                )
            }
        },
        inputs = {
            'optim_run_button': {
                'n_clicks':  Input({
                    'type': 'action-button', 'purpose': 'request-process',
                    'supersection': 'optim', 'section': 'run',
                    'key': 'optim_run_metamodel', 'subindex': 0,
                }, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-btn', 'page': ALL, 'key': 'optim-run-confirm'},
                    'n_clicks'
                )
            },
            'optim_prerun_button': {
                'n_clicks': Input({'type': 'optim-prerun-btn', 'page': ALL}, 'n_clicks'),
            }
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'optim-run-confirm'},
                    'id'
                )
            }
        },
        prevent_initial_call = True
    )
    def confirm_optim_run(
        optim_run_button,
        modal_close_button,
        optim_prerun_button,
        modal,
    ):
        print('modal')
        n_modals = len(modal['ids'])
        if n_modals == 0:
            return dict(modal = dict(is_opens = []))
        trig_id = ctx.triggered_id
        if trig_id is None:
            return dict(modal = dict(is_opens = [no_update] * n_modals))
        
        if trig_id.get('type') == 'optim-prerun-btn':
            return dict(modal = dict(is_opens = [True] * n_modals))
        else:
            return dict(modal = dict(is_opens = [False] * n_modals))
