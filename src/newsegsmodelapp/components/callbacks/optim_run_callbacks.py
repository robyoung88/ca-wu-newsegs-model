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
                    'supersection': 'optim', 'section': 'tabledraw',
                    'key': 'table_optim_metamodel', 'subindex': ALL # If we don't include the wildcard, we get complaints navigating away from the page.
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
        stat = kwargs.get('statistic')
        if stat is not None and not isinstance(stat, str) and len(stat):
            kwargs['statistic'] = stat[0]

        request_id = app.request_handler.add_request(
            'optim_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
            kwargs
        )

        return dict(trigger = request_id)

    # Marginal statistic plot draw
    @app.callback(
        output = dict(
            trigger = Output('trigger-check-requests', 'data', allow_duplicate = True),
        ),
        inputs = dict(
            n_clicks = Input(
                {
                    'type': 'btn-action-optim-create-marginalplot', 'varid': ALL
                },
                'n_clicks'
            ),
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
            statistic = State(
                {
                    'type': 'result-table-option', 'purpose': 'statistic',
                    'supersection': 'optim', 'section': 'tabledraw',
                    'key': 'table_optim_metamodel', 'subindex': ALL # If we don't include the wildcard, we get complaints navigating away from the page.
                },
                'value'
            ),
        ),
        prevent_initial_call = True,
    )
    def request_marginal_plot(
        n_clicks,
        active_project_id,
        statistic,
    ):
        triggered_id = ctx.triggered_id
        if triggered_id is None or statistic is None:
            raise PreventUpdate

        if statistic is not None and not isinstance(statistic, str) and len(statistic):
            statistic = statistic[0]
        
        if not isinstance(triggered_id, str) and triggered_id.get('type') == 'btn-action-optim-create-marginalplot':
            clicks = callback_utils.get_triggered_value()
            if not clicks:
                raise PreventUpdate
        if isinstance(triggered_id, str):
            raise TypeError('Can only trigger with an object specifing the variable to plot')

        request_id = app.request_handler.add_request(
            'table_optim_metamodel', # TODO: Improve this key
            active_project_id,
            app.project_provider,
            'tabledraw',
            dict(
                metamodel_id = app.project_provider.get_focussed_metamodel_id(active_project_id),
                varid = triggered_id.get('varid'),
                statistic = statistic,
            )
        )

        return dict(trigger = request_id)

    @app.callback(
        Output('active-project-id', 'data'),
        Input(
            {
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': 'global', 'section': 'run',
                'key': 'optim_run_metamodel', 'subindex': 0
            },
            'data'
        ),
        State('active-project-id', 'data'),
        prevent_initial_call = True,
    )
    def update_project_after_optimisation(trigger, active_project_id):
        trig_id = ctx.triggered_id
        if trig_id is None:
            raise PreventUpdate
        return active_project_id
    