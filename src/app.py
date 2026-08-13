"""
NewSEGS model as a multi-page app.
"""
import copy
import datetime
import json
import logging
import os
import time
from typing import Callable, Literal, cast, MutableMapping

from dash import ALL, Dash, dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
# At the moment, use a diskcache cache for transferring models 
# regardless of background callback manager
import diskcache

# For local testing
#import sys
#curdir = os.path.dirname(__file__)
#src_path = os.path.join(
#    curdir,
#    'src'
#)
#sys.path.append(src_path)

from config import settings

from newsegsmodelframework.newsegsmodel import newsegsmodel
from newsegsmodelframework.newsegsfinance import newsegsfinance
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel

from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager

from newsegsmodelapp.newsegsbrowser.layouts import template_psa_configuration_layout
from newsegsmodelapp.newsegsbrowser.layouts import template_landing_layout
from newsegsmodelapp.newsegsbrowser.layouts import template_model_configuration_layout
from newsegsmodelapp.newsegsbrowser.layouts import template_dsa_configuration_layout
from newsegsmodelapp.newsegsbrowser.layouts import layout_registry, model_selection_layout

from newsegsmodelapp.newsegsbrowser.callbacks import psa_run_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import model_configuration_callbacks, model_selection_callbacks, optim_run_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import model_run_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import postprocess_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import results_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import callbacks_map
from newsegsmodelapp.newsegsbrowser.callbacks import timeseries_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import configuration_selector_callbacks
from newsegsmodelapp.newsegsbrowser.callbacks import dsa_run_callbacks
from newsegsmodelapp.newsegsbrowser.map import add_site_selector_callbacks

from newsegsmodelapp.newsegsbrowser.postprocess import postprocess_utils

from newsegsmodelapp.newsegsbrowser.background_callback_errors import add_background_callback_error_dispatch, background_callback_error_handler_factory

from newsegsmodelapp.newsegsbrowser import energy_balance_estimation

logger = logging.getLogger(__name__)

BOOTSTRAP_STYLESHEETS = [dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]

models: MutableMapping[str, newsegsmodel.NewsegsModel] = {}
finances: MutableMapping[str, newsegsfinance.NewsegsFinance] = {}
results = {}
metamodels: MutableMapping[str, NewsegsMetaModel] = {}
cache = diskcache.Cache(settings.get('DiskcacheCache', './cache'))

# Manager for background callbacks
if 'REDIS_URL' in os.environ:
    # Use Redis & Celery if REDIS_URL is set
    from dash import CeleryManager
    from celery import Celery
    celery_app = Celery(
        __name__,
        broker = os.environ['REDIS_URL'],
        backend = os.environ['REDIS_URL']
    )
    noncaching_background_callback_manager = CeleryManager(celery_app)
else:
    # Diskcache otherwise, for non-production and local dev.
    from dash import DiskcacheManager

    #cache = diskcache.Cache(settings.get('DiskcacheCache', './cache'))
    #background_callback_manager = DiskcacheManager(cache, cache_by = [lambda: launch_uid])
    noncaching_background_callback_manager = DiskcacheManager(cache)

def metamodel_to_cache(metamodel_id: str):
    mm = metamodels.get(metamodel_id)
    logger.info('writing metamodel %s to cache', metamodel_id)
    if mm:
        cache[metamodel_id] = mm
    logger.info('writing metamodel %s to cache was successful', metamodel_id)

def metamodel_from_cache(
        metamodel_id: str, 
        reattach_location: Literal['local', 'cache'] = 'local'
    ) -> NewsegsMetaModel:
        logger.info('retrieving metamodel %s from cache', metamodel_id)
        mm = cache.get(metamodel_id)
        if not isinstance(mm, NewsegsMetaModel):
            raise TypeError(f'{metamodel_id} retrieved from cache is of type {type(mm)}')
        match reattach_location:
            case 'local':
                mm.reattach_model(models)
                mm.reattach_finance(finances)
            case 'cache':
                mm.reattach_model(cache) # pyright: ignore[reportArgumentType]
                mm.reattach_finance(cache) # pyright: ignore[reportArgumentType]
                mm.finance.set_model(mm.model, False)
        logger.info('retrieving metamodel %s was successful', metamodel_id)
        return mm

