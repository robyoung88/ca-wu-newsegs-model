"""
Functions for creating a deterministic sensitivity analysis layout
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
from newsegsmodelapp.components.callbacks.action_callbacks import generate_post_action_requests
from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container

from newsegsmodelapp.components.layouts.page_layouts import fourpane_layout
from newsegsmodelapp.components import callback_utils, export, navigation

from newsegsmodelapp.dash_extension import NewsegsDash
from newsegsmodelapp.components import icons
from newsegsmodelapp.components.staleness import create_staleness_indicator
from newsegsmodelapp.types import Page
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import optim

from newsegsmodelapp.components.layouts import result_group_containers, results_header
from newsegsmodelframework.newsegssensitivity import common as sensitivity
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

from .processes.dsa_process_components import dsa_process_components
from .processes.optim_process_components import optim_process_components

PAGE_TYPE = 'dsa'

def create_dsa_header():
    """Create the header of the DSA page.

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
                                'Deterministic Sensitivity Analysis',
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
                    create_header_metamodel_input_container('dsa'),
                    class_name = 'align-items-center text-center'
                )
            )
        ],
        fluid = True
    )

def create_dsa_configuration_editor():
    """Create the editor of the DSA: the inputs of the variables, with their bounds.

    Returns:
        The editor.
    """
    return dbc.Col([
        html.Div(
            [
                html.H2(
                    'DSA Configuration',
                    style = {'display': 'inline-flex',
                            'margin-right': '20px'}
                ),
            ],
            style = {'vertical-align': 'baseline'}
        ),

        html.Div(
            id = {'type': 'input-section-header', 'supersection': 'dsa', 'section': 'dsa'},
            style = {'display': 'none'}
        ),
        dcc.Interval(
            id = {
                'type': 'input-container-hydration-interval', 
                'supersection': 'dsa', 
                'section': 'dsa'
            },
            n_intervals = 1,
            disabled = False,
            max_intervals = 1,
            interval = 50,
        ),

        html.Div(
            id = {'type': 'input-container', 'supersection': 'dsa', 'section': 'dsa'}
        )
    ])

def create_optim_configuration_editor_header(**kwargs):
    """Create the header of the optimisation editor.

    Args:
        **kwargs: Further keyword arguments.

    Returns:
        The header.
    """
    button_container_children = [
        dbc.Button(
            'Optimise',
            color = 'primary',
            id = 'btn-optim-prerun',
            title = 'Start optimisation',
            disabled = False
        )
    ]

    return dbc.Row([
        html.Div(
            html.H2('Optimisation Configuration'),
            className = 'configuration-header-title-container'
        ),
        html.Div(
            button_container_children,
            className = 'configuration-header-button-container'
        )
    ],
    class_name = 'configuration-header'
    )

def create_optim_configuration_editor(**kwargs):
    """Create the editor of the optimisation: the variables to vary, with their bounds.

    Args:
        **kwargs: Further keyword arguments.

    Returns:
        The editor.
    """
    return dbc.Col([
        *create_staleness_indicator(kwargs.get('page_type', PAGE_TYPE), 'optim'),
        create_optim_configuration_editor_header(**kwargs),
        dcc.Loading(
            [
                dbc.Row([
                    html.H4('Optimisation statistic:'),
                    dcc.Dropdown(
                        options = [{'value': x, 'label': optim.OPTIM_TARGET_STATISTIC_LABELS[x]} for x in optim.OPTIM_TARGET_STATISTICS],
                        value = optim.OPTIM_TARGET_STATISTICS[0],
                        searchable = False,
                        multi = False,
                        clearable = False,
                        id = {
                            'type': 'result-table-option', 'purpose': 'statistic',
                            'supersection': 'optim', 'section': 'tabledraw',
                            'key': 'table_optim_metamodel', 'subindex': 0
                        },
                    ),
                ]),
                
                result_group_containers.create_results_container(
                    [
                        dbc.Row([
                            dcc.Graph(
                                id = {
                                    'type': 'result-figure', 'purpose': 'container',
                                    'supersection': 'optim', 'section': 'tabledraw',
                                    'key': 'table_optim_metamodel', 'subindex': 0
                                },
                                style= {
                                    'height': '590px',
                                    'border': '1px solid #dee2e6',
                                    'borderRadius': '0.5rem',
                                    'backgroundColor': 'transparent'
                                }
                            )
                        ]), 
                        html.Div(
                            id = {
                                'type': 'result-table', 'purpose': 'container',
                                'supersection': 'optim', 'section': 'tabledraw',
                                'key': 'table_postopt_metamodel', 'subindex': 0
                            }
                        ), 
                    ],
                    section = 'tabledraw',
                    supersection = 'optim'
                ),

                html.Div(
                    id = {'type': 'input-section-header', 'supersection': 'optim', 'section': 'optim'},
                    style = {'display': 'none'}
                ),

                dcc.Interval(
                    id = {
                        'type': 'input-container-hydration-interval', 
                        'supersection': 'optim', 
                        'section': 'optim'
                    },
                    n_intervals = 1,
                    disabled = False,
                    max_intervals = 1,
                    interval = 50,
                ),
                
                
                dbc.Row(
                    id = {'type': 'input-container', 'supersection': 'optim', 'section': 'optim'}
                ),
            ] + optim_process_components(**kwargs),
            delay_show = 300, 
        )
        
    ]) 

