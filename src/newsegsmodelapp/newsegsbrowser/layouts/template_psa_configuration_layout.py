"""
Functions for creating a probabilistic sensitivity analysis layout
"""

from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsmodelapp.components.post_page_load import create_post_page_load_components
from newsegsmodelapp.newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsmodelapp.newsegsbrowser.components.layout import navigation
from newsegsmodelapp.newsegsbrowser.layouts import common as clayouts, layout_registry
from newsegsmodelapp.newsegsbrowser.layouts.results import results_header
from newsegsmodelapp.registers import register_page_layout
from newsegsmodelframework.newsegssensitivity import psa

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
            ) # pyright: ignore[reportCallIssue]
        ]), # pyright: ignore[reportCallIssue]
        dbc.Row([
            dbc.Col([
                html.H2(
                    [
                        html.Span('Configuration: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'configuration-name'})
                    ]
                )
            ]) # pyright: ignore[reportCallIssue]
        ]) # pyright: ignore[reportCallIssue]
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
                        dbc.InputGroupText('N'), # pyright: ignore[reportCallIssue]
                        dbc.Input(
                            id = {'type': 'numeric-input', 'target': 'psa-settings', 'key': 'samples'},
                            placeholder = 'N',
                            value = 1000,
                            min = 0,
                            max = 10000,
                            step = 1
                        ) # pyright: ignore[reportCallIssue]
                    ]) # pyright: ignore[reportCallIssue]
                ],
                className = 'input-settings'
                ),
                html.Div([
                    html.H4('Random Seed:'),
                    dbc.InputGroup([
                        dbc.InputGroupText('Seed'), # pyright: ignore[reportCallIssue]
                        dbc.Input(
                            id = {'type': 'numeric-input', 'target': 'psa-settings', 'key': 'seed'},
                            placeholder = 'seed',
                            value = None,
                            className = 'input-numeric'
                        ) # pyright: ignore[reportCallIssue]
                    ]) # pyright: ignore[reportCallIssue]
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
    ]) # pyright: ignore[reportCallIssue]

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
        ), # pyright: ignore[reportCallIssue]
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        ) # pyright: ignore[reportCallIssue]
    ]) # pyright: ignore[reportCallIssue]

    psa_config = create_psa_configuration_editor()

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
                                id = {'type': 'result-table-container', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-results-table'},
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
                                    id = {'type': 'psa-graph-selection-dropdown', 'page': kwargs.get('page-type', 'None'), 'key': 'psa-primary-plot'},
                                    searchable = False,
                                    clearable = False,
                                )
                            ]),
                            html.Div(
                                html.H2(""),
                                id = {'type': 'plot-header-container', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-primary-plot'}
                            ),
                            
                            html.Div(
                                dcc.Graph(
                                    id = {'type': 'plot', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-primary-plot'},
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
            + clayouts.model_run_components(**kwargs)
            + clayouts.finance_run_components(**kwargs)
            
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
