"""
NewSEGS model as a multi-page app.
"""
import copy
import datetime
import os
import time
import logging
from typing import Literal, cast, MutableMapping

from dash import ALL, Dash, dcc, html, Input, Output, State, callback, no_update
import dash_bootstrap_components as dbc
# At the moment, use a diskcache cache for transferring models 
# regardless of background callback manager
import diskcache
import pandas as pd

# For local testing
import sys

curdir = os.path.dirname(__file__)
src_path = os.path.join(
    curdir,
    'src'
)
sys.path.append(src_path)


from config import settings

from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance
from newsegsmetamodel import NewsegsMetaModel
from newsegssensitivity import dsa
from newsegssensitivity import psa

from newsegsbrowser.layouts import model_selection_layout, template_psa_configuration_layout
from newsegsbrowser.layouts import template_landing_layout
from newsegsbrowser.layouts import template_model_configuration_layout
from newsegsbrowser.layouts import template_dsa_configuration_layout
from newsegsbrowser.layouts import layout_registry

from newsegsbrowser.callbacks import model_selection_callbacks, psa_run_callbacks
from newsegsbrowser.callbacks import model_configuration_callbacks
from newsegsbrowser.callbacks import model_run_callbacks
from newsegsbrowser.callbacks import postprocess_callbacks
from newsegsbrowser.callbacks import results_callbacks
from newsegsbrowser.callbacks import callbacks_map
from newsegsbrowser.callbacks import timeseries_callbacks
from newsegsbrowser.callbacks import configuration_selector_callbacks
from newsegsbrowser.callbacks import dsa_run_callbacks
from newsegsbrowser.map import add_site_selector_callbacks

from newsegsbrowser.postprocess import postprocess_utils

from newsegsbrowser.background_callback_errors import add_background_callback_error_dispatch, background_callback_error_handler_factory

from newsegsbrowser import energy_balance_estimation

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
        print(pathname)

        if pathname == '/' or pathname == '/model_selection':
            return model_selection_layout.model_selection_layout
        
        splitname = str(pathname).lstrip('/').split("/")
        selected_model = splitname[0]
        print(selected_model)
        if not selected_model in ['sprake','localised']:
            return model_selection_layout.model_selection_layout
        
        pagename = '/'.join(splitname[1:])
        print(pagename)
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
import json

def add_caching_callbacks(app):
    @app.callback(
        Output({'type': 'background-callback-return', 'target': 'model-run'}, 'data', allow_duplicate = True),

        Input({'type': 'background-callback-call', 'target': 'model-run'}, 'data'),
        prevent_initial_call = True,
        background = True,
        manager = noncaching_background_callback_manager,
        on_error = background_callback_error_handler_factory('model-run')
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
        on_error = background_callback_error_handler_factory('finance-run')
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
        on_error = background_callback_error_handler_factory('metamodel-process'),
        running = [
            (
                Output({'type': 'metamodel-process-cancel', 'target': ALL}, 'class_name'), 
                'background-callback-cancel-button',
                'background-callback-cancel-button background-callback-cancel-button-hidden'
            )
        ],
        cancel=Input('background_cancel_trigger', "data"),
        # running = [
        #     (Output({'type': 'background_callback_run_button', 'key': ALL}, 'disabled'), True, False),
        #     (Output({'type': 'background_callback_cancel_button', 'key': ALL}, 'disabled'), False, True),
        #     (
        #         Output({'type':'progress_bar','key':ALL}, "style"),
        #         {"visibility": "visible"},
        #         {"visibility": "hidden"},
        #     ),
        # ],
        
        # progress=[Output('background_progress_tracker', 'data')],
        # progress_default='{"value":"0","max":"1"}',
    )
    def run_metamodel_process(metamodel_process):
        process_request = json.loads(metamodel_process)
        mm = metamodel_from_cache(process_request.get('metamodel_id'), 'cache')
        
        # Do the process
        match process_request['type']:
            case 'dsa-run-request':
                debug_dsa_run_results_fn = os.path.join('.', 'temp_dsa_run_results.csv')
                if os.path.isfile(debug_dsa_run_results_fn):
                    dsa_results = pd.read_csv(debug_dsa_run_results_fn).set_index(['variable', 'bound'])
                else:
                    dsa_results = dsa.run_dsa(
                        mm
                    ).set_index(['variable', 'bound'])
                    dsa_results.to_csv(debug_dsa_run_results_fn)
                dsa_result_id = postprocess_utils.get_dsa_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES['dsa_results'],
                    mm.id
                )
                mm.last_dsa_run = datetime.datetime.now().timestamp()
                setattr(dsa_results, '_run_time', mm.last_dsa_run)
                cache[dsa_result_id] = dsa_results

                # Not convinced this is necessary
                #mm.dsa_result_id = dsa_result_id
            case 'psa-run-request':
                debug_psa_run_results_fn = os.path.join('.', 'temp_psa_run_results.csv')
                if os.path.isfile(debug_psa_run_results_fn):
                    psa_results = (
                        pd.read_csv(
                            debug_psa_run_results_fn
                        )
                    )
                else:
                    psa_results = psa.run_psa(
                        mm,
                        samples = process_request.get('samples', 10),
                        return_draws = process_request.get('return_draws', False),
                        seed = process_request.get('seed', None)
                    )
                    psa_results.to_csv(debug_psa_run_results_fn)

                psa_result_id = postprocess_utils.get_psa_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES['psa_results'],
                    mm.id
                )

                mm.last_psa_run = datetime.datetime.now().timestamp()
                setattr(psa_results, '_run_time', mm.last_psa_run)
                cache[psa_result_id] = psa_results

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

        Input({'type': 'metamodel-process-cancel', 'target': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def set_cancel_trigger(n_clicks):
        if n_clicks is None:
            return no_update
        logger.info('User has attempted to cancel metamodel process %s', datetime.datetime.now())
        return time.time_ns()

    @app.callback(
        Output({'type':'progress_bar','key':ALL}, "value"), 
        Output({'type':'progress_bar','key':ALL}, "max"),

        Input('background_progress_tracker', 'data'),
        State({'type':'progress_bar','key':ALL}, "id"),
        prevent_initial_call = True
    )
    def set_progress_bars(progress, ids):
        if progress is None:
            return [no_update] * len(ids)
        progress = json.loads(progress)
        return ([progress['value']] * len(ids), [progress['max']] * len(ids))
    
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
        ),
        template_psa_configuration_layout.create_psa_layout(
            **layout_registry.get_psa_layout_config(
                'sprake'
            )
        ),

    ])

    # TODO: Extend the app class to create these attributes
    app.models = models # pyright: ignore[reportAttributeAccessIssue]
    app.finances = finances # pyright: ignore[reportAttributeAccessIssue]
    app.results = results # pyright: ignore[reportAttributeAccessIssue]
    app.metamodels = metamodels # pyright: ignore[reportAttributeAccessIssue]
    app.estimated_energy_balance = energy_balance_estimation.EstimatedEnergyBalance() # pyright: ignore[reportAttributeAccessIssue]
    app.cache = cache # pyright: ignore[reportAttributeAccessIssue]
    app.noncaching_background_callback_manager = noncaching_background_callback_manager # pyright: ignore[reportAttributeAccessIssue]

    def model_to_cache(model_id):
        mdl = models.get(model_id)
        logger.info('writing model %s to cache, %s', model_id, datetime.datetime.now())
        if mdl:
            cache[model_id] = mdl
        logger.info('writing model %s to cache was successful, %s', model_id, datetime.datetime.now())
    
    def model_from_cache(model_id) -> newsegsmodel.NewsegsModel:
        logger.info('retrieving model %s from cache', model_id)
        mdl = cache.get(model_id)
        if not isinstance(mdl, newsegsmodel.NewsegsModel):
            raise TypeError(f'{model_id} retrieved from cache is of type {type(mdl)}')
        logger.info('retrieving model %s was successful', model_id)
        return mdl
    
    app.model_to_cache = model_to_cache # pyright: ignore[reportAttributeAccessIssue]
    app.model_from_cache = model_from_cache # pyright: ignore[reportAttributeAccessIssue]

    def finance_to_cache(finance_id):
        fnc = finances.get(finance_id)
        logger.info('writing finance %s to cache', finance_id)
        if fnc:
            cache[finance_id] = fnc
        logger.info('writing finance %s to cache was successful', finance_id)
    
    def finance_from_cache(finance_id) -> newsegsfinance.NewsegsFinance:
        logger.info('retrieving finance %s from cache', finance_id)
        fnc = cache.get(finance_id)
        if not isinstance(fnc, newsegsfinance.NewsegsFinance):
            raise TypeError(f'{finance_id} retrieved from cache is of type {type(fnc)}')
        logger.info('retrieving finance %s was successful', finance_id)
        return fnc
    
    app.finance_to_cache = finance_to_cache # pyright: ignore[reportAttributeAccessIssue]
    app.finance_from_cache = finance_from_cache # pyright: ignore[reportAttributeAccessIssue]
    
    app.metamodel_to_cache = metamodel_to_cache  # pyright: ignore[reportAttributeAccessIssue]
    app.metamodel_from_cache = metamodel_from_cache # pyright: ignore[reportAttributeAccessIssue]
    
    def duplicate_model(model_id: str) -> newsegsmodel.NewsegsModel:
        ref = models.get(model_id, None)
        if ref is None:
            raise ValueError(f'NewsegsModel not found: {model_id}')
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
            res = results.get(ref_id)
            if res is not None:
                results[new_id] = copy.copy(res)
                results[new_id]['run_hash'] = hash(mdl)

        return mdl
    
    def duplicate_finance(
            finance_id: str, 
            model_id: str|None = None
        ) -> newsegsfinance.NewsegsFinance:
        ref = finances.get(finance_id, None)
        if ref is None:
            raise ValueError(f'NewsegsFinance not found: {finance_id}')
        
        fnc = type(ref)(ref)

        try:
            ref_model_id = ref.model.id
        except AttributeError:
            ref_model_id = None
        if not model_id:
            model_id = ref_model_id
        
        if model_id is not None:
            mdl = models.get(model_id, None)
            if mdl is not None:
                fnc.model = mdl
        finances[fnc.id] = fnc
        
        # Copy over any results
        if ref_model_id is not None:
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
                res = results.get(ref_id)
                if res is not None:
                    results[new_id] = copy.copy(res)
                    results[new_id]['run_hash'] = hash(fnc) + hash(fnc.model)
            
        return fnc
    
    def duplicate_metamodel(metamodel_id: str):
        ref = metamodels.get(metamodel_id, None)
        if ref is None:
            raise ValueError(f'NewsegsMetaModel not found: {metamodel_id}')
        
        dup_mdl = duplicate_model(ref.model_id)
        #models[dup_mdl.id] = dup_mdl

        dup_fnc = duplicate_finance(ref.finance_id, dup_mdl.id)
        #dup_fnc.set_model(dup_mdl)
        #finances[dup_fnc.id] = dup_fnc

        #variables = copy.deepcopy(list(ref.variables.values()))
        variables = copy.deepcopy(list(ref.variables.values()))
        dup_mm = NewsegsMetaModel(dup_mdl, dup_fnc, variables)

        metamodels[dup_mm.id] = dup_mm
        
        return dup_mm

    app.duplicate_model = duplicate_model # pyright: ignore[reportAttributeAccessIssue]
    app.duplicate_finance = duplicate_finance # pyright: ignore[reportAttributeAccessIssue]
    app.duplicate_metamodel = duplicate_metamodel # pyright: ignore[reportAttributeAccessIssue]

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
    
    def remove_metamodel(metamodel_id: str, remove_children: bool = True):
        if remove_children:
            mm = metamodels.get(metamodel_id)
            if mm:
                remove_model(mm.model_id)
                remove_finance(mm.finance_id)
        cache.delete(metamodel_id)
        return metamodels.pop(metamodel_id)
    
    app.remove_model = remove_model # pyright: ignore[reportAttributeAccessIssue]
    app.remove_finance = remove_finance # pyright: ignore[reportAttributeAccessIssue]
    app.remove_metamodel = remove_metamodel # pyright: ignore[reportAttributeAccessIssue]

    # Short-term stor
    app.sts = {} # pyright: ignore[reportAttributeAccessIssue]

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
    app = dsa_run_callbacks.add_dsa_run_callbacks(app)
    app = psa_run_callbacks.add_psa_run_callbacks(app)
    app = add_site_selector_callbacks(app)
    app = add_background_callback_error_dispatch(app)

    app = add_caching_callbacks(app)

    return app

if __name__ == '__main__':
    logging.basicConfig(filename='app.log', level=logging.INFO)
    app = create_app()

    app.run(debug = True)