@dataclass
class DSAConfigurationLayoutConfiguration(registers.LayoutConfiguration):
    """Layout configuration of the DSA page: the input and result cards and the navigation.
    """
    page_type: str = PAGE_TYPE

    layout_navigation: Callable[[str], Any] = navigation.create_navigation_component
    width_navigation: int = 1
    layout_top: Callable[[], Any] = create_dsa_header
    layout_results_header: Callable = results_header.create_results_header_dsa

def create_dsa_layout(config: DSAConfigurationLayoutConfiguration):

    """The layout of the DSA page: the editors of the DSA and the optimisation, and their results.

    Args:
        config: The layout configuration of the page.

    Returns:
        The layout.
    """
    a1_contents = [
        dbc.Row([
            dbc.Col(
                config.layout_navigation(config.model_type),
                width = 'auto',
            ),
            dbc.Col(
                config.layout_top(),
                class_name = 'page-top'
            ),
        ],
        class_name = 'align-items-start'
        )
    ]

    dsa_config = create_dsa_configuration_editor()

    optim_config = create_optim_configuration_editor(**asdict(config))

    a2_contents = [
        dsa_config,
        optim_config,
    ]

    b1_contents = [
        dbc.Container(
            [
                dbc.Row(
                    config.layout_results_header(**asdict(config)),
                ),
                
                dbc.Row([
                    dcc.Dropdown(
                        options = [
                            {'label': v, 'value': k} for k, v in sensitivity.DSA_STATISTIC_LABELS.items()
                        ],
                        value = list(sensitivity.DSA_STATISTIC_LABELS.keys())[0],
                        id = {
                            'type': 'result-table-option', 'purpose': 'statistic',
                            'supersection': 'dsa', 'section': 'tabledraw',
                            'key': 'table_dsa_metamodel', 'subindex': 0
                        },
                        searchable = False,
                        clearable = False,
                    )
                ]),
            ]    
        )
    ]

    b2_contents = [
        result_group_containers.create_results_container([
            html.Div([
                    dbc.Col(
                        [
                            html.H2("DSA Results Table"),
                            html.Div(
                                'No DSA Run',
                                id = {
                                    'type': 'result-table', 'purpose': 'container',
                                    'supersection': 'dsa', 'section': 'tabledraw',
                                    'key': 'table_dsa_metamodel', 'subindex': 0,
                                }
                            )
                        ],
                        width = 12
                    ),
                    html.Hr(),
                    dbc.Col(
                        [
                            html.H2("Tornado plot"),
                            html.Div(
                                dcc.Graph(
                                    # Using result-table dispatch to call a custom table getter
                                    id = {
                                        'type': 'result-figure', 'purpose': 'container',
                                        'supersection': 'dsa', 'section': 'tabledraw',
                                        'key': 'table_dsa_metamodel', 'subindex': 1,
                                    },
                                    style= {
                                        'height': '590px',
                                        'border': '1px solid #dee2e6',
                                        'borderRadius': '0.5rem',
                                        'backgroundColor': 'transparent'
                                    }
                                ),
                                style={'display':'block', 'height': '600px'},
                                id = {'type': 'plot-container', 'page': config.page_type, 'key': 'dsa-tornado-plot'},
                            )
                        ],
                        width = 12
                    ),
                    dcc.Store(id={'type': 'trigger', 'page': config.page_type, 'key': 'dsa-run-postprocess'}, data = []),
                    dcc.Store(id={'type': 'result-statistics', 'supersection': 'dsa-results', 'key': 'res-dsa-table'}, data = []),
                ],
                
                className = 'drawer-content',
                ),
            ],
            section = 'tabledraw',
            supersection = 'dsa',
            ),
            dbc.Button(
                'Cancel DSA',
                id = {'type': 'metamodel-process-cancel', 'target': 'dsa_run_request'},
                class_name = 'background-callback-cancel-button background-callback-cancel-button-hidden'
            ), 
            html.Progress(
                id={'type': 'progress-bar', 'page': config.page_type},
                className='feedback-strip feedback-strip-progress',
                style = {'display': 'none'}
            ),
            dbc.Tooltip(
                'DSA Running',
                id = {'type': 'progress-tooltip', 'page': config.page_type},
                target = {'type': 'progress-bar', 'page': config.page_type}
            ),
            
        ] + dsa_process_components(**asdict(config))

    
    return fourpane_layout(
        a1_contents,
        b1_contents,
        a2_contents,
        b2_contents,
    )

