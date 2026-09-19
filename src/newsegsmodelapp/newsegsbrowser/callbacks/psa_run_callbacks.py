"""
Callbacks for handling PSA runs
"""
import base64
import io
import json
import logging
import os
import random
import tempfile
import zipfile
from typing import Any, cast

from dash import ALL, Input, Output, State, no_update, ctx
from dash.exceptions import PreventUpdate
import pandas as pd

from newsegsmodelapp import registers
from newsegsmodelapp.components import callback_utils, export
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import psa

logger = logging.getLogger(__name__)

def add_psa_run_callbacks(app: NewsegsDash):
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
            'psa_run_button': Input({
                'type': 'action-button', 'purpose': 'request-process',
                'supersection': 'psa', 'section': 'run',
                'key': 'psa_run_metamodel', 'subindex': ALL,
            },'n_clicks'),
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
            'active_project_id': State('active-project-id', 'data'),
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
        active_project_id,
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
                opts = callback_utils.get_options(
                    options['ids'],
                    options['values'],
                    page,
                    ['contents-option', 'format-option']
                )

                to_export = export.export_results(
                    'psa',
                    app.project_provider,
                    app.results_provider,
                    active_project_id,
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
            active_project_id = Output('active-project-id', 'data', allow_duplicate = True),

            trigger = dict(
                value = Output({
                    'type': 'postaction-trigger', 'purpose': 'trigger',
                    'supersection': 'global', 'section': 'run',
                    'key': 'psa_run_metamodel', 'subindex': 0
                }, 'data', allow_duplicate = True)
            ),
        ),
        inputs = dict(
            uploads = dict(
                datas = Input({'type': 'results-upload', 'page': ALL, 'key': 'psa'}, 'contents'),
                filenames = Input({'type': 'results-upload', 'page': ALL, 'key': 'psa'}, 'filename'),
                ids = State({'type': 'results-upload', 'page': ALL, 'key': 'psa'}, 'id')
            )
        ),
        state = dict(
           active_project_id = State('active-project-id', 'data'),
        ),
        prevent_initial_call = True
    )
    def upload_psa_results(
        uploads,
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
                                if file.endswith('psa-results.csv') or file.endswith('psa-results.xlsx'):
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
        
        # Set the result_df as appropriate for a psa result and trigger post-processing
        mm = proj.get_focussed_metamodel()
        mark_stale = mm_new is None
        app.results_provider.upsert_result('psa_single_metamodel', mm.table_config, result_df, mark_stale = mark_stale)

        rr_generator = registers.RUN_REQUEST_REGISTER['psa_single_metamodel']
        request = rr_generator(active_project_id, app.project_provider)
        request.run_id = -random.randrange(1, 10000)

        rval['trigger']['value'] = [json.dumps(request.as_dict())]

        return rval

    ##################################################
    # Totally different style for syncing psa figures - will update in future
    ##################################################
    @app.callback(
        output = {
            'plot_header' : {
                'children': Output(
                    {
                        'type': 'result-figure-header', 'purpose': 'header',
                        'supersection': 'psa', 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': 1
                    },
                    'children', allow_duplicate = True
                )
            },
            'plot': {
                'figures' : Output(
                    {                    
                        'type': 'result-figure', 'purpose': 'container',
                        'supersection': 'psa', 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': 1,
                    },
                    'figure', allow_duplicate = True
                )
            },
            'plot_container': {
                'children' : Output(
                    {'type': 'plot-container', 'page': ALL, 'key': 'psa-primary-plot'},
                    'children', allow_duplicate = True
                )
            }
        },

        inputs = {
            'psa_table': {
                'trigger': Input(
                    {
                        'type': 'postaction-trigger', 'purpose': 'trigger',
                        'supersection': ALL, 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': ALL
                    },
                    'data'
                ),
            },
            'graph_selection_dropdown': {
                'values': Input(
                    {
                        'type': 'result-table-option', 'purpose': 'plot-type',
                        'supersection': 'psa', 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': ALL
                    },
                    'value'
                ),
                'ids': State(
                    {
                        'type': 'result-table-option', 'purpose': 'plot-type',
                        'supersection': 'psa', 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': ALL
                    },
                    'id'
                )
            },
            'plot_controls': {
                'values': Input(
                    {'type': 'psa-graph-plot-control', 'page': ALL, 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'psa-graph-plot-control', 'page': ALL, 'key': ALL},
                    'id'
                ),
            }
        },

        state = {
            'plot_header': {
                'ids': State(
                    {
                        'type': 'result-figure-header', 'purpose': 'header',
                        'supersection': 'psa', 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': 1
                    },
                    'id'
                )
            },
            'plot': {
                'ids' : State(
                    {                    
                        'type': 'result-figure', 'purpose': 'container',
                        'supersection': 'psa', 'section': 'tabledraw',
                        'key': 'table_psa_metamodel', 'subindex': 1,
                    },
                    'id'
                )
            },
            'plot_container': {
                'ids' : State(
                    {'type': 'plot-container', 'page': ALL, 'key': 'psa-primary-plot'},
                    'id'
                )
            },
            'active_project_id': State('active-project-id', 'data'),
        },

        prevent_initial_call = True
    )
    def sync_psa_primary_plot_to_store(
        psa_table,
        graph_selection_dropdown,
        plot_controls,
        plot_header,
        plot,
        plot_container,
        active_project_id
    ):
        null_return = dict(
            plot_header = dict(children = no_update),
            plot = dict(figures = no_update),
            plot_container = dict(children = [no_update] * len(plot_container['ids'])),
        )
        rval = null_return
        if len(plot_container['ids']) == 0 or len(graph_selection_dropdown['values']) == 0:
            raise PreventUpdate
        
        trig = ctx.triggered_id
        if trig is None:
            raise PreventUpdate
        
        proj = app.project_provider.get_project(active_project_id)
        mm = proj.get_focussed_metamodel()

        psa_raw_data, _ = app.results_provider.get_result('psa_single_metamodel', mm.table_config, False)
        if psa_raw_data is None:
            raise PreventUpdate
        
        graph_type = None
        full_draw = False
        if trig.get('purpose') == 'plot-type':
            # Need to do a full graph refresh
            full_draw = True
            graph_type = callback_utils.get_triggered_value()
        
        if graph_type is None:
            graph_type = graph_selection_dropdown['values'][0]
        
        graph_drawn_indicator_key = 'psa-primary-plot-'+graph_type+'-ii'
        if not full_draw:
            graph_is_drawn = False
            for id in plot_controls['ids']:
                if id.get('key') == graph_drawn_indicator_key:
                    graph_is_drawn = True
            
                
            full_draw = not graph_is_drawn
        
        plot_funcs = psa.psa_plots.get(graph_type)
        if plot_funcs is None:
            raise ValueError(f'Plot functions not found for graph_type {graph_type}')
    
        plot_kwargs = plot_funcs['arguments'](plot_controls)
    
        if full_draw:
            rval['plot_header']['children'] = plot_funcs['controls'](plot_header['ids']['subindex'])
            
            rval['plot']['figures'] = plot_funcs['draw'](psa_raw_data, **plot_kwargs)
    
        else:
            rval['plot']['figures'] = plot_funcs['update'](psa_raw_data, **plot_kwargs)
    
        return rval
