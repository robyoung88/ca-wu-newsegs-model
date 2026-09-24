"""
Functions for creating a deterministic sensitivity analysis layout
"""
from dataclasses import asdict, dataclass
from typing import Any, Callable

from dash import dcc, html

from newsegsmodelapp import registers
from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components.dsa_process_components import dsa_process_components
from newsegsmodelapp.components.page_layouts import fourpane_layout
from newsegsmodelapp.components import navigation, result_group_containers

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.types import Page
from newsegsmodelframework.newsegssensitivity import optim

from newsegsmodelapp.components import  results_header
from newsegsmodelapp.components.optim_process_components import optim_process_components
from newsegsmodelframework.newsegssensitivity import common as sensitivity
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

PAGE_TYPE = 'dsa'

def create_dsa_header():
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
    return dbc.Col([
        html.Div([
            html.H2(
                'DSA Configuration',
                style = {'display': 'inline-flex',
                         'margin-right': '20px'}
            ),
            ],
            style = {'vertical-align': 'baseline'}
            ),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'dsa', 'section': 'dsa'}
        )
    ])

def create_optim_configuration_editor_header(**kwargs):
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
    return dbc.Col([
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
                
                dbc.Row(
                    id = {'type': 'input-container', 'supersection': 'optim', 'section': 'optim'}
                ), 
            ] + optim_process_components(**kwargs)
        )
        
    ]) 

@dataclass
class DSAConfigurationLayoutConfiguration(registers.LayoutConfiguration):
    page_type: str = PAGE_TYPE

    layout_navigation: Callable[[str], Any] = navigation.create_navigation_component
    width_navigation: int = 1
    layout_top: Callable[[], Any] = create_dsa_header
    layout_results_header: Callable = results_header.create_results_header_dsa

def create_dsa_layout(config: DSAConfigurationLayoutConfiguration):

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
                className='resize-handle resize-handle-progress',
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

dsa_configuration_page = Page(
    id = PAGE_TYPE,
    nav_label = 'Sensitivity analysis',
    nav_icon = html.I(
        className = icons.get_icon('nav-dsa-config', style_name = 'raw'),
        style = {'display': 'inline'}
    ),
    layout = create_dsa_layout,
    default_configuration = DSAConfigurationLayoutConfiguration()
)
registers.add_page(dsa_configuration_page)
