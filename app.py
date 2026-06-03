"""
NewSEGS model as a multi-page app.
"""
import copy
import os
import logging
from typing import cast

from dash import Dash, dcc, html, Input, Output, State, callback
import dash_bootstrap_components as dbc
# At the moment, use a diskcache cache for transferring models 
# regardless of background callback manager
import diskcache

from config import settings

from src.newsegsmodel import newsegsmodel
from src.newsegsfinance import newsegsfinance

from src.newsegsbrowser.layouts import model_selection_layout
from src.newsegsbrowser.layouts import template_landing_layout
from src.newsegsbrowser.layouts import template_model_configuration_layout
from src.newsegsbrowser.layouts import template_dsa_configuration_layout
from src.newsegsbrowser.layouts import layout_registry

from src.newsegsbrowser.callbacks import model_selection_callbacks
from src.newsegsbrowser.callbacks import model_configuration_callbacks
from src.newsegsbrowser.callbacks import model_run_callbacks
from src.newsegsbrowser.callbacks import postprocess_callbacks
from src.newsegsbrowser.callbacks import results_callbacks
from src.newsegsbrowser.callbacks import callbacks_map
from src.newsegsbrowser.callbacks import timeseries_callbacks
from src.newsegsbrowser.callbacks import configuration_selector_callbacks
from src.newsegsbrowser.map import add_site_selector_callbacks

from src.newsegsbrowser.postprocess import postprocess_utils

from src.newsegsbrowser import energy_balance_estimation

logger = logging.getLogger(__name__)

BOOTSTRAP_STYLESHEETS = [dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]

models = {}
finances = {}
results = {}
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

def serve_layout():
    """
    
    """

    return html.Div([
        dcc.Location(id = 'url', refresh = 'callback-nav'),
        html.Div(id = 'page-content'),
        dcc.Store(id = 'selected-model', data = 'sprake'),
        dcc.Store(id = 'store-selected-configuration'),
        dcc.Store(id = 'store-configurations')
    ])

def add_display_callbacks(app: Dash) -> Dash:
    """
    Attach callbacks for multi-page handling to app
    """
    app = app

    @app.callback(
        Output('page-content', 'children'),
        Input('url', 'pathname'),
        State('selected-model', 'data'),
        State('store-selected-configuration', 'data')
    )
    def display_page(pathname, selected_model, selected_conf):
        print(selected_conf)
        if pathname == '/' or pathname == '/model_selection':
            return model_selection_layout.model_selection_layout
        elif pathname == '/landing':
            return template_landing_layout.create_landing_layout(
                **layout_registry.get_landing_layout_config(
                    selected_model
                )
            )
        elif pathname == '/site-config':
            return template_model_configuration_layout.create_model_configuration_layout(
                **layout_registry.get_model_configuration_layout_config(
                    selected_model
                )
            )
        elif pathname == '/dsa':
            return template_dsa_configuration_layout.create_dsa_layout(
                **layout_registry.get_dsa_layout_config(
                    selected_model
                )
            )

        else:
            return '404'
    
    return app
import json

