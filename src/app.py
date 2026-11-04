"""NewSEGS model as a multi-page app.
"""
import time
t1 = time.time()

# Set up logging
import logging
if not logging.getLogger().hasHandlers():
    import app_logging  # noqa: F401
logger = logging.getLogger(__name__)

import json
import os
from pathlib import Path
import uuid

from dash import Dash, Input, Output, State
from dash import dcc, html, no_update
import dash_bootstrap_components as dbc
from flask import jsonify, send_from_directory
import sqlalchemy as sa
import sqlite3

APP_ROOT = Path(__file__).parent.parent.resolve() / 'src'
os.environ['ROOT_PATH_FOR_DYNACONF'] = str(APP_ROOT)
from config import settings, environment
logger.info('Environment: %s', environment.get_environment())

from newsegsmodelapp.components.navigation import DOCS_URL
DEFAULT_DOCS_PATH = APP_ROOT.parent / 'site' # Where `mkdocs build` puts the documentation

# PLUGINS
import newsegsmodelframework.register_plugins  # noqa: F401
import newsegsmodelapp.register_plugins # MUST be imported  # noqa: F401

from newsegsmodelapp import registers
from newsegsmodelapp.backend.db.db import init_db
from newsegsmodelapp.backend.db.db_request_handler import FromDatabaseRequestHandler
from newsegsmodelapp.backend.db.db_result_provider import CachedFromDatabaseResultProvider
from newsegsmodelapp.components.configuration_selector import add_configuration_selector_callbacks
from newsegsmodelapp.components.callbacks.action_callbacks import add_action_callbacks
from newsegsmodelapp.components.callbacks.result_container_callbacks import add_result_container_callbacks
from newsegsmodelapp.components.callbacks.timeseries_callbacks import add_result_timeseries_callbacks

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_component_provider import CachedFromDatabaseNewsegsProjectProvider
from newsegsmodelapp.dash_extension import NewsegsDash

from newsegsmodelapp.components import project_selector as project_selector
from newsegsmodelapp.components import CONFIGURATION_UPDATE_TRIGGER_ID
from newsegsmodelapp.components.callbacks.input_container_callbacks import add_input_container_callbacks
from newsegsmodelapp.components import map

RESULTS_STORE = Path(str(settings['RESULTS_STORE']))
if not RESULTS_STORE.exists():
    RESULTS_STORE.mkdir(parents=True, exist_ok=True)

AVAILABLE_MODELS = ['sprake', 'sprakeloc']

BOOTSTRAP_STYLESHEETS = [dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]

t2 = time.time()
logger.info('App imports completed in %s', t2 - t1)

# -----------------------------------------------
# Layout
# -----------------------------------------------

def serve_layout():
    """
    
    """
    post_action_triggers = (
        [
            dcc.Store(id = {
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': 'global', 'section': 'run',
                'key': x, 'subindex': 0
            })
            for x  in registers.RUN_REQUEST_REGISTER.keys()
        ]
        + [
            dcc.Store(id = {
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': 'global', 'section': 'postprocess',
                'key': x, 'subindex': 0
            })
            for x  in registers.POSTPROCESS_REQUEST_REGISTER.keys()
        ]
        +[
            dcc.Store(id = {
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': 'global', 'section': 'tabledraw',
                'key': x, 'subindex': 0
            })
            for x  in registers.TABLE_DRAW_REQUEST_REGISTER.keys()
        ]
    )

    return html.Div([
        dcc.Location(id = 'url', refresh = 'callback-nav'),
        html.Div(id = 'page-content'),
        dcc.Store(id = 'session-id', data = '', storage_type = 'local'),
        dcc.Store(id = 'app-state', data = '{}', storage_type = 'session'),
        dcc.Store(id = 'active-project-id', data = '', storage_type = 'session'),
        dcc.Store(id = 'layout-update-trigger', data = '', storage_type = 'memory'),
        dcc.Store(id = CONFIGURATION_UPDATE_TRIGGER_ID, data = '', storage_type = 'memory'),
        dcc.Store(id = 'trigger-check-requests', data = 0, storage_type = 'memory'),
        dcc.Store(id = 'trigger-check-stale', data = 0, storage_type = 'memory'),
        # Set when process staleness may have changed outside the input-group update triggers
        dcc.Store(id = 'staleness-update-trigger', data = 0, storage_type = 'memory'),
        dcc.Store(id = 'ongoing-actions', data = [], storage_type = 'memory'),
        dcc.Interval(id = 'progress-poll-interval', interval = settings.get('PROGRESS_POLL_INTERVAL', 1000), n_intervals = 0, disabled = False),
        dcc.Interval(id = 'feedback-graph-interval', interval = 100, n_intervals = 1, max_intervals = 1, disabled = False),
        dcc.Interval(id = 'delayed-result-container-refill-interval', interval = 1000, n_intervals = 1, max_intervals = 1, disabled = False),
    ] 
    + post_action_triggers
)

