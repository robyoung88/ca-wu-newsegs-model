"""
Callbacks for handling optimisation requests
"""

import logging

from dash import ALL, Dash, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

logger = logging.getLogger(__name__)

def add_optim_run_callbacks(app: Dash):

    # Pre-run modal control
    @app.callback(
        output = {
            'modal': {
                'is_open': Output('modal-optim-confirm','is_open')
            }
        },
        inputs = {
            'optim_run_button': {
                'n_clicks':  Input('btn-action-optim-run-metamodel', 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input('btn-optim-confirm-abort', 'n_clicks')
            },
            'optim_prerun_button': {
                'n_clicks': Input('btn-optim-prerun', 'n_clicks'),
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
        
        trig_id = ctx.triggered_id
        if trig_id is None:
            raise PreventUpdate
        
        if trig_id == 'btn-optim-prerun':
            return dict(modal = dict(is_open = True))
        else:
            return dict(modal = dict(is_open = False))
