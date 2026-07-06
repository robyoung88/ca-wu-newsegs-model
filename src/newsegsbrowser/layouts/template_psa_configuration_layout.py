"""
Functions for creating a probabilistic sensitivity analysis layout
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsbrowser.layouts import navigation
from newsegsbrowser.layouts import common as clayouts
from newsegsbrowser.layouts.results import results_header

def create_psa_header():
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.H1(
                    [
                        'Probabilistic Sensitivity Analysis',
                        html.Br(),
                        html.Span('Site: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'site-name'}),
                    ]
                )
            )
        ]),
        dbc.Row([
            dbc.Col([
                html.H2(
                    [
                        html.Span('Configuration: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'configuration-name'})
                    ]
                )
            ])
        ])
    ])

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
            [
                html.P(
                    html.H3(
                        'PSA Settings'
                    )
                ),
                html.Div([
                    html.H4('Number of samples:'),
                    dbc.InputGroup([
                        dbc.InputGroupText('N'),
                        dbc.Input(
                            id = {'type': 'numeric-input', 'target': 'psa-settings', 'key': 'samples'},
                            placeholder = 'N',
                            value = 1000,
                            min = 0,
                            max = 10000,
                            step = 1
                        )
                    ])
                ],
                className = 'input-settings'
                ),
                html.Div([
                    html.H4('Random Seed:'),
                    dbc.InputGroup([
                        dbc.InputGroupText('Seed'),
                        dbc.Input(
                            id = {'type': 'numeric-input', 'target': 'psa-settings', 'key': 'seed'},
                            placeholder = 'seed',
                            value = None,
                            className = 'input-numeric'
                        )
                    ])
                ],
                className = 'input-settings'
                ),
                html.Div([
                    html.H4('Keep drawn parameters:'),
                    daq.ToggleSwitch(
                        id = {'type': 'toggle-input', 'target': 'psa-settings', 'key': 'return_draws'},
                        value = False,
                        size = 36,
                        className = 'input-toggle',
                    )
                ],
                className = 'input-settings'
                )
                
            ]
        ),
        html.Hr(),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'psa', 'section': 'psa'}
        )
    ])

DEFAULT_LAYOUT_PSA = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_head': create_psa_header,
    'width_head': 11,

    'layout_results_header': results_header.create_results_header_psa,

}

def create_psa_layout(*args, **kwargs):
    config_dict = DEFAULT_LAYOUT_PSA.copy()
    config_dict.update(kwargs)

    header = dbc.Row([
        dbc.Col(
            html.Div(
                config_dict['layout_navigation'](config_dict.get('selected_model'))
            ),
            class_name = 'newsegs-navbar-vertical collapsed',
            width = config_dict['width_navigation'],
        ),
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        )
    ])

    psa_config = create_psa_configuration_editor()

    results_section = [
        html.Div([
            dcc.Loading(([
                config_dict['layout_results_header'](),
            
                html.Div([
                    dbc.Col(
                        [
                            html.H2("PSA Results Table"),
                            html.Div(
                                'No PSA Run',
                                id = {'type': 'result-table-container', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-results-table'},
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
                                    id = {'type': 'plot', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-tornado-plot'},
                                    style= {
                                        'height': '590px',
                                        'border': '1px solid #dee2e6',
                                        'borderRadius': '0.5rem',
                                        'backgroundColor': 'transparent'
                                    }
                                ),
                                style={'display':'block', 'height': '600px'},
                                id = {'type': 'plot-container', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-tornado-plot'},
                            )
                        ],
                        width = 12
                    ),
                    dcc.Store(id={'type': 'trigger', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-run-postprocess'}, data = []),
                    dcc.Store(id={'type': 'result-statistics', 'supersection': 'psa-results', 'key': 'res-psa-table'}, data = []),
                ],
                
                className = 'drawer-content',
                ),
            ]
            + clayouts.metamodel_process_components()
            + clayouts.psa_process_components(**kwargs)
            + background_callback_error_handler_components()
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
                id = {'type': 'metamodel-process-cancel', 'target': 'psa-run-request'},
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
                ),
                html.Hr()
            ] 
            + results_section
            + clayouts.user_action_components()
            + clayouts.model_run_components(**kwargs)
            + clayouts.finance_run_components(**kwargs)
            
            + clayouts.post_page_load_components(
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
    )