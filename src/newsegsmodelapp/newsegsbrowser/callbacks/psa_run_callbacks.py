"""
Callbacks for handling PSA runs
"""
import base64
import io
import json
import logging
import os
import tempfile
import zipfile
from typing import Any, MutableMapping

from dash import ALL, Dash, Input, Output, State, no_update, Patch, ctx, dcc
import pandas as pd
import pathvalidate


from newsegsmodelapp.newsegsbrowser import common as browser
from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager
from newsegsmodelapp.newsegsbrowser.callbacks.configuration_selector_callbacks import metamodel_to_dict
from newsegsmodelapp.newsegsbrowser.postprocess import postprocess_utils
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import psa
from newsegsmodelframework.util import jsonfuncs

logger = logging.getLogger(__name__)

def add_psa_run_callbacks(app: Dash, acm: NewsegsBrowserCacheManager):
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'psa-run-confirm'},
                    'is_open'
                )
            }
        },
        inputs = {
            'psa_run_button': {
                'n_clicks': Input({'type': 'psa-run-button', 'page': ALL}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-button', 'page': ALL, 'key': 'psa-run-confirm'},
                    'n_clicks'
                )
                
            },
            'psa_prerun_button': {
                'n_clicks': Input({'type': 'psa-prerun-button', 'page': ALL}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'psa-run-confirm'},
                    'id'
                )
            }
        }
    )
    def confirm_psa_run(
        psa_run_button,
        modal_close_button,
        psa_prerun_button,
        modal,
    ):
        n_modals = len(modal['ids'])
        if n_modals == 0:
            return dict(modal = dict(is_opens = []))
        trig_id = ctx.triggered_id
        if trig_id is None:
            return dict(modal = dict(is_opens = [no_update] * n_modals))
        
        if trig_id.get('type') == 'psa-prerun-button':
            return dict(modal = dict(is_opens = [True] * n_modals))
        else:
            return dict(modal = dict(is_opens = [False] * n_modals))
        
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'psa-download-confirm'},
                    'is_open'
                )
            },
            'download': {
                'datas': Output(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'psa'},
                    'data'
                )
            },
        },
        inputs = {
            'results_download_button': {
                'n_clicks': Input({'type': 'results-download-btn', 'page': ALL, 'key': 'psa'}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-btn', 'page': ALL, 'key': 'psa-download-confirm'},
                    'n_clicks'
                )
                
            },
            'results_predownload_button': {
                'n_clicks': Input({'type': 'results-predownload-btn', 'page': ALL, 'key': 'psa'}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'psa-download-confirm'},
                    'id'
                )
            },
            'options': {
                'values': State(
                    {'type': 'psa-result-download-option', 'page': ALL, 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'psa-result-download-option', 'page': ALL, 'key': ALL},
                    'id'
                )
            },
            'download': {
                'ids': State(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'psa'},
                    'id'
                )
            },
            'selected_configuration': State('store-selected-configuration', 'data'),
        },
        prevent_initial_call = True
    )
    def confirm_psa_results_download(
        results_download_button,
        modal_close_button,
        results_predownload_button,
        modal,
        options,
        download,
        selected_configuration,
    ):
        n_modals = len(modal['ids'])
        n_downloads = len(download['ids'])
        trig_id = ctx.triggered_id
        rval: dict[str, Any] = dict(
            modal = dict(is_opens = [no_update] * n_modals),
            download = dict(datas =  [no_update] * n_downloads)
        )
        if trig_id is None:
            return rval
        
        match trig_id.get('type'):
            case 'results-predownload-btn':
                rval['modal']['is_opens'] = [True] * n_modals
                return rval
            case 'results-download-btn':
                rval['modal']['is_opens'] = [False] * n_modals
                page = trig_id.get('page')
                opts = browser.get_options(
                    options['ids'],
                    options['values'],
                    page,
                    ['contents-option', 'format-option']
                )
                selected_configuration = json.loads(selected_configuration)

                to_export = browser.export_results(
                    'psa',
                    selected_configuration,
                    app,
                    opts.get('contents-option', 'result'),
                    opts.get('format-option', 'csv')
                )
                
                if to_export is not None:
                    for idx, id in enumerate(download['ids']):
                        if id['page'] == page:
                            rval['download']['datas'][idx] = to_export
            case _:
                rval['modal']['is_opens'] = [False] * n_modals
        return rval
    
    @app.callback(
        output = dict(
            configurations = Output('store-configurations', 'data', allow_duplicate = True),
            selected_configuration = Output('store-selected-configuration', 'data', allow_duplicate = True),

            triggers = dict(values = Output({'type': 'trigger', 'page': ALL, 'key': 'psa-run-postprocess'}, 'data', allow_duplicate = True))
        ),
        inputs = dict(
            uploads = dict(
                datas = Input({'type': 'results-upload', 'page': ALL, 'key': 'psa'}, 'contents'),
                filenames = Input({'type': 'results-upload', 'page': ALL, 'key': 'psa'}, 'filename'),
                ids = State({'type': 'results-upload', 'page': ALL, 'key': 'psa'}, 'id')
            )
        ),
        state = dict(
            triggers = dict(ids = State({'type': 'trigger', 'page': ALL, 'key': 'psa-run-postprocess'}, 'id')),
            configurations = State('store-configurations', 'data'),
            selected_configuration = State('store-selected-configuration', 'data'),
        ),
        prevent_initial_call = True
    )
    def upload_psa_results(
        uploads,
        triggers,
        configurations,
        selected_configuration
    ):
        rval: dict[str, Any] = dict(
            configurations = no_update,
            selected_configuration = no_update,
            triggers = dict(values = [no_update] * len(triggers['ids']))
        )

        trig = ctx.triggered_id
        if trig is None:
            return rval
        
        page = trig.get('page')
        
        raw_data = None
        raw_filename = None
        for idx, id in enumerate(uploads['ids']):
            if id['page'] == trig['page'] and id['key'] == trig['key']:
                if uploads['datas'][idx] is None:
                    return rval
                raw_data = uploads['datas'][idx]
                raw_filename = uploads['filenames'][idx]
                break
        if raw_data is None:
            return rval
        
        ctype, cstr = raw_data.split(',')
        decoded = base64.b64decode(cstr)
        split_fn = str(raw_filename).rsplit('.', 1)
        if len(split_fn) == 2:
            file_ext = split_fn[1]
        else:
            file_ext = 'csv'
        
        result_df = None
        selected_configuration = json.loads(selected_configuration)
        try:
            match file_ext:
                case 'csv':
                    result_df = pd.read_csv(io.StringIO(decoded.decode('utf-8')))
                case 'xlsx':
                    result_df = pd.read_excel(io.BytesIO(decoded))
                case 'zip':
                    with tempfile.TemporaryDirectory() as temp_dir:
                        with zipfile.ZipFile(io.BytesIO(decoded), 'r') as zip_ref:
                            zip_ref.extractall(temp_dir)
                        
                        results_file = None
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.endswith('psa-results.csv') or file.endswith('psa-results.xlsx'):
                                    results_file = os.path.join(root, file)
                                    break
                        if results_file is None:
                            return rval
                        
                        new_mm = None
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.endswith('.json'):
                                    json_file = os.path.join(root, file)
                                    try:
                                        with open(json_file, 'r') as f:
                                            cfg = json.load(f)
                                            new_mm = browser.metamodel_from_configuration_file(
                                                cfg,
                                                selected_configuration,
                                                configurations,
                                                app,
                                                overwrite_selected_config = False
                                            )
                                            if new_mm is not None:
                                                break
                                    except ValueError as e:
                                        logger.error(str(e))
                                        continue
                        
                        if new_mm:
                            selected_configuration = new_mm.to_config()
                            selected_configuration['config_index'] = len(configurations) - 1
                            
                            rval['configurations'] = configurations
                            rval['selected_configuration'] = json.dumps(selected_configuration) # pyright: ignore[reportArgumentType]
                        
                        split_results_fn = str(results_file).rsplit('.', 1)
                        if len(split_results_fn) == 2:
                            result_file_ext = split_results_fn[1]
                        else:
                            result_file_ext = 'csv'
                        match result_file_ext:
                            case 'csv':
                                result_df = pd.read_csv(results_file)
                            case 'xlsx':
                                result_df = pd.read_excel(results_file)
        except Exception as e:
            logger.error(e)
            return rval
        
        if result_df is None:
            # Should never be reached
            logger.error('No results in archive, but initial results file check has passed')
            return rval
        
        # Set the result_df as appropriate for a psa result and trigger post-processing
        mm = acm.metamodels[str(selected_configuration['metamodel_id'])]
        result_id = postprocess_utils.assign_psa_results(mm, result_df)
        logger.info('Results %s created', result_id)
        acm.results[result_id] = result_df

        for idx, id in enumerate(triggers['ids']):
            if id.get('page') == page:
                rval['triggers']['values'][idx] = [json.dumps(
                    browser.psa_run_request(
                        metamodel_id = mm.id,
                        debounce = False,
                    ).as_dict()
                )]

        return rval

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
        logger.info('a psa-run-button has been hit - n_clicks is %s', n_clicks)
        
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

        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(
                browser.psa_run_request(
                    metamodel_id = selected_configuration.get('metamodel_id'), 
                    debounce = False,
                    **kwargs
                ).as_dict()
            )
        )

        return prequeue_patch

    return app

def psa_metamodel_process(
    set_progress,
    process_request: dict[str, Any],
    mm: NewsegsMetaModel,
    cache: MutableMapping[str, Any]
):
    set_progress(json.dumps(dict(value=str(1),max=str(3),message='searching for results')))
    debug_psa_run_results_fn = os.path.join('.', 'temp_psa_run_results.csv')
    if os.path.isfile(debug_psa_run_results_fn):
        set_progress(json.dumps(dict(value=str(2),max=str(3),message='loading results')))
        psa_results = (
            pd.read_csv(
                debug_psa_run_results_fn
            )
        )
    else:
        set_progression = browser.set_progression_factory(set_progress, 'PSA running')
        psa_results = psa.run_psa(
            mm,
            samples = process_request.get('samples', 10),
            return_draws = process_request.get('return_draws', False),
            seed = process_request.get('seed', None),
            progress = set_progression
        )
        psa_results.to_csv(debug_psa_run_results_fn)

    set_progress(json.dumps(dict(value=str(3),max=str(3),message='syncing results')))
    psa_result_id = postprocess_utils.assign_psa_results(mm, psa_results)
    cache[psa_result_id] = psa_results
