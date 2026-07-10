"""
Callbacks for handling DSA runs
"""
import io
import json
import logging
import tempfile
from typing import Any
import zipfile

from dash import ALL, Dash, Input, Output, State, no_update, Patch, ctx, dcc
import dash_ag_grid as dag
import pathvalidate

from newsegsbrowser import common as browser
from newsegsbrowser.callbacks.configuration_selector_callbacks import metamodel_to_dict
from newsegsbrowser.postprocess import postprocess_utils
from util import jsonfuncs

logger = logging.getLogger(__name__)

def add_dsa_run_callbacks(app: Dash):

    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'dsa-run-confirm'},
                    'is_open'
                )
            }
        },
        inputs = {
            'dsa_run_button': {
                'n_clicks': Input({'type': 'dsa-run-button', 'page': ALL}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-button', 'page': ALL, 'key': 'dsa-run-confirm'},
                    'n_clicks'
                )
                
            },
            'dsa_prerun_button': {
                'n_clicks': Input({'type': 'dsa-prerun-button', 'page': ALL}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'dsa-run-confirm'},
                    'id'
                )
            }
        }
    )
    def confirm_dsa_run(
        dsa_run_button,
        modal_close_button,
        dsa_prerun_button,
        modal,
    ):
        n_modals = len(modal['ids'])
        if n_modals == 0:
            return dict(modal = dict(is_opens = []))
        trig_id = ctx.triggered_id
        if trig_id is None:
            return dict(modal = dict(is_opens = [no_update] * n_modals))
        
        if trig_id.get('type') == 'dsa-prerun-button':
            return dict(modal = dict(is_opens = [True] * n_modals))
        else:
            return dict(modal = dict(is_opens = [False] * n_modals))
        
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'dsa-download-confirm'},
                    'is_open'
                )
            },
            'download': {
                'datas': Output(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'dsa'},
                    'data'
                )
            },
        },
        inputs = {
            'results_download_button': {
                'n_clicks': Input({'type': 'results-download-btn', 'page': ALL, 'key': 'dsa'}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-btn', 'page': ALL, 'key': 'dsa-download-confirm'},
                    'n_clicks'
                )
                
            },
            'results_predownload_button': {
                'n_clicks': Input({'type': 'results-predownload-btn', 'page': ALL, 'key': 'dsa'}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'dsa-download-confirm'},
                    'id'
                )
            },
            'options': {
                'values': State(
                    {'type': 'dsa-result-download-option', 'page': ALL, 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'dsa-result-download-option', 'page': ALL, 'key': ALL},
                    'id'
                )
            },
            'download': {
                'ids': State(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'dsa'},
                    'id'
                )
            },
            'selected_configuration': State('store-selected-configuration', 'data'),
        }
    )
    def confirm_dsa_results_download(
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
                    'dsa',
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
        
        request_ = browser.dsa_run_request(
            metamodel_id = selected_configuration.get('metamodel_id'),
            debounce = False
        )
        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(
                request_.as_dict()
            )
        )
        logger.info('Adding dsa request to prequeue-action-user: %s', request_)

        return prequeue_patch
    
    return app
