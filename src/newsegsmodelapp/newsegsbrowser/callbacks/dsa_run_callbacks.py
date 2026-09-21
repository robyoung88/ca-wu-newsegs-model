"""
Callbacks for handling DSA runs
"""
import base64
import io
import json
import logging
import os
import random
import tempfile
import time
from typing import Any, cast
import zipfile

from dash import ALL, MATCH, Input, Output, State, no_update, ctx
from dash.exceptions import PreventUpdate
import dash_ag_grid as dag
import pandas as pd

from newsegsmodelapp import registers
from newsegsmodelapp.components import callback_utils, export
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

logger = logging.getLogger(__name__)

def add_dsa_run_callbacks(app: NewsegsDash):
    if True:
        @app.callback(
            output = {
                'modal': {
                    'is_opens': Output('modal-dsa-confirm', 'is_open')
                }
            },
            inputs = {
                'dsa_run_button': {
                    'n_clicks': Input(
                        'btn-action-dsa-run-metamodel',
                        'n_clicks'
                    ),
                },
                'modal_close_button': {
                    'n_clicks': Input('btn-dsa-confirm-abort', 'n_clicks'),
                },
                'dsa_prerun_button': {
                    'n_clicks': Input('btn-dsa-prerun', 'n_clicks'),
                },
            },
            prevent_initial_call = True
        )
        def confirm_dsa_run(
            dsa_run_button,
            modal_close_button,
            dsa_prerun_button,
        ):
            clicks = callback_utils.get_triggered_value()
            if not clicks:
                raise PreventUpdate
            
            trig_id = ctx.triggered_id
            if trig_id is None:
                raise PreventUpdate

            rval = callback_utils.create_noupdate_return()
            if trig_id == 'btn-dsa-prerun':
                rval['modal']['is_opens'] = True
            else:
                rval['modal']['is_opens'] = False
            return rval
        
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output('modal-dsa-download-confirm', 'is_open')
            },
            'download': {
                'datas': Output('download-dsa-result', 'data')
            },
        },
        inputs = {
            'results_download_button': {
                'n_clicks': Input('btn-dsa-download-confirm-ok', 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input('btn-dsa-download-confirm-abort', 'n_clicks')
                
            },
            'results_predownload_button': {
                'n_clicks': Input('btn-dsa-result-predownload', 'n_clicks'),
            },
        },
        state = {
            'options': {
                'values': State(
                    {'type': 'dsa-result-download-option', 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'dsa-result-download-option', 'key': ALL},
                    'id'
                )
            },
            'active_project_id': State('active-project-id', 'data'),
        }
    )
    def confirm_dsa_results_download(
        results_download_button,
        modal_close_button,
        results_predownload_button,
        options,
        active_project_id,
    ):
        trig_id = ctx.triggered_id
        if trig_id is None:
            raise PreventUpdate
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        rval = callback_utils.create_noupdate_return()

        if isinstance(trig_id, str):
            match trig_id:
                case 'btn-dsa-download-confirm-ok':
                    rval['modal']['is_opens'] = False
                    opts = callback_utils.get_options_nopage(
                        options['ids'],
                        options['values'],
                        ['contents-option', 'format-option']
                    )
    
                    to_export = export.export_results(
                        'dsa',
                        app.project_provider,
                        app.results_provider,
                        active_project_id,
                        opts.get('contents-option', 'result'),
                        opts.get('format-option', 'csv')
                    )
                    
                    if to_export is not None:
                        rval['download']['datas'] = to_export

                case 'btn-dsa-result-predownload':
                    rval['modal']['is_opens'] = True

                case _:
                    rval['modal']['is_opens'] = False
        else:
            match trig_id.get('type'):
                case 'results-predownload-btn':
                    rval['modal']['is_opens'] = True
                    return rval
            
                case _:
                    rval['modal']['is_opens'] = False
        return rval
    
    @app.callback(
        output = dict(
            active_project_id = Output('active-project-id', 'data', allow_duplicate = True),

            trigger = dict(
                value = Output({
                    'type': 'postaction-trigger', 'purpose': 'trigger',
                    'supersection': 'global', 'section': 'run',
                    'key': 'dsa_run_metamodel', 'subindex': 0
                }, 'data', allow_duplicate = True)
            ),
        ),
        inputs = dict(
            upload = dict(
                data = Input('upload-dsa-result', 'contents'),
                filename = Input('upload-dsa-result', 'filename'),
                id = State('upload-dsa-result', 'id')
            )
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
        ),
        prevent_initial_call = True
    )
    def upload_dsa_results(
        upload,
        active_project_id,
    ):
        rval: dict[str, Any] = dict(
            active_project_id = no_update,
            trigger = dict(value = no_update)
        )

        trig = ctx.triggered_id
        if trig is None:
            return rval
        
        raw_data = None
        raw_filename = None
        if upload['data'] is None:
            raise PreventUpdate
        raw_data = upload['data']
        raw_filename = upload['filename']
        
        if raw_data is None:
            raise PreventUpdate
        
        ctype, cstr = raw_data.split(',')
        decoded = base64.b64decode(cstr)
        split_fn = str(raw_filename).rsplit('.', 1)
        if len(split_fn) == 2:
            file_ext = split_fn[1]
        else:
            file_ext = 'csv'

        proj = app.project_provider.get_project(active_project_id)
        result_df = None
        mm_new = None
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
                                if file.endswith('dsa-results.csv') or file.endswith('dsa-results.xlsx'):
                                    results_file = os.path.join(root, file)
                                    break
                        if results_file is None:
                            return rval

                        
                        for root, dirs, files in os.walk(temp_dir):
                            for file in files:
                                if file.endswith('.json'):
                                    json_file = os.path.join(root, file)
                                    try:
                                        with open(json_file, 'r') as f:
                                            cfg = json.load(f)
                                            constr = find_constructor(cfg['constructor_class'], cfg['class'])
                                            if not constr:
                                                raise PreventUpdate
                                            mm_new = cast(NewsegsMetaModel, constr(cfg))
                                            mm_new.anonymise_ids()

                                            proj.metamodels.append(mm_new) # pyright: ignore[reportAttributeAccessIssue]
                                            proj.set_focussed_metamodel(mm_new.id)
                                            proj.revision += 1
                                            app.project_provider.upsert_component(proj)
                                            
                                    except ValueError as e:
                                        logger.error(str(e))
                                        continue
                        
                        if mm_new:
                            rval['active_project_id'] = active_project_id
                        
                        
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
        
        # Set the result_df as appropriate for a dsa result and trigger post-processing
        result_df = result_df.set_index(['variable', 'bound'])
        mm = proj.get_focussed_metamodel()
        mark_stale = mm_new is None
        app.results_provider.upsert_result('dsa_single_metamodel', mm.table_config, result_df, mark_stale = mark_stale)
        
        rr_generator = registers.RUN_REQUEST_REGISTER['dsa_single_metamodel']
        request = rr_generator(active_project_id, app.project_provider)
        request.run_id = -random.randrange(1, 10000)

        rval['trigger']['value'] = [json.dumps(request.as_dict())]

        return rval

    @app.callback(
        Output('trigger-check-requests', 'data'),
        Input('btn-action-dsa-run-metamodel', 'n_clicks'),
        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def request_dsa_run_metamodel(
        n_clicks,
        active_project_id
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        # TODO: Create request, then update trigger.

        return time.time_ns()
    