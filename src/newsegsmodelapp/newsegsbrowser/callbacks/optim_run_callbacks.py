"""
Callbacks for handling optimisation requests
"""

import logging

from dash import ALL, Dash, Input, Output, State, ctx, no_update
from dash.exceptions import PreventUpdate

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash

logger = logging.getLogger(__name__)

def add_optim_run_callbacks(app: NewsegsDash):

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

    @app.callback(
        output = dict(
            trigger = Output('trigger-check-requests', 'data', allow_duplicate = True),
        ),
        inputs = dict(
            n_clicks = Input('btn-action-optim-run-metamodel', 'n_clicks'),
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
            statistic = State(
                {
                    'type': 'result-table-option', 'purpose': 'statistic',
                    'supersection': 'dsa', 'section': 'tabledraw',
                    'key': 'table_dsa_metamodel', 'subindex': 0
                },
                'value'
            ),
            optim_method = State(
                {
                    'type': 'result-table-option', 'purpose': 'optim-method',
                    'supersection': 'optim', 'section': 'run',
                    'key': 'optim_run_metamodel', 'subindex': 0
                },
                'value'
            )
        ),
        prevent_initial_call = True
    )
    def request_optim_run_metamodel(
        n_clicks,
        active_project_id,
        **kwargs
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        request_id = app.request_handler.add_request(
            'optim_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
            kwargs
        )

        return dict(trigger = request_id)
    