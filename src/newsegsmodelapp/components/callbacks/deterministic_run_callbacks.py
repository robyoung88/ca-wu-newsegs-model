from dash import Input, Output, State
from dash.exceptions import PreventUpdate

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash


def add_deterministic_run_callbacks(app: NewsegsDash):
    @app.callback(
        Output('trigger-check-requests', 'data', allow_duplicate = True),
        Input('btn-action-deterministic-run-metamodel', 'n_clicks'),
        State('active-project-id', 'data'),
        prevent_initial_call = True,
    )
    def request_deterministic_run_metamodel(
        n_clicks,
        active_project_id
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        request_id = app.request_handler.add_request(
            'deterministic_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
        )

        return request_id

    @app.callback(
        Output('trigger-check-requests', 'data', allow_duplicate = True),
        Input('btn-action-deterministic-run-project', 'n_clicks'),
        State('active-project-id', 'data'),
        prevent_initial_call = True,
    )
    def request_deterministic_run_project(
        n_clicks,
        active_project_id
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        request_id = app.request_handler.add_request(
            'deterministic_run_project',
            active_project_id,
            app.project_provider,
            'run',
        )

        return request_id
    