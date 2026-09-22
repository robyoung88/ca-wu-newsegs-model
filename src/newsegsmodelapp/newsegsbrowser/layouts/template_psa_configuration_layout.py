"""
Functions for creating a probabilistic sensitivity analysis layout
"""

from dash import dcc, html
import dash_daq as daq

from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components.page_layouts import fourpane_layout
from newsegsmodelapp.components.post_page_load import create_post_page_load_components
from newsegsmodelapp.components import navigation, result_group_containers
from newsegsmodelapp.newsegsbrowser.layouts import common as clayouts, layout_registry
from newsegsmodelapp.components import results_header
from newsegsmodelapp.components.psa_process_components import psa_process_components
from newsegsmodelapp.registers import register_page_layout
from newsegsmodelframework.newsegssensitivity import psa
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

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
    ]) # pyright: ignore[reportCallIssue]

DEFAULT_LAYOUT_PSA = {
    'layout_navigation': navigation.create_navigation_component,
    'width_navigation': 1,
    'layout_top': create_psa_header,
    'width_head': 11,

    'layout_results_header': results_header.create_results_header_psa,

}

def create_psa_layout(*args, **kwargs):
    config_dict = DEFAULT_LAYOUT_PSA.copy()
    config_dict.update(kwargs)

    a1_contents = [
        dbc.Row([
            dbc.Col(
                config_dict['layout_navigation'](config_dict.get('selected_model')),
                width = 'auto',
            ),
            dbc.Col(
                config_dict['layout_top'](**kwargs),
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
                    config_dict['layout_results_header'](**kwargs)
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

    results_section = [
        html.Div([
            dcc.Loading(([
                config_dict['layout_results_header'](**kwargs),
            
                html.Div([
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
                                # id = {
                                #     'type': 'result-table-container', 
                                #     'page': kwargs.get('page_type', 'None'), 
                                #     'key': 'psa-results-table'
                                # },
                            )
                        ],
                        width = 12
                    ), # pyright: ignore[reportCallIssue]
                    html.Hr(),
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
                                    #id = {'type': 'plot', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-primary-plot'},
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
                    ), # pyright: ignore[reportCallIssue]
                    dcc.Store(id={'type': 'trigger', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-run-postprocess'}, data = []),
                    dcc.Store(id={'type': 'result-statistics', 'supersection': 'psa-results', 'key': 'res-psa-table'}, data = []),
                ],
                
                className = 'drawer-content',
                ),
            ]
            + psa_process_components(**kwargs)
            ),
            overlay_style = {
                'visibility': 'visible',
                'filter': 'blur(2px)',
                'display': 'block',
            },
            delay_show = 200,
            delay_hide = 200,
            id = 'loading-results',
            parent_className = 'drawer-loading-container',
            ),

            dbc.Button(
                'Cancel PSA',
                id = {'type': 'metamodel-process-cancel', 'target': 'psa_run_request'},
                class_name = 'background-callback-cancel-button background-callback-cancel-button-hidden'
            ), # pyright: ignore[reportCallIssue]
            html.Progress(
                id={'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')},
                className='resize-handle resize-handle-progress',
                style = {'display': 'none'}
            ),
            dbc.Tooltip(
                'PSA Running',
                id = {'type': 'progress-tooltip', 'page': kwargs.get('page_type', 'None')},
                target = {'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')}
            ), # pyright: ignore[reportCallIssue]

        ],
        className = 'drawer-container',

        ),

        html.Div(
            id = {'type':'post-drawer-attach', 'page': kwargs.get('page_type', 'None')},
            style = {'display': 'none'}
        ),
    ]

    return dbc.Container(
        html.Div(
            ([
                header,
                html.Hr(),
                dbc.Row(
                    psa_config
                ), # pyright: ignore[reportCallIssue]
                html.Hr()
            ] 
            + results_section
            + clayouts.user_action_components()
            
            + create_post_page_load_components(
                kwargs.get('selected_model'),
                kwargs.get('page_type')
                )
            ),
            
            
            id = 'main-content-pane',
            className = 'main-content-pane',
        ),
        fluid = True,
        id = 'app-layout-wrapper',
        class_name = 'app-layout-wrapper',
    ) # pyright: ignore[reportCallIssue]

@register_page_layout('psa')
def _create_psa_configuration_layout(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_psa_layout(
        **layout_registry.get_psa_layout_config(
            selected_model
        )
    )