# -----------------------------------------------
# Navigation
# -----------------------------------------------

def add_display_callbacks(app: NewsegsDash):
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
        logger.info('URL changed to %s, current page is %s', pathname, current_page)

        # Will allow for refreshes - if we don't and the page load doesn't complete,
        # content will be permanently blank until we navigate.
        #if current_page == pathname:
        #    raise PreventUpdate
        app_state_hold = app_state.copy()

        def return_app_state(app_state):
            # Do not trigger listeners on app state if it has not actually changed.
            if app_state == app_state_hold:
                return no_update
            return json.dumps(app_state)

        app_state['current_page'] = pathname
        app_state['session_id'] = session_id # Layout functions should not be reliant on having access to session_id, but it might cut down on some redundant draws.

        if pathname in (
            '/',
            '/model-selection'
        ):
            page = registers.get_page('model-selection')
            if page is None:
                return '404', return_app_state(app_state)
            layout_function = page.layout
            config = registers.get_page_layout_configuration('model-selection', 'default')

            return layout_function(config), return_app_state(app_state)

        splitname = str(pathname).lstrip('/').split("/")

        # If model not supported, route to model selection
        model_type = splitname[0]

        if not model_type in AVAILABLE_MODELS:
            app_state['current_page'] = '/model-selection'
            page = registers.get_page('model-selection')
            if page is None:
                return '404', return_app_state(app_state)
            layout_function = page.layout
            config = registers.get_page_layout_configuration('model-selection', 'default')

            return layout_function(config), return_app_state(app_state)            

        app_state['model_type'] = model_type
        rval = [no_update, return_app_state(app_state)]
        pagename = '/'.join(splitname[1:])

        page = None
        try:
            page = registers.get_page(pagename)
        except KeyError as e:
            logger.warning('Page not found for %s - KeyError raised', pagename)

        if page is None:
            rval[0] = '404'
        else:
            layout_function = page.layout
            config = registers.get_page_layout_configuration(pagename, model_type)
            rval[0] = layout_function(config)

        return tuple(rval)

    # Ensuring that the active project is set
    @app.callback(
        Output('active-project-id', 'data', allow_duplicate = True),

        Input('session-id', 'data'), # Changed session trigger
        Input('app-state', 'data'), # Changed app state (e.g. page, model_type)
        prevent_initial_call = True
    )
    def fetch_active_project_id(
        session_id,
        app_state
    ):
        app_state = json.loads(app_state) if app_state else {}
        model_type = app_state.get('model_type', 'default')
        proj_id = app.project_provider.get_session_project_id(
            session_id,
            model_type,
        )
        logger.info('Project id "%s" has been found for session id "%s"', proj_id, session_id)
        return proj_id

    @app.callback(
        Output('delayed-result-container-refill-interval', 'n_intervals'),
        Input('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def _(apid):
        return 0 # Interval will increment to 1

project_provider = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)
results_provider = CachedFromDatabaseResultProvider(db.get_engine,  RESULTS_STORE)
request_handler = FromDatabaseRequestHandler(db.get_engine)
    
# -----------------------------------------------
# Create App
# -----------------------------------------------

def create_app(external_stylesheets = None) -> Dash:
    """
    Create the NewSEGS Dash App
    """
    logger.info('Creating App')

    if external_stylesheets is None:
        external_stylesheets = BOOTSTRAP_STYLESHEETS
    else:
        # Always add on bootstrap
        external_stylesheets += BOOTSTRAP_STYLESHEETS

    # project_provider = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)
    # results_provider = CachedFromDatabaseResultProvider(db.get_engine,  RESULTS_STORE)
    # request_handler = FromDatabaseRequestHandler(db.get_engine)

    app = NewsegsDash(
        __name__,
        title = 'NewSEGS Energy Model',
        update_title = None, # pyright: ignore[reportArgumentType]
        external_stylesheets = external_stylesheets,
        project_provider = project_provider,
        results_provider = results_provider,
        request_handler = request_handler,
        #background_callback_manager = background_callback_manager,
    )

    app.layout = serve_layout
    default_app_state = {'model_selection': 'default'} 
    app.validation_layout = html.Div(
        [serve_layout()] + [page.layout(page.default_configuration) for page in registers.PAGE_REGISTER.values()] # pyright: ignore[reportArgumentType]
    )

    server = app.server
    # ---------------------------------
    # Health check
    # ---------------------------------
    @server.route('/health')
    def health_check():
        DB_PATH = Path(settings['DB_PATH'])
        """Endpoint for load balancers and Docker to verify app readiness"""
        # Check if DB file exists (might be restoring)
        if not DB_PATH.exists():
            return jsonify({'status': 'starting', 'message': 'Database is restoring...'}), 503

        # Check if the database is responsive and not locked/corrupt
        try:
            with db.get_engine().connect() as conn:
                # Lightweight query to verify read access
                conn.execute(sa.text('SELECT 1 FROM sqlite_master LIMIT 1'))

            return jsonify({'status': 'healthy', 'message': 'Service is operational'}), 200
        except sqlite3.Error as e:
            return jsonify({'status': 'unhealthy', 'message': f'Database error: {e}'}), 500

    # ---------------------------------
    # Documentation
    # ---------------------------------
    # The HTML built by `mkdocs build` is served from DOCS_PATH, so that the app can link to it.
    # The documentation is not part of the Dash app: pages are plain HTML files with relative
    # links (use_directory_urls is false in mkdocs.yml), served below DOCS_URL.
    @server.route(DOCS_URL, defaults = {'filename': 'index.html'})
    @server.route(DOCS_URL + '<path:filename>')
    def documentation(filename):
        docs_path = Path(str(settings.get('DOCS_PATH', DEFAULT_DOCS_PATH)))
        if not (docs_path / 'index.html').exists():
            return (
                'The documentation has not been built. Run "mkdocs build" in the root of the '
                f'repository, or set DOCS_PATH (currently {docs_path}).',
                404
            )
        return send_from_directory(docs_path, filename)

    # Bind callbacks
    add_display_callbacks(app)
    #add_background_callbacks(app)
    add_input_container_callbacks(app)
    project_selector.add_project_selector_callbacks(app)
    map.add_site_selector_callbacks(app)
    add_configuration_selector_callbacks(app)
    add_action_callbacks(app)
    add_result_container_callbacks(app)
    add_result_timeseries_callbacks(app)

    for page in registers.PAGE_REGISTER.values():
        page.attach_callbacks(app)

    t3 = time.time()
    logger.info('App Time To Start (including imports): %s', t3 - t1)

    return app

# -----------------------------------------------
# if __name__ == '__main__'
# -----------------------------------------------

init_db()
app = create_app()
# Expose the underlying Flask server for WSGI servers like Gunicorn
server = app.server

if __name__ == '__main__':
    # The Flask development server. In production the app is served by gunicorn
    # (`gunicorn --config gunicorn.conf.py app:server`) and this block is not run.
    if environment.is_production():
        logger.warning(
            'Running the development server with NEWSEGS_ENV=production; '
            'use gunicorn instead. Debug tools are disabled.'
        )
    # Debug tools (error pop-ups, the callback graph, hot reload of assets) only in development
    debug = environment.is_development()
    app.run(
        host = '0.0.0.0', port = 8050, debug = debug, use_reloader = False, threaded = True,
        # Circular-callback validation expands every pattern-matching id over all
        # wildcard values in the browser, which blocks the initial page load for
        # about a minute. Set DASH_VALIDATE_CALLBACKS=true to check for cycles.
        dev_tools_validate_callbacks = debug and os.environ.get('DASH_VALIDATE_CALLBACKS', 'false').lower() == 'true',
    )