def serve_layout():
    """
    
    """

    return html.Div([
        dcc.Location(id = 'url', refresh = 'callback-nav'),
        html.Div(id = 'page-content'),
        dcc.Store(id = 'selected-model', data = 'sprake'),
        dcc.Store(id = 'store-selected-configuration'),
        dcc.Store(id = 'store-configurations', data = []),
    ])

def add_display_callbacks(app: Dash, acm: NewsegsBrowserCacheManager) -> Dash:
    """
    Attach callbacks for multi-page handling to app
    """
    #app = app
    #acm = acm

    @app.callback(
        Output('page-content', 'children'),
        Input('url', 'pathname'),
        State('selected-model', 'data'),
        State('store-selected-configuration', 'data'),
        State('store-configurations', 'data')
    )
    def display_page(pathname, selected_model, selected_conf, configurations):
        
        current_page = acm.sts.get('current_page')

        if current_page is not None and current_page == pathname:
            return no_update
        
        acm.sts['current_page'] = pathname        

        if pathname == '/' or pathname == '/model_selection':
            return model_selection_layout.model_selection_layout
        
        splitname = str(pathname).lstrip('/').split("/")
        selected_model = splitname[0]
        
        if not selected_model in ['sprake','localised']:
            return model_selection_layout.model_selection_layout
        
        pagename = '/'.join(splitname[1:])
        
        # As we are changing page, we will naturally lose any of our background callbacks
        # Therefore, make sure that all models in all configs are unlocked.
        for config_j in configurations:
            mm = acm.metamodels.get(json.loads(config_j).get('metamodel_id'))
            if mm is not None:
                mm.model.checked_out = False
                mm.finance.checked_out = False
        # Also set the number of background processes to 0
        acm.sts['n_bgp'] = 0

        if pagename == 'landing':
            return template_landing_layout.create_landing_layout(
                **layout_registry.get_landing_layout_config(
                    selected_model
                )
            )
        elif pagename == 'site-config':
            return template_model_configuration_layout.create_model_configuration_layout(
                **layout_registry.get_model_configuration_layout_config(
                    selected_model
                )
            )
        elif pagename == 'dsa':
            return template_dsa_configuration_layout.create_dsa_layout(
                **layout_registry.get_dsa_layout_config(
                    selected_model
                )
            )
        elif pagename == 'psa':
            return template_psa_configuration_layout.create_psa_layout(
                **layout_registry.get_psa_layout_config(
                    selected_model
                )
            )

        else:
            return '404'
    
    return app


