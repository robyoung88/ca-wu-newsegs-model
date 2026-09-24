"""Layout and callbacks for after page load on pages requiring live project data."""

import datetime

import dash
from dash import ALL, ClientsideFunction, Input, Output, State, clientside_callback, dcc, html

from newsegsmodelapp.dash_extension import NewsegsDash

# -----------------------------------------------
# Layout component
# -----------------------------------------------
def create_post_page_load_components(
    model_type, 
    page_type,
) -> list[dash.development.base_component.Component]:
    """App control components which should be the last things loaded onto a page.
    
    Used to trigger callbacks on page load completion.
    """
    return [

        # Records the project that the page is currently configured for.
        # Used to verify whether we need a complete redraw on change of the active
        # project.
        dcc.Store(id = 'loaded-project-id', data = None, storage_type = 'memory'),

        # Used as a trigger for events altering allow_duplicate components,
        # which cannot be used without prevent_initial_call
        dcc.Store(id = {
            'type': 'firstload-config-watcher',
            'model_type': model_type, 
            'page_type': page_type
        }),

        # Used as a trigger for events on load.
        html.Div(id = {
            'type': 'onload-div',
            'model_type': model_type, 
            'page_type': page_type
        })
    ]

def add_post_page_load_callbacks(app: NewsegsDash):
    """
    Functions which are triggered immediately after page load.
    """

    # Logic for controlling the results drawer in a vertical view
    clientside_callback(
        ClientsideFunction(
            namespace = 'clientside',
            function_name = 'attach_drawer'
        ),
        Output({'type': 'post-drawer-attach', 'page': ALL}, 'children'),
        
        Input({'type' : 'onload-div', 'model_type': ALL, 'page_type': ALL}, 'children')
    )

    @app.callback(
        Output({'type' : 'firstload-config-watcher', 'model_type': ALL, 'page_type': ALL}, 'data'),
        
        Input({'type' : 'onload-div', 'model_type': ALL, 'page_type': ALL}, 'children'),
        State({'type' : 'onload-div', 'model_type': ALL, 'page_type': ALL}, 'id'),
    )
    def sync_config_init(_, config_watcher_ids):
        """
        Trigger any initial actions after a page load
        """
        print('Model configuration onload div constructed.')
        return [datetime.datetime.now().timestamp()] * len(config_watcher_ids)
        