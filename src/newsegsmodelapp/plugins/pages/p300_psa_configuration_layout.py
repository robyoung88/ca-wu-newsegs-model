"""
Functions for creating a probabilistic sensitivity analysis layout
"""
import logging
logger = logging.getLogger(__name__)

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
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components.psa_group_editor import count_variables_with_different_distributions_or_sds
from newsegsmodelapp.components.layouts.page_layouts import fourpane_layout
from newsegsmodelapp.components import callback_utils, export, navigation, stats
from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.components import icons
from newsegsmodelapp.components.layouts import result_group_containers, results_header
from newsegsmodelapp.types import Page
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import common as sensitivity, psa
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

from .processes.psa_process_components import psa_process_components

PAGE_TYPE = 'psa'

def create_psa_header(**kwargs):
    """Create the header of the PSA page.

    Args:
        **kwargs: Further keyword arguments.

    Returns:
        The header.
    """
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
    """Create the editor of the PSA: its settings, and the distributions of the variables.

    Returns:
        The editor.
    """
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
            id = {'type': 'input-section-header', 'supersection': 'psa', 'section': 'psa-settings'},
            style = {'display': 'none'}
        ),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'psa', 'section': 'psa-settings'},
        ),
        dcc.Interval(
            id = {
                'type': 'input-container-hydration-interval', 
                'supersection': 'psa', 
                'section': 'psa-settings'
            },
            n_intervals = 1,
            disabled = False,
            max_intervals = 1,
            interval = 50,
        ),
        html.Hr(),
        html.Div(
            id = {'type': 'input-section-header', 'supersection': 'psa', 'section': 'psa'},
            style = {'display': 'none'}
        ),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'psa', 'section': 'psa'}
        ),
        dcc.Interval(
            id = {
                'type': 'input-container-hydration-interval', 
                'supersection': 'psa', 
                'section': 'psa'
            },
            n_intervals = 1,
            disabled = False,
            max_intervals = 1,
            interval = 50,
        ),
    ])

def _psa_project_option_id(purpose: str) -> dict:
    """Id of an option of the comparator views of a whole-project PSA (the `table_psa_project` table)"""
    return {
        'type': 'result-table-option', 'purpose': purpose,
        'supersection': 'psa', 'section': 'tabledraw',
        'key': 'table_psa_project', 'subindex': 0
    }

def _options(labels: dict) -> list[dict]:
    return [{'label': v, 'value': k} for k, v in labels.items()]

def create_psa_project_options():
    """Create the options of the comparator views of a whole-project PSA: the statistic, the plot, the comparators and the variable.

    Hidden in the individual view. The options are filled from the results by `update_psa_view_options`.

    Returns:
        The options.
    """
    def labelled(label, component):
        return html.Div([html.Label(label), component], className = 'mb-2')

    return html.Div(
        [
            dbc.Row([
                dbc.Col(labelled('Statistic:', dcc.Dropdown(
                    options = _options(sensitivity.PSA_STATISTIC_LABELS),
                    value = next(iter(sensitivity.PSA_STATISTIC_LABELS)),
                    id = _psa_project_option_id('statistic'),
                    searchable = False,
                    clearable = False,
                ))),
                dbc.Col(labelled('Plot:', dcc.Dropdown(
                    options = _options(stats.PSA_PROJECT_PLOTS['multiple']),
                    value = next(iter(stats.PSA_PROJECT_PLOTS['multiple'])),
                    id = _psa_project_option_id('plot'),
                    searchable = False,
                    clearable = False,
                ))),
            ]),
            html.Div(
                labelled('Configurations:', dcc.Dropdown(
                    options = [], value = [], multi = True,
                    id = _psa_project_option_id('comparators'),
                    placeholder = 'All configurations',
                )),
                id = 'psa-multiple-options',
                style = {'display': 'none'},
            ),
            html.Div(
                dbc.Row([
                    dbc.Col(labelled('Comparator:', dcc.Dropdown(
                        options = [], id = _psa_project_option_id('comparator'), clearable = False,
                    ))),
                    dbc.Col(labelled('Reference:', dcc.Dropdown(
                        options = [], id = _psa_project_option_id('reference'), clearable = False,
                    ))),
                ]),
                id = 'psa-pairwise-options',
                style = {'display': 'none'},
            ),
            html.Div(
                labelled('Variable:', dcc.Dropdown(
                    options = [], id = _psa_project_option_id('variable'), clearable = False,
                    placeholder = 'Choose a variable drawn in the PSA',
                )),
                id = 'psa-variable-options',
                style = {'display': 'none'},
            ),
        ],
        id = 'psa-project-options',
        style = {'display': 'none'},
    )

def create_psa_project_results():
    """Create the containers of the comparator views of a whole-project PSA: a table and a plot.

    Hidden in the individual view.

    Returns:
        The containers.
    """
    return html.Div(
        [
            dbc.Col(
                [
                    html.H2('PSA Comparison Table'),
                    html.Div(
                        'No whole-project PSA run',
                        id = {
                            'type': 'result-table', 'purpose': 'container',
                            'supersection': 'psa', 'section': 'tabledraw',
                            'key': 'table_psa_project', 'subindex': 0,
                        }
                    )
                ],
                width = 12
            ),
            html.Hr(),
            dbc.Col(
                [
                    html.H2('Comparison plot'),
                    dcc.Graph(
                        # Using result-table dispatch to call a custom table getter
                        id = {
                            'type': 'result-figure', 'purpose': 'container',
                            'supersection': 'psa', 'section': 'tabledraw',
                            'key': 'table_psa_project', 'subindex': 1,
                        },
                        style = {
                            'minHeight': '590px',
                            'border': '1px solid #dee2e6',
                            'borderRadius': '0.5rem',
                            'backgroundColor': 'transparent'
                        }
                    ),
                ],
                width = 12
            ),
        ],
        id = 'psa-project-results',
        style = {'display': 'none'},
    )

@dataclass
class PSAConfigurationLayoutConfiguration(registers.LayoutConfiguration):
    """Layout configuration of the PSA page: the input and result cards and the navigation.
    """
    page_type: str = PAGE_TYPE

    layout_navigation: Callable[[str], Any] = navigation.create_navigation_component
    width_navigation: int = 1
    layout_top: Callable[[], Any] = create_psa_header
    layout_results_header: Callable = results_header.create_results_header_psa

def create_psa_layout(config: PSAConfigurationLayoutConfiguration):
    """The layout of the PSA page: the editor of the PSA and its results.

    Args:
        config: The layout configuration of the page.

    Returns:
        The layout.
    """
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
                ),
                dbc.Row(
                    dcc.RadioItems(
                        options = [
                            {'label': 'Individual', 'value': 'individual'},
                            {'label': 'Multiple', 'value': 'multiple'},
                            {'label': 'Pairwise', 'value': 'pairwise'},
                        ],
                        value = 'individual',
                        inline = True,
                        inputStyle = {'margin-right': '4px', 'margin-left': '12px'},
                        id = _psa_project_option_id('view'),
                    ),
                    class_name = 'mb-2',
                ),
                create_psa_project_options(),
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
                ],
                id = 'psa-individual-results',
            ),
            create_psa_project_results(),
        ]),
        dbc.Button(
            'Cancel PSA',
            id = {'type': 'metamodel-process-cancel', 'target': 'psa_run_request'},
            class_name = 'background-callback-cancel-button background-callback-cancel-button-hidden'
        ),
        html.Progress(
            id={'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')},
            className='feedback-strip feedback-strip-progress',
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
    """Bind the callbacks which run, cancel, download and upload the PSA.

    Args:
        app: The Dash app.
    """
    @app.callback(
        Output('psa-run-differences-note', 'children'),
        Input('psa-run-scope', 'value'),
        Input('modal-psa-confirm', 'is_open'),
        State('active-project-id', 'data'),
    )
    def show_psa_run_differences_note(scope, is_open, active_project_id):
        """For a PSA of all configurations, the number of variables whose distributions or SDs differ across them"""
        if scope != 'project' or not is_open or active_project_id is None:
            return None
        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        lproj = provider.get_lightweight_project(active_project_id)
        var_uids = list(dict.fromkeys(uid for lmm in lproj.metamodels for uid in lmm.variables.values()))
        variables = {x.id: x for x in provider.variable_provider.get_full_lightweight_variable(var_uids)}
        n = count_variables_with_different_distributions_or_sds(lproj, variables)
        if not n:
            return None
        return f'{n} variable{"s have" if n != 1 else " has"} different distributions or SDs across configurations'

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
                                            app.project_provider.upsert_component(proj)
                                    except ValueError as e:
                                        logger.exception(
                                            'Exception whilst uploading PSA results.', exc_info = True
                                        )
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
            logger.exception(
                'Exception whilst uploading PSA results.', exc_info = True
            )
            return rval
        
        if result_df is None:
            # Should never be reached
            logger.exception(
                'No results in uploaded PSA archive, but initial results file check passed.'
            )
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

        # Results from before a statistic was added do not include it: draw an empty plot rather than fail
        missing_statistics = [
            v for v in plot_kwargs.values()
            if isinstance(v, str) and v in psa.PSA_STATISTIC_LABELS and v not in psa_raw_data.columns
        ]
        if missing_statistics:
            if full_draw:
                rval['plot_header']['children'] = plot_funcs['controls'](plot_header['ids']['subindex'])
            fig = plot_funcs['draw'](None, **plot_kwargs)
            fig.update_layout(
                title_text = 'Not in these PSA results - re-run the PSA to include '
                    + ', '.join(psa.PSA_STATISTIC_LABELS[s] for s in missing_statistics)
            )
            rval['plot']['figures'] = fig
            return rval

        if full_draw:
            rval['plot_header']['children'] = plot_funcs['controls'](plot_header['ids']['subindex'])
            
            rval['plot']['figures'] = plot_funcs['draw'](psa_raw_data, **plot_kwargs)
    
        else:
            fig_patch = plot_funcs['update'](psa_raw_data, **plot_kwargs)
            # Clear any message that the previous statistic was missing from the results
            fig_patch['layout']['title']['text'] = ''
            rval['plot']['figures'] = fig_patch
    
        return rval

    @app.callback(
        Output('trigger-check-requests', 'data', allow_duplicate = True),
        Input('btn-action-psa-run-metamodel', 'n_clicks'),
        State('active-project-id', 'data'),
        State('psa-run-scope', 'value'),
        prevent_initial_call = True
    )
    def request_psa_run_metamodel(
        n_clicks,
        active_project_id,
        run_scope,
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate

        request = app.request_handler.add_request(
            'psa_run_project' if run_scope == 'project' else 'psa_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
        )

        return request.request_id

    @app.callback(
        output = dict(
            individual_results_style = Output('psa-individual-results', 'style'),
            project_options_style = Output('psa-project-options', 'style'),
            project_results_style = Output('psa-project-results', 'style'),
            multiple_options_style = Output('psa-multiple-options', 'style'),
            pairwise_options_style = Output('psa-pairwise-options', 'style'),
            variable_options_style = Output('psa-variable-options', 'style'),
            statistic = dict(
                options = Output(_psa_project_option_id('statistic'), 'options'),
                value = Output(_psa_project_option_id('statistic'), 'value'),
            ),
            plot = dict(
                options = Output(_psa_project_option_id('plot'), 'options'),
                value = Output(_psa_project_option_id('plot'), 'value'),
            ),
            comparators = dict(
                options = Output(_psa_project_option_id('comparators'), 'options'),
                value = Output(_psa_project_option_id('comparators'), 'value'),
            ),
            comparator = dict(
                options = Output(_psa_project_option_id('comparator'), 'options'),
                value = Output(_psa_project_option_id('comparator'), 'value'),
            ),
            reference = dict(
                options = Output(_psa_project_option_id('reference'), 'options'),
                value = Output(_psa_project_option_id('reference'), 'value'),
            ),
            variable = dict(
                options = Output(_psa_project_option_id('variable'), 'options'),
                value = Output(_psa_project_option_id('variable'), 'value'),
            ),
        ),
        inputs = dict(
            view = Input(_psa_project_option_id('view'), 'value'),
            plot_value = Input(_psa_project_option_id('plot'), 'value'),
            table_trigger = Input({
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': 'global', 'section': 'tabledraw',
                'key': 'table_psa_project', 'subindex': 0
            }, 'data'),
            active_project_id = Input('active-project-id', 'data'),
        ),
        state = dict(
            statistic = State(_psa_project_option_id('statistic'), 'value'),
            comparators = State(_psa_project_option_id('comparators'), 'value'),
            comparator = State(_psa_project_option_id('comparator'), 'value'),
            reference = State(_psa_project_option_id('reference'), 'value'),
            variable = State(_psa_project_option_id('variable'), 'value'),
        ),
    )
    def update_psa_view_options(
        view,
        plot_value,
        table_trigger,
        active_project_id,
        statistic,
        comparators,
        comparator,
        reference,
        variable,
    ):
        """Show the options and results of the PSA view, and fill the comparator and variable options from the results of the whole-project PSA."""
        rval = callback_utils.create_noupdate_return()
        # Shown components keep the display of their classes
        shown, hidden = {}, {'display': 'none'}
        is_individual = view not in stats.PSA_PROJECT_PLOTS
        rval['individual_results_style'] = shown if is_individual else hidden
        rval['project_options_style'] = hidden if is_individual else shown
        rval['project_results_style'] = hidden if is_individual else shown
        rval['multiple_options_style'] = shown if view == 'multiple' else hidden
        rval['pairwise_options_style'] = shown if view == 'pairwise' else hidden
        if is_individual:
            rval['variable_options_style'] = hidden
            return rval

        plots = stats.PSA_PROJECT_PLOTS[view]
        rval['plot']['options'] = _options(plots)
        if plot_value not in plots:
            plot_value = next(iter(plots))
            rval['plot']['value'] = plot_value
        rval['variable_options_style'] = shown if plot_value == 'marginal' else hidden

        labels = sensitivity.PSA_PAIRWISE_STATISTIC_LABELS if view == 'pairwise' else sensitivity.PSA_STATISTIC_LABELS
        rval['statistic']['options'] = _options(labels)
        if statistic not in labels:
            rval['statistic']['value'] = next(iter(labels))

        if active_project_id is None:
            return rval

        lproj = app.project_provider.get_lightweight_project(active_project_id)
        options, _ = app.results_provider.get_result('table_psa_project_options', lproj.table_config, True)
        if not options:
            for key in ('comparators', 'comparator', 'reference', 'variable'):
                rval[key]['options'] = []
            return rval

        mm_options = options.get('metamodels', [])
        mm_ids = [x['value'] for x in mm_options]
        var_options = options.get('variables', [])
        for key in ('comparators', 'comparator', 'reference'):
            rval[key]['options'] = mm_options
        rval['variable']['options'] = [{'label': x, 'value': x} for x in var_options]

        if not comparators or any(x not in mm_ids for x in comparators):
            rval['comparators']['value'] = [x for x in (comparators or []) if x in mm_ids] or mm_ids
        if comparator not in mm_ids:
            rval['comparator']['value'] = mm_ids[1] if len(mm_ids) > 1 else (mm_ids[0] if mm_ids else None)
        if reference not in mm_ids:
            rval['reference']['value'] = mm_ids[0] if mm_ids else None
        if variable not in var_options:
            rval['variable']['value'] = var_options[0] if var_options else None

        return rval

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