def add_caching_callbacks(app, acm: NewsegsBrowserCacheManager):
    @app.callback(
        Output({'type': 'background-callback-return', 'target': 'model-run'}, 'data', allow_duplicate = True),

        Input({'type': 'background-callback-call', 'target': 'model-run'}, 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager,
        on_error = background_callback_error_handler_factory('model-run', app, acm)
    )
    def run_model(model_run_request):
        model_run = json.loads(model_run_request)
        model_id = model_run['model_id']
        mdl = cast(newsegsmodel.NewsegsModel, cache.get(model_id))
        run_hash = None
        if mdl is not None:
            run_hash = mdl.run() 
        # Simply because of how to_cache is written, need to place model in
        # local dict
        models[model_id] = mdl
        cache[model_id] = mdl
        return model_run_request
    
    @app.callback(
        Output({'type': 'background-callback-return', 'target': 'finance-run'}, 'data', allow_duplicate = True),

        Input({'type': 'background-callback-call', 'target': 'finance-run'}, 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager,
        on_error = background_callback_error_handler_factory('finance-run', app, acm)
    )
    def run_finance(finance_run_request):
        finance_run = json.loads(finance_run_request)
        model_id = finance_run['model_id']
        finance_id = finance_run['finance_id']
        mdl = cast(newsegsmodel.NewsegsModel, cache.get(model_id))

        fnc = cast(newsegsfinance.NewsegsFinance, cache.get(finance_id))
        if fnc is None:
            return finance_run_request
        # Suspect that if we don't do this, things will rapidly break
        # unless the pickle serialises the model for the finance
        # in which case, we may need to re-write the reduce function
        fnc.set_model(mdl, False)

        # CREATE THE FINANCE RESULTS
        fnc.run()

        # SYNCRONISE THE FINANCE
        finances[finance_id] = fnc
        cache[finance_id] = fnc
        
        return finance_run_request
    
    @app.callback(
        Output({'type': 'background-callback-return', 'target': 'metamodel-process'}, 'data', allow_duplicate = True),

        Input({'type': 'background-callback-call', 'target': 'metamodel-process'}, 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager,
        on_error = background_callback_error_handler_factory('metamodel-process', app, acm),
        running = [
            (
                Output({'type': 'metamodel-process-cancel', 'target': ALL}, 'class_name'), 
                'background-callback-cancel-button',
                'background-callback-cancel-button background-callback-cancel-button-hidden'
            ),
            (
                Output({'type': 'resize-handle', 'page': ALL}, 'style'),
                {'display': 'none'},
                {}
            ),
            (
                Output({'type': 'progress-bar', 'page': ALL}, 'style'),
                {},
                {'display': 'none'},
            ),
        ],
        cancel=Input('background_cancel_trigger', "data"),
        progress = [
            Output('background_progress_tracker', 'data')
        ],
        progress_default = '{"value":"0", "max":"1", "message":"running"}',
    )
    def run_metamodel_process(
        set_progress,
        metamodel_process
    ):
        process_request = json.loads(metamodel_process)
        mm = metamodel_from_cache(process_request.get('metamodel_id'), 'cache')
        
        # Do the process
        match process_request['type']:
            case 'dsa_run_request':
                dsa_run_callbacks.dsa_metamodel_process(
                    set_progress, process_request, mm, cache # pyright: ignore[reportArgumentType]
                )
            case 'psa_run_request':
                psa_run_callbacks.psa_metamodel_process(
                    set_progress, process_request, mm, cache # pyright: ignore[reportArgumentType]
                    ) 
            case 'optim_run_request':
                optim_run_callbacks.optim_metamodel_process(
                    set_progress, process_request, mm, cache # pyright: ignore[reportArgumentType]
                )

        metamodels[mm.id] = mm
        models[mm.model.id] = mm.model
        finances[mm.finance.id] = mm.finance

        # Resynchronise
        metamodel_to_cache(mm.id)
        cache[mm.model.id] = mm.model
        cache[mm.finance.id] = mm.finance

        return metamodel_process

    @app.callback(
        Output('background_cancel_trigger', 'data'),
        Output({
            'type': 'lock', 
            'target': 'metamodel-process', 
            'stage': 'dispatch', 
            'key': 'process-in-use'
        }, 'data', allow_duplicate = True),

        Input({'type': 'metamodel-process-cancel', 'target': ALL}, 'n_clicks'),
        State({'type': 'background-callback-call', 'target': 'metamodel-process'}, 'data'),
        prevent_initial_call = True
    )
    def set_cancel_trigger(
        n_clicks,
        metamodel_process_call
    ):
        if n_clicks is None:
            return no_update, no_update
        logger.info('User has attempted to cancel metamodel process %s', datetime.datetime.now())
        call_ = json.loads(metamodel_process_call)
        mm = acm.metamodels[call_['metamodel_id']]
        mm.checked_out = False
        mm.model.checked_out = False
        mm.finance.checked_out = False

        return time.time_ns(), True

    @app.callback(
        Output({'type':'progress-bar', 'page': ALL}, "value"), 
        Output({'type':'progress-bar', 'page': ALL}, "max"),
        Output({'type': 'progress-tooltip', 'page': ALL}, 'children'), 

        Input('background_progress_tracker', 'data'),
        State({'type': 'progress-bar', 'page': ALL}, "id"),
        State({'type': 'progress-tooltip', 'page': ALL}, "id"),
        prevent_initial_call = True
    )
    def set_progress_bars(
        progress, 
        progress_ids,
        tooltip_ids,
        ):
        if len(progress_ids) == 0 and len(tooltip_ids) == 0:
            return [], [], []
        if progress is None:
            return [no_update] * len(progress_ids), [no_update] * len(progress_ids), [no_update] * len(tooltip_ids)
        progress = json.loads(progress)
        return (
            [str(progress['value'])] * len(progress_ids), 
            [str(progress['max'])] * len(progress_ids),
            [progress.get('message', no_update)] * len(tooltip_ids),
        )
    
    return app

def create_app(external_stylesheets = None) -> Dash:
    """
    Create the NewSEGS Dash App
    """
    logging.info('Creating app')

    if external_stylesheets is None:
        external_stylesheets = BOOTSTRAP_STYLESHEETS
    else:
        # Always add on bootstrap
        external_stylesheets += BOOTSTRAP_STYLESHEETS
    
    #assets_path = 'src/assets'
    app = Dash(
        __name__,
        #suppress_callback_exceptions = True,
        title = 'NewSEGS Energy Model',
        update_title = None, # pyright: ignore[reportArgumentType]
        external_stylesheets = external_stylesheets,
        #assets_url_path = assets_path,
        routing_callback_inputs = {
            'selected-model': Input('selected-model', 'data'),
            'store-selected-configuration': Input('store-selected-configuration', 'data'),
            'store-configurations': Input('store-configurations', 'data'),
        }
    )
    app.config.suppress_callback_exceptions = True

    app.layout = serve_layout
    app.validation_layout = html.Div([
        serve_layout(),
        template_landing_layout.create_landing_layout(
            **layout_registry.get_landing_layout_config(
                'sprake'
            )
        ),
        template_model_configuration_layout.create_model_configuration_layout(
            **layout_registry.get_model_configuration_layout_config(
                'sprake'
            )
        ),
        template_dsa_configuration_layout.create_dsa_layout(
            **layout_registry.get_dsa_layout_config(
                'sprake'
            )
        ),
        template_psa_configuration_layout.create_psa_layout(
            **layout_registry.get_psa_layout_config(
                'sprake'
            )
        ),

    ])

    acm = NewsegsBrowserCacheManager(
        cache,
        noncaching_background_callback_manager,
        logger = logger
    )

    # Can't late bind callbacks - do it now
    app = add_display_callbacks(app, acm)
    app = model_selection_callbacks.assign_callbacks(app, acm)
    app = model_configuration_callbacks.add_initial_callbacks(app, acm)
    app = model_configuration_callbacks.add_model_to_interface_callbacks(app, acm)
    app = model_configuration_callbacks.add_feedback_callbacks(app, acm)
    app = model_configuration_callbacks.add_interface_to_model_callbacks(app, acm)
    app = model_run_callbacks.add_model_run_callbacks(app, acm)
    app = model_run_callbacks.add_finance_run_callbacks(app, acm)
    app = postprocess_callbacks.add_postprocess_callbacks(app, acm)
    app = results_callbacks.add_result_header_callbacks(app, acm)
    app = results_callbacks.add_result_table_callbacks(app, acm)
    app = timeseries_callbacks.add_result_timeseries_callbacks(app, acm)
    app = configuration_selector_callbacks.add_configuration_selection_callbacks(app, acm)
    app = dsa_run_callbacks.add_dsa_run_callbacks(app, acm)
    app = psa_run_callbacks.add_psa_run_callbacks(app, acm)
    app = optim_run_callbacks.add_optim_run_callbacks(app, acm)
    app = add_site_selector_callbacks(app, acm)
    app = add_background_callback_error_dispatch(app, acm)
    app = add_caching_callbacks(app, acm)

    return app

if __name__ == '__main__':
    logging.basicConfig(filename='app.log', level=logging.INFO)
    app = create_app()

    app.run(debug = True)
