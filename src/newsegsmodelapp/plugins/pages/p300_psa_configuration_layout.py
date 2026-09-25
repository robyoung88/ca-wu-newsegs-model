"""
Functions for creating a probabilistic sensitivity analysis layout
"""

import base64
from dataclasses import asdict, dataclass
import io
import json
import os
import random
import tempfile
from typing import Any, Callable, cast
import zipfile

from dash import ALL, Input, Output, State, ctx, dcc, html
from dash.exceptions import PreventUpdate
import pandas as pd

from newsegsmodelapp import registers
from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components.layouts.page_layouts import fourpane_layout
from newsegsmodelapp.components import callback_utils, export, navigation
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.components import icons
from newsegsmodelapp.components.layouts import result_group_containers, results_header
from newsegsmodelapp.types import Page
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import psa
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

from .processes.psa_process_components import psa_process_components

PAGE_TYPE = 'psa'

def create_psa_header(**kwargs):
    return dbc.Container(
        [
            dbc.Row(
                [
                    dbc.Col(
                        [
                            html.H3(
                                'Probabilistic Sensitivity Analysis',
                                className='text-end mb-0',
                            )
                        ],
                        width = 6,
                        className='d-flex align-items-center justify-content-end pe-3 border-end border-2 border-secondary',
                    ),
                    dbc.Col(
                        [
                            html.H3(
                                id = {'type': 'generic_text', 'section': 'any', 'key': 'project-name'},
                                className='text-start mb-0',
                            )
                        ],
                        width = 6,
                        className='d-flex align-items-center justify-content-start ps-3',
                    ),

                ],
            className='align-items-stretch',  # Stretches the columns to match height, allowing the vertical border to extend
            ),
            dbc.Row(
                dbc.Col(
                    create_header_metamodel_input_container('psa'),
                    class_name = 'align-items-center text-center'
                )
            )
        ],
        fluid = True
    )

def create_psa_configuration_editor():
    return dbc.Col([
        html.Div([
            html.H2(
                'PSA Configuration',
                style = {'display': 'inline-flex',
                         'margin-right': '20px'}
            ),
            ],
            style = {'vertical-align': 'baseline'}
            ),
        html.Hr(),
        html.Div(
            html.P(
                html.H3('PSA Settings')
            )
        ),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'psa', 'section': 'psa-settings'},
        ),
        html.Hr(),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'psa', 'section': 'psa'}
        )
    ])

@dataclass
class PSAConfigurationLayoutConfiguration(registers.LayoutConfiguration):
    page_type: str = PAGE_TYPE

    layout_navigation: Callable[[str], Any] = navigation.create_navigation_component
    width_navigation: int = 1
    layout_top: Callable[[], Any] = create_psa_header
    layout_results_header: Callable = results_header.create_results_header_psa

def create_psa_layout(config: PSAConfigurationLayoutConfiguration):
    kwargs = asdict(config)
   
    a1_contents = [
        dbc.Row([
            dbc.Col(
                config.layout_navigation(config.model_type),
                width = 'auto',
            ),
            dbc.Col(
                config.layout_top(**kwargs),
                class_name = 'page-top'
            ),
        ],
        class_name = 'align-items-start'
        )
    ]

    psa_config = create_psa_configuration_editor()

    a2_contents = [
        psa_config,
    ]

    b1_contents = [
        dbc.Container(
            [
                dbc.Row(
                    config.layout_results_header(**kwargs)
                )
            ]
        )
    ]

    b2_contents = [
        result_group_containers.create_results_container([
            dbc.Container(
                [
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.H2("PSA Results Table"),
                                    html.Div(
                                        'No PSA Run',
                                        id = {
                                            'type': 'result-table', 'purpose': 'container',
                                            'supersection': 'psa', 'section': 'tabledraw',
                                            'key': 'table_psa_metamodel', 'subindex': 0,
                                        }
                                    )
                                ],
                                width = 12
                            ),
                        ]
                    ),
                    html.Hr(),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Div([
                                        dcc.Dropdown(
                                            options = psa.PSA_PLOT_TYPES,
                                            value = psa.PSA_PLOT_TYPES[0],
                                            id = {
                                                'type': 'result-table-option', 'purpose': 'plot-type',
                                                'supersection': 'psa', 'section': 'tabledraw',
                                                'key': 'table_psa_metamodel', 'subindex': 0
                                            },
                                            searchable = False,
                                            clearable = False,
                                        )
                                    ]),
                                    html.Div(
                                        html.H2(""),
                                        id = {
                                            'type': 'result-figure-header', 'purpose': 'header',
                                            'supersection': 'psa', 'section': 'tabledraw',
                                            'key': 'table_psa_metamodel', 'subindex': 1
                                        },
                                    ),
                                    
                                    html.Div(
                                        dcc.Graph(
                                            id = {
                                                'type': 'result-figure', 'purpose': 'container',
                                                'supersection': 'psa', 'section': 'tabledraw',
                                                'key': 'table_psa_metamodel', 'subindex': 1,
                                            },
                                            style= {
                                                'height': '590px',
                                                'border': '1px solid #dee2e6',
                                                'borderRadius': '0.5rem',
                                                'backgroundColor': 'transparent'
                                            }
                                        ),
                                        style={'display':'block', 'height': '600px'},
                                        id = {'type': 'plot-container', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-primary-plot'},
                                    )
                                ],
                                width = 12
                            ),
                            dcc.Store(id={'type': 'trigger', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-run-postprocess'}, data = []),
                            dcc.Store(id={'type': 'result-statistics', 'supersection': 'psa-results', 'key': 'res-psa-table'}, data = []),
                        ]
                    )
                ]
            ),
        ]),
        dbc.Button(
            'Cancel PSA',
            id = {'type': 'metamodel-process-cancel', 'target': 'psa_run_request'},
            class_name = 'background-callback-cancel-button background-callback-cancel-button-hidden'
        ),
        html.Progress(
            id={'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')},
            className='resize-handle resize-handle-progress',
            style = {'display': 'none'}
        ),
        dbc.Tooltip(
            'PSA Running',
            id = {'type': 'progress-tooltip', 'page': kwargs.get('page_type', 'None')},
            target = {'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')}
        ),
    ] + psa_process_components(**kwargs)

    return fourpane_layout(
        a1_contents,
        b1_contents,
        a2_contents,
        b2_contents,
    )

