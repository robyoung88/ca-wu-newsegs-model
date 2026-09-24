"""
Functions for creating a probabilistic sensitivity analysis layout
"""

from dataclasses import asdict, dataclass
from typing import Any, Callable

from dash import dcc, html

from newsegsmodelapp import registers
from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components.page_layouts import fourpane_layout
from newsegsmodelapp.components import navigation, result_group_containers
from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.components import results_header
from newsegsmodelapp.components.psa_process_components import psa_process_components
from newsegsmodelapp.types import Page
from newsegsmodelframework.newsegssensitivity import psa
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

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

psa_configuration_page = Page(
    id = PAGE_TYPE,
    nav_label = 'Probabilistic analysis',
    nav_icon = html.I(
        className = icons.get_icon('nav-psa-config', style_name = 'raw'),
        style = {'display': 'inline'}
    ),
    layout = create_psa_layout,
    default_configuration = PSAConfigurationLayoutConfiguration()
)
registers.add_page(psa_configuration_page)
