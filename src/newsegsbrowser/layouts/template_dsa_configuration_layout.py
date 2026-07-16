"""
Functions for creating a deterministic sensitivity analysis layout
"""
from typing import cast

from dash import dcc, html
import dash_bootstrap_components as dbc

from newsegsbrowser import STATICDATA
from newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsbrowser.layouts import navigation
from newsegsbrowser.layouts.common import NULL_LAYOUT
from newsegsbrowser.layouts import common as clayouts
from newsegsbrowser import variable_dash_component as var_dc
from newsegssensitivity import opt
from newsegsvariable import variable

from newsegsbrowser.layouts.results import results_header


def create_dsa_header():
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.H1(
                    [
                        'Deterministic Sensitivity Analysis',
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
            id = {'type': 'optim-prerun-button', 'page': kwargs.get('page_type', 'None')},
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
                        options = [{'value': x, 'label': opt.OPTIM_TARGET_STATISTIC_LABELS[x]} for x in opt.OPTIM_TARGET_STATISTICS],
                        value = opt.OPTIM_TARGET_STATISTICS[0],
                        searchable = False,
                        multi = False,
                        clearable = False,
                        id = {'type': 'dropdown-opt-statistic', 'page': kwargs.get('page_type', 'None'), 'key': 'opt-marginal-statistic'}
                    ),
                ]),
                dbc.Row([
                    dcc.Graph(
                        id = {'type': 'plot', 'page': kwargs.get('page_type', 'None'), 'key': 'opt-marginal-statistic'},
                        style= {
                            'height': '590px',
                            'border': '1px solid #dee2e6',
                            'borderRadius': '0.5rem',
                            'backgroundColor': 'transparent'
                        }
                    )
                ]),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'optim', 'section': 'optim'}
                ),
                dcc.Store(
                    id = {'type': 'store-optim-marginal-statistic-plot', 'page': kwargs.get('page_type', 'None')},
                    data = None,
                )
            ]
        )
        
    ])

DEFAULT_LAYOUT_DSA = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_head': create_dsa_header,
    'width_head': 11,

    'layout_results_header': results_header.create_results_header_dsa,

}

def create_dsa_layout(*args, **kwargs):
    config_dict = DEFAULT_LAYOUT_DSA.copy()
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

    dsa_config = create_dsa_configuration_editor()

    optim_config = create_optim_configuration_editor(**kwargs)

    results_section = [
        html.Div([
            dcc.Loading([
                config_dict['layout_results_header'](**kwargs),
            
                html.Div([
                    dbc.Col(
                        [
                            html.H2("DSA Results Table"),
                            html.Div(
                                'No DSA Run',
                                id = {'type': 'result-table-container', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-results-table'},
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
                                    id = {'type': 'plot', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-tornado-plot'},
                                    style= {
                                        'height': '590px',
                                        'border': '1px solid #dee2e6',
                                        'borderRadius': '0.5rem',
                                        'backgroundColor': 'transparent'
                                    }
                                ),
                                style={'display':'block', 'height': '600px'},
                                id = {'type': 'plot-container', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-tornado-plot'},
                            )
                        ],
                        width = 12
                    ),
                    dcc.Store(id={'type': 'trigger', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-run-postprocess'}, data = []),
                    dcc.Store(id={'type': 'result-statistics', 'supersection': 'dsa-results', 'key': 'res-dsa-table'}, data = []),
                ],
                
                className = 'drawer-content',
                ),
            ],
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
                'Cancel DSA',
                id = {'type': 'metamodel-process-cancel', 'target': 'dsa_run_request'},
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
                    dsa_config
                ),
                html.Hr(),
                dbc.Row(
                    optim_config
                ),
                html.Hr()
            ] 
            + results_section
            + clayouts.user_action_components()
            + clayouts.model_run_components(**kwargs)
            + clayouts.finance_run_components(**kwargs)
            + clayouts.metamodel_process_components()
            + clayouts.dsa_process_components(**kwargs)
            + background_callback_error_handler_components()
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
