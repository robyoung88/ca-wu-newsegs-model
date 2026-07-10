"""
Callbacks for handling PSA runs
"""
import io
import json
import logging
import tempfile
import zipfile
from typing import Any

from dash import ALL, Dash, Input, Output, State, no_update, Patch, ctx, dcc
import pathvalidate


from newsegsbrowser import common as browser
from newsegsbrowser.callbacks.configuration_selector_callbacks import metamodel_to_dict
from newsegsbrowser.postprocess import postprocess_utils
from util import jsonfuncs

logger = logging.getLogger(__name__)

def add_psa_run_callbacks(app: Dash):
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
        }
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
