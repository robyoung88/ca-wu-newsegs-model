"""NewSEGS model as a multi-page app.
"""
import json
import os
from pathlib import Path
import uuid

from dash import Dash, Input, Output, State
from dash import dcc, html, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.components.configuration_selector import add_configuration_selector_callbacks

APP_ROOT = Path(__file__).parent.parent.resolve() / 'src'
os.environ['ROOT_PATH_FOR_DYNACONF'] = str(APP_ROOT)
from config import settings

# PLUGINS
import newsegsmodelframework.register_plugins
import newsegsmodelapp.register_plugins # MUST be imported
from newsegsmodelapp.registers import PAGE_LAYOUT_REGISTER

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.newsegsbrowser.callbacks import model_selection_callbacks

from newsegsmodelapp.components import project_selector
from newsegsmodelapp.components import CONFIGURATION_UPDATE_TRIGGER_ID
from newsegsmodelapp.components.post_page_load import add_post_page_load_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks.input_container_callbacks import add_input_container_callbacks
from newsegsmodelapp.components import map

RESULTS_STORE = Path(str(settings['RESULTS_STORE']))
if not RESULTS_STORE.exists():
    RESULTS_STORE.mkdir(parents=True, exist_ok=True)


# LAYOUTS
from newsegsmodelapp.newsegsbrowser.layouts import model_selection_layout

AVAILABLE_MODELS = ['sprake', 'sprake-localised']

BOOTSTRAP_STYLESHEETS = [dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]


# -----------------------------------------------
# Layout
# -----------------------------------------------

def serve_layout():
    """
    
    """
    return html.Div([
        dcc.Location(id = 'url', refresh = 'callback-nav'),
        html.Div(id = 'page-content'),
        dcc.Store(id = 'session-id', data = '', storage_type = 'local'),
        dcc.Store(id = 'app-state', data = '{}', storage_type = 'session'),
        dcc.Store(id = 'active-project-id', data = '', storage_type = 'session'),
        dcc.Store(id = 'layout-update-trigger', data = '', storage_type = 'memory'),
        dcc.Store(id = CONFIGURATION_UPDATE_TRIGGER_ID, data = '', storage_type = 'memory'),
    ])

# -----------------------------------------------
# Navigation
# -----------------------------------------------

def add_display_callbacks(app: NewsegsDash) -> NewsegsDash:
    """
    Attach callbacks for multi-page handling to app
    """
    @app.callback(
        Output('session-id', 'data'),
        Input('session-id', 'data'),
    )
    def initialise_session_id(session_id):
        """If session_id does not exist, generates a new one."""
        if not session_id:
            session_id = 'sess-' + str(uuid.uuid4())
            return session_id
        return no_update

    @app.callback(
        Output('page-content', 'children'),
        Output('app-state', 'data'),
        Input('url', 'pathname'),
        State('session-id', 'data'),
        State('app-state', 'data'),
    )
    def display_page(pathname, session_id, app_state):
        app_state = json.loads(app_state) if app_state else {}
        current_page = app_state.get('current_page', '')
        print(pathname, ' ', current_page)

        # Will allow for refreshes - if we don't and the page load doesn't complete,
        # content will be permanently blank until we navigate.
        #if current_page == pathname:
        #    raise PreventUpdate

        app_state['current_page'] = pathname
        app_state['session_id'] = session_id # Layout functions should not be reliant on having access to session_id, but it might cut down on some redundant draws.

        rval = [no_update, json.dumps(app_state)]
        if pathname in (
            '/',
            '/model_selection'
        ):
            rval[0] = model_selection_layout.model_selection_layout
            return tuple(rval)

        splitname = str(pathname).lstrip('/').split("/")
        selected_model = splitname[0]

        if not selected_model in AVAILABLE_MODELS:
            return model_selection_layout.model_selection_layout

        app_state['selected_model'] = selected_model
        rval = [no_update, json.dumps(app_state)]
        pagename = '/'.join(splitname[1:])

        layout_function = PAGE_LAYOUT_REGISTER.get(pagename)
        if layout_function is None:
            rval[0] = '404'
        else:
            rval[0] = layout_function(app_state)

        return tuple(rval)

    # Ensuring that the active project is set
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

        Input('session-id', 'data'), # Changed session trigger
        Input('app-state', 'data'), # Changed app state (e.g. page, selected_model)
        prevent_initial_call = True
    )
    def fetch_active_project_id(
        session_id,
        app_state
    ):
        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('selected_model', 'default')
        proj_id = app.project_provider.get_session_project_id(
            session_id,
            model_type,
        )
        print (f'Project {proj_id} has been found for session {session_id}')
        return proj_id
        

    return app

# -----------------------------------------------
# Create App
# -----------------------------------------------

def create_app(external_stylesheets = None) -> Dash:
    """
    Create the NewSEGS Dash App
    """
    print('Creating app')

    if external_stylesheets is None:
        external_stylesheets = BOOTSTRAP_STYLESHEETS
    else:
        # Always add on bootstrap
        external_stylesheets += BOOTSTRAP_STYLESHEETS

    project_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
    results_provider = FromDatabaseResultProvider(db.get_engine,  RESULTS_STORE)

    app = NewsegsDash(
        __name__,
        title = 'NewSEGS Energy Model',
        update_title = None, # pyright: ignore[reportArgumentType]
        external_stylesheets = external_stylesheets,
        project_provider = project_provider,
        results_provider = results_provider,
        #routing_callback_inputs = {
        #    'session-id': Input('session-id', 'data'),
        #    'app-state': Input('app-state', 'data'),
        #}
    )

    app.layout = serve_layout
    default_app_state = {'model_selection': 'default'} 
    app.validation_layout = html.Div([
        serve_layout(),
        *[f(default_app_state) for f in PAGE_LAYOUT_REGISTER.values()]
    ])

    # Bind callbacks
    app = add_display_callbacks(app)
    app = add_post_page_load_callbacks(app)
    app = add_input_container_callbacks(app)
    app = model_selection_callbacks.assign_callbacks(app)
    app = project_selector.add_project_selector_callbacks(app)
    app = map.add_site_selector_callbacks(app)
    add_configuration_selector_callbacks(app)

    return app

# -----------------------------------------------
# if __name__ == '__main__'
# -----------------------------------------------

if __name__ == '__main__':
    app = create_app()
    app.run(debug = True)