def add_dsa_run_callbacks(app: NewsegsDash):
    """Bind the callbacks which run, cancel, download and upload the DSA.

    Args:
        app: The Dash app.
    """
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
        },
        prevent_initial_call = True,
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
                        contents_option = opts.get('contents-option', 'result'),
                        format_option = opts.get('format-option', 'csv'),
                        result_level = 'metamodel',
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

            postaction_trigger = dict(
                data = Output({
                    'type': 'postaction-trigger', 'purpose': 'trigger',
                    'supersection': 'global', 'section': 'run',
                    'key': 'dsa_run_metamodel', 'subindex': 0
                }, 'data', allow_duplicate = True)
            ),

            check_requests_trigger = dict(
                data = Output('trigger-check-requests', 'data', allow_duplicate = True),
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
                                            app.project_provider.upsert_component(proj)
                                            
                                    except ValueError as e:
                                        logger.exception(
                                            'Exception whilst uploading DSA results.', exc_info = True
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
                'Exception whilst uploading DSA results.', exc_info = True
            )
            raise PreventUpdate
        
        if result_df is None:
            # Should never be reached
            logger.exception(
                'No results in uploaded DSA archive, but initial results file check passed.'
            )
            return rval
        
        # Set the result_df as appropriate for a dsa result and trigger post-processing
        result_df = result_df.set_index(['variable', 'bound'])
        mm = proj.get_focussed_metamodel()
        # Will allow a manual revision increment here as no need to disrupt the upstream project revision number.
        mm.table_config.revision += 1
        mark_stale = mm_new is None
        app.results_provider.upsert_result(
            'dsa_single_metamodel', mm.table_config, result_df, mark_stale = mark_stale
        )

        # Spoof a dsa run request to register requests for post dsa run procedures
        rr_generator = registers.RUN_REQUEST_REGISTER['dsa_run_metamodel']
        request = rr_generator(active_project_id, app.project_provider)
        request.run_id = -random.randrange(1, 10000)

        new_request_ids, request_keys = generate_post_action_requests(
            request,
            app.request_handler,
            app.project_provider
        )

        rval['postaction_trigger']['data'] = [json.dumps(request.as_dict())]
        if new_request_ids:
            rval['check_requests_trigger']['data'] = new_request_ids

        return rval

    @app.callback(
        Output('trigger-check-requests', 'data', allow_duplicate = True),
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

        request = app.request_handler.add_request(
            'dsa_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
        )

        return request.request_id

def add_optim_run_callbacks(app: NewsegsDash):

    # Pre-run modal control
    """Bind the callbacks which run and cancel the optimisation.

    Args:
        app: The Dash app.
    """
    @app.callback(
        output = {
            'modal': {
                'is_open': Output('modal-optim-confirm','is_open')
            }
        },
        inputs = {
            'optim_run_button': {
                'n_clicks':  Input('btn-action-optim-run-metamodel', 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input('btn-optim-confirm-abort', 'n_clicks')
            },
            'optim_prerun_button': {
                'n_clicks': Input('btn-optim-prerun', 'n_clicks'),
            }
        },
        prevent_initial_call = True
    )
    def confirm_optim_run(
        optim_run_button,
        modal_close_button,
        optim_prerun_button,
    ):
        
        trig_id = ctx.triggered_id
        if trig_id is None:
            raise PreventUpdate
        
        if trig_id == 'btn-optim-prerun':
            return dict(modal = dict(is_open = True))
        else:
            return dict(modal = dict(is_open = False))

    @app.callback(
        output = dict(
            trigger = Output('trigger-check-requests', 'data', allow_duplicate = True),
        ),
        inputs = dict(
            n_clicks = Input('btn-action-optim-run-metamodel', 'n_clicks'),
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
            statistic = State(
                {
                    'type': 'result-table-option', 'purpose': 'statistic',
                    'supersection': 'optim', 'section': 'tabledraw',
                    'key': 'table_optim_metamodel', 'subindex': ALL # If we don't include the wildcard, we get complaints navigating away from the page.
                },
                'value'
            ),
            optim_method = State(
                {
                    'type': 'result-table-option', 'purpose': 'optim-method',
                    'supersection': 'optim', 'section': 'run',
                    'key': 'optim_run_metamodel', 'subindex': 0
                },
                'value'
            )
        ),
        prevent_initial_call = True
    )
    def request_optim_run_metamodel(
        n_clicks,
        active_project_id,
        **kwargs
    ):
        click = callback_utils.get_triggered_value()
        if not click:
            raise PreventUpdate
        stat = kwargs.get('statistic')
        if stat is not None and not isinstance(stat, str) and len(stat):
            kwargs['statistic'] = stat[0]

        request = app.request_handler.add_request(
            'optim_run_metamodel',
            active_project_id,
            app.project_provider,
            'run',
            kwargs
        )

        return dict(trigger = request.request_id)

    # Marginal statistic plot draw
    @app.callback(
        output = dict(
            trigger = Output('trigger-check-requests', 'data', allow_duplicate = True),
        ),
        inputs = dict(
            n_clicks = Input(
                {
                    'type': 'btn-action-optim-create-marginalplot', 'varid': ALL
                },
                'n_clicks'
            ),
        ),
        state = dict(
            active_project_id = State('active-project-id', 'data'),
            statistic = State(
                {
                    'type': 'result-table-option', 'purpose': 'statistic',
                    'supersection': 'optim', 'section': 'tabledraw',
                    'key': 'table_optim_metamodel', 'subindex': ALL # If we don't include the wildcard, we get complaints navigating away from the page.
                },
                'value'
            ),
        ),
        prevent_initial_call = True,
    )
    def request_marginal_plot(
        n_clicks,
        active_project_id,
        statistic,
    ):
        triggered_id = ctx.triggered_id
        if triggered_id is None or statistic is None:
            raise PreventUpdate

        if statistic is not None and not isinstance(statistic, str) and len(statistic):
            statistic = statistic[0]
        
        if not isinstance(triggered_id, str) and triggered_id.get('type') == 'btn-action-optim-create-marginalplot':
            clicks = callback_utils.get_triggered_value()
            if not clicks:
                raise PreventUpdate
        if isinstance(triggered_id, str):
            raise TypeError('Can only trigger with an object specifing the variable to plot')

        request = app.request_handler.add_request(
            'table_optim_metamodel', # TODO: Improve this key
            active_project_id,
            app.project_provider,
            'tabledraw',
            dict(
                metamodel_id = app.project_provider.get_focussed_metamodel_id(active_project_id),
                varid = triggered_id.get('varid'),
                statistic = statistic,
            )
        )

        return dict(trigger = request.request_id)

    @app.callback(
        Output('active-project-id', 'data'),
        Input(
            {
                'type': 'postaction-trigger', 'purpose': 'trigger',
                'supersection': 'global', 'section': 'run',
                'key': 'optim_run_metamodel', 'subindex': 0
            },
            'data'
        ),
        State('active-project-id', 'data'),
        prevent_initial_call = True,
    )
    def update_project_after_optimisation(trigger, active_project_id):
        trig_id = ctx.triggered_id
        if trig_id is None:
            raise PreventUpdate
        return active_project_id

def _add_page_callbacks(app: NewsegsDash):
    add_dsa_run_callbacks(app)
    add_optim_run_callbacks(app)

dsa_configuration_page = Page(
    id = PAGE_TYPE,
    nav_label = 'Sensitivity analysis',
    nav_icon = html.I(
        className = icons.get_icon('nav-dsa-config', style_name = 'raw'),
        style = {'display': 'inline'}
    ),
    layout = create_dsa_layout, # pyright: ignore[reportArgumentType]
    default_configuration = DSAConfigurationLayoutConfiguration(),
    attach_callbacks = _add_page_callbacks
)
registers.add_page(dsa_configuration_page)
