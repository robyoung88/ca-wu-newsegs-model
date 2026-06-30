"""
Callbacks for handling DSA runs
"""
import json
import logging

from dash import ALL, Dash, Input, Output, State, no_update, Patch
import dash_ag_grid as dag

from newsegsbrowser import common as browser

logger = logging.getLogger(__name__)

def add_dsa_run_callbacks(app: Dash):
    
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
        
        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(
                browser.dsa_run_request(selected_configuration.get('metamodel_id'))
            )
        )

        return prequeue_patch
    
    return app