def add_caching_callbacks(app):
    @app.callback(
        Output('trigger-post-model-run', 'data'),
        Input('trigger-model-run', 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager
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
        Output('trigger-post-finance-run', 'data'),
        Input('trigger-finance-run', 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager
    )
    def run_finance(finance_run_request):
        finance_run = json.loads(finance_run_request)
        model_id = finance_run['model_id']
        finance_id = finance_run['finance_id']
        mdl = cast(newsegsmodel.NewsegsModel, cache.get(model_id))

        fnc = cast(newsegsfinance.NewsegsFinance, cache.get(finance_id))
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
    
    assets_path = '/assets'
    app = Dash(
        __name__,
        #suppress_callback_exceptions = True,
        title = 'NewSEGS Energy Model',
        external_stylesheets = external_stylesheets,
        assets_url_path = assets_path,
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
            )

    ])

    app.models = models # pyright: ignore[reportAttributeAccessIssue]
    app.finances = finances # pyright: ignore[reportAttributeAccessIssue]
    app.results = results # pyright: ignore[reportAttributeAccessIssue]
    app.estimated_energy_balance = energy_balance_estimation.EstimatedEnergyBalance() # pyright: ignore[reportAttributeAccessIssue]
    app.cache = cache # pyright: ignore[reportAttributeAccessIssue]
    app.noncaching_background_callback_manager = noncaching_background_callback_manager # pyright: ignore[reportAttributeAccessIssue]

    def model_to_cache(model_id):
        mdl = models.get(model_id)
        logger.info('writing model %s to cache', model_id)
        if mdl:
            cache[model_id] = mdl
        logger.info('writing model %s to cache was successful', model_id)
    
    def model_from_cache(model_id) -> newsegsmodel.NewsegsModel:
        logger.info('retrieiving model %s from cache', model_id)
        mdl = cache.get(model_id)
        if not isinstance(mdl, newsegsmodel.NewsegsModel):
            raise TypeError(f'{model_id} retrieved from cache is of type {type(mdl)}')
        return mdl
    
    app.model_to_cache = model_to_cache # pyright: ignore[reportAttributeAccessIssue]
    app.model_from_cache = model_from_cache # pyright: ignore[reportAttributeAccessIssue]

    def finance_to_cache(finance_id):
        fnc = finances.get(finance_id)
        if fnc:
            cache[finance_id] = fnc
    
    def finance_from_cache(finance_id) -> newsegsfinance.NewsegsFinance:
        fnc = cache.get(finance_id)
        if not isinstance(fnc, newsegsfinance.NewsegsFinance):
            raise TypeError(f'{finance_id} retrieved form cache is of type {type(fnc)}')
        return fnc
    
    app.finance_to_cache = finance_to_cache # pyright: ignore[reportAttributeAccessIssue]
    app.finance_from_cache = finance_from_cache # pyright: ignore[reportAttributeAccessIssue]

    def duplicate_model(model_id: str):
        ref = models.get(model_id, None)
        if ref is None:
            return None
        mdl = type(ref)(ref)
        models[mdl.id] = mdl
        new_model_id = mdl.id
        mdl.last_run = ref.last_run
        mdl._last_hash = hash((mdl.id, str(mdl.last_run)))
        # Copy over any results
        for res_class in ['generation', 'storage', 'consumption', 'net_energy']:
            ref_id = postprocess_utils.get_model_result_id(
                postprocess_utils.RESULT_CACHE_PREFIXES[res_class],
                model_id)
            new_id = postprocess_utils.get_model_result_id(
                postprocess_utils.RESULT_CACHE_PREFIXES[res_class],
                new_model_id
            )
            results[new_id] = copy.copy(results.get(ref_id))
            results[new_id]['run_hash'] = hash(mdl)

        return mdl
    
    def duplicate_finance(finance_id: str, model_id: str|None = None):
        ref = finances.get(finance_id, None)
        if ref is None:
            return None
        
        ref_model_id = ref.model.id
        if not model_id:
            model_id = ref_model_id
        fnc = type(ref)(ref)
        fnc.model = models.get(model_id, None)
        finances[fnc.id] = fnc
        
        # Copy over any results
        for res_class in ['finance_benefits_so', 'finance_costs_so', 'finance_value_so']:
            ref_id = postprocess_utils.get_finance_result_id(
                postprocess_utils.RESULT_CACHE_PREFIXES[res_class], 
                ref.id, 
                ref_model_id
            )
            new_id = postprocess_utils.get_finance_result_id(
                postprocess_utils.RESULT_CACHE_PREFIXES[res_class], 
                fnc.id,
                model_id
            )
            results[new_id] = copy.copy(results.get(ref_id))
            results[new_id]['run_hash'] = hash(fnc) + hash(fnc.model)
            
        return fnc
    
    app.duplicate_model = duplicate_model # pyright: ignore[reportAttributeAccessIssue]
    app.duplicate_finance = duplicate_finance # pyright: ignore[reportAttributeAccessIssue]

    def remove_model(model_id):
        cache.delete(model_id)
        res_remove = []
        for k in results.keys():
            if model_id in k:
                res_remove.append(k)
        if res_remove:
            for k in res_remove:
                results.pop(k)
        return models.pop(model_id, None)
    
    def remove_finance(finance_id):
        cache.delete(finance_id)
        res_remove = []
        for k in results.keys():
            if finance_id in k:
                res_remove.append(k)
        if res_remove:
            for k in res_remove:
                results.pop(k)
        return finances.pop(finance_id, None)
    
    app.remove_model = remove_model # pyright: ignore[reportAttributeAccessIssue]
    app.remove_finace = remove_finance # pyright: ignore[reportAttributeAccessIssue]

    app = add_display_callbacks(app)

    # Can't late bind callbacks - do it now
    app = model_selection_callbacks.assign_callbacks(app)
    app = model_configuration_callbacks.add_initial_callbacks(app)
    app = model_configuration_callbacks.add_model_to_interface_callbacks(app)
    app = model_configuration_callbacks.add_feedback_callbacks(app)
    app = model_configuration_callbacks.add_interface_to_model_callbacks(app)
    app = model_run_callbacks.add_model_run_callbacks(app)
    app = model_run_callbacks.add_finance_run_callbacks(app)
    app = postprocess_callbacks.add_postprocess_callbacks(app)
    app = results_callbacks.add_result_header_callbacks(app)
    app = results_callbacks.add_result_table_callbacks(app)
    app = timeseries_callbacks.add_result_timeseries_callbacks(app)
    app = configuration_selector_callbacks.add_configuration_selection_callbacks(app)
    app = add_site_selector_callbacks(app)

    app = add_caching_callbacks(app)

    return app

if __name__ == '__main__':
    logging.basicConfig(filename='app.log', level=logging.INFO)
    app = create_app()

    app.run(debug = True)
