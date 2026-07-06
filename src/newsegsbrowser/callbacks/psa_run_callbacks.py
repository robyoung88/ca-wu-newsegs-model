"""
Callbacks for handling PSA runs
"""
import json
import logging

from dash import ALL, Dash, Input, Output, State, no_update, Patch


from newsegsbrowser import common as browser

logger = logging.getLogger(__name__)

def add_psa_run_callbacks(app: Dash):

    @app.callback(
        Output('prequeue-action-user', 'data', allow_duplicate = True),

        Input({'type': 'psa-run-button', 'page': ALL}, 'n_clicks'),
        State({'type': ALL, 'target': 'psa-settings', 'key': ALL}, 'id'),
        State({'type': ALL, 'target': 'psa-settings', 'key': ALL}, 'value'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def start_psa_run(
        n_clicks,
        input_ids,
        input_values,
        selected_configuration
    ):
        if n_clicks is None:
            return no_update
        
        if selected_configuration is None:
            return no_update
        
        selected_configuration = json.loads(selected_configuration)

        kwargs = {}
        for idx, id in enumerate(input_ids):
            if id.get('key') in {'samples', 'seed'}:
                if input_values[idx] is not None:
                    kwargs[id.get('key')] = int(input_values[idx])
                else:
                    kwargs[id.get('key')] = input_values[idx]
            elif id.get('key') in {'return_draws'}:
                kwargs[id.get('key')] = bool(input_values[idx])

        print(kwargs)

        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(
                browser.psa_run_request(selected_configuration.get('metamodel_id'), **kwargs)
            )
        )

        return prequeue_patch

    return app