def add_psa_run_callbacks(app: NewsegsDash):
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output('modal-psa-confirm', 'is_open')
            }
        },
        inputs = {
            'psa_run_button': Input('btn-action-psa-run-metamodel','n_clicks'),
            'modal_close_button': {
                'n_clicks': Input('btn-psa-confirm-abort','n_clicks')
                
            },
            'psa_prerun_button': {
                'n_clicks': Input('btn-psa-prerun', 'n_clicks'),
            },
        },
        prevent_initial_call = True,
    )
    def confirm_psa_run(
        psa_run_button,
        modal_close_button,
        psa_prerun_button,
    ):
        clicks = callback_utils.get_triggered_value()
        if not clicks:
            raise PreventUpdate
        
        trig_id = ctx.triggered_id
        if trig_id is None:
            raise PreventUpdate

        rval = callback_utils.create_noupdate_return()
        if trig_id == 'btn-psa-prerun':
            rval['modal']['is_opens'] = True
        else:
            rval['modal']['is_opens'] = False

        return rval
        
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output('modal-psa-download-confirm', 'is_open')
            },
            'download': {
                'datas': Output('download-psa-result', 'data')
            },
        },
        inputs = {
            'results_download_button': {
                'n_clicks': Input('btn-psa-download-confirm-ok', 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input('btn-psa-download-confirm-abort', 'n_clicks')
                
            },
            'results_predownload_button': {
                'n_clicks': Input('btn-psa-result-predownload', 'n_clicks'),
            },
        },
        state = {
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
            'active_project_id': State('active-project-id', 'data'),
        },
        prevent_initial_call = True
    )
    def confirm_psa_results_download(
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
                case 'btn-psa-download-confirm-ok':
                    rval['modal']['is_opens'] = False
                    opts = callback_utils.get_options_nopage(
                        options['ids'],
                        options['values'],
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
                        rval['download']['datas'] = to_export

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
                    'key': 'psa_run_metamodel', 'subindex': 0
                }, 'data', allow_duplicate = True)
            ),
        ),
        inputs = dict(
            upload = dict(
                data = Input('upload-psa-result', 'contents'),
                filename = Input('upload-psa-result', 'filename'),
                id = State('upload-psa-result', 'id')
            )
        ),
        state = dict(
           active_project_id = State('active-project-id', 'data'),
        ),
        prevent_initial_call = True
    )
    def upload_psa_results(
        upload,
        active_project_id,
    ):

        trig = ctx.triggered_id
        if trig is None:
            raise PreventUpdate
        if upload['data'] is None:
            raise PreventUpdate

        raw_data = upload['data']
        raw_filename = upload['filename']
        
        if raw_data is None:
            raise PreventUpdate

        rval = callback_utils.create_noupdate_return()
        
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
                                        print(e)
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
            print(e)
            return rval
        
        if result_df is None:
            # Should never be reached
            print('No results in archive, but initial results file check has passed')
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
            'active_project_id': Input('active-project-id', 'data'),
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
        rval = callback_utils.create_noupdate_return()
        if len(plot_container['ids']) == 0 or len(graph_selection_dropdown['values']) == 0:
            raise PreventUpdate
        
        trig = ctx.triggered_id
        if trig is None:
            raise PreventUpdate
        
        proj = app.project_provider.get_project(active_project_id)
        mm = proj.get_focussed_metamodel()

        psa_raw_data, _ = app.results_provider.get_result('psa_single_metamodel', mm.table_config, False)
        if psa_raw_data is None:
            rval['plot_header']['children'] = [html.Div(html.H3('No PSA Run'), className = 'd-flex justify-content-center w-100')]
            graph_type = graph_selection_dropdown['values'][0]
            plot_funcs = psa.psa_plots.get(graph_type)
            if plot_funcs is None:
                rval['plot']['figures'] = []
            else:
                rval['plot']['figures'] = plot_funcs['draw'](None)
            return rval
        
        graph_type = None
        full_draw = False
        if isinstance(trig, str) or trig.get('purpose') == 'plot-type':
            # Need to do a full graph refresh
            full_draw = True
            if not isinstance(trig, str):
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

    @app.callback(
        Output('trigger-check-requests', 'data', allow_duplicate = True),
        Input('btn-action-psa-run-metamodel', 'n_clicks'),
        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def request_psa_run_metamodel(
        n_clicks,
        active_project_id
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        request_id = app.request_handler.add_request(
            'psa_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
        )

        return request_id

psa_configuration_page = Page(
    id = PAGE_TYPE,
    nav_label = 'Probabilistic analysis',
    nav_icon = html.I(
        className = icons.get_icon('nav-psa-config', style_name = 'raw'),
        style = {'display': 'inline'}
    ),
    layout = create_psa_layout, # pyright: ignore[reportArgumentType]
    default_configuration = PSAConfigurationLayoutConfiguration(),
    attach_callbacks = add_psa_run_callbacks
)
registers.add_page(psa_configuration_page)
