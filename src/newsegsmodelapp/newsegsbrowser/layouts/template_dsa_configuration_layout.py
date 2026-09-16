"""
Functions for creating a deterministic sensitivity analysis layout
"""
from typing import cast

from dash import dcc, html
import dash_bootstrap_components as dbc

from newsegsmodelapp.components.dsa_process_components import dsa_process_components
from newsegsmodelapp.components.post_page_load import create_post_page_load_components
from newsegsmodelapp.newsegsbrowser import STATICDATA
from newsegsmodelapp.newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsmodelapp.newsegsbrowser.components.layout import navigation
from newsegsmodelapp.newsegsbrowser.layouts.common import NULL_LAYOUT
from newsegsmodelapp.newsegsbrowser.layouts import common as clayouts, layout_registry

from newsegsmodelapp.registers import register_page_layout
from newsegsmodelframework.newsegssensitivity import optim

from newsegsmodelapp.components import  results_header
from newsegsmodelapp.components.optim_process_components import optim_process_components
from newsegsmodelframework.newsegssensitivity import common as sensitivity

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
            ) # pyright: ignore[reportCallIssue]
        ]),
        dbc.Row([
            dbc.Col([
                html.H2(
                    [
                        html.Span('Configuration: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'configuration-name'})
                    ]
                )
            ]) # pyright: ignore[reportCallIssue]
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
    ]) # pyright: ignore[reportCallIssue]

def create_optim_configuration_editor_header(**kwargs):
    button_container_children = [
        dbc.Button(
            'Optimise',
            color = 'primary',
            id = {'type': 'optim-prerun-btn', 'page': kwargs.get('page_type', 'None')},
            title = 'Start optimisation',
            disabled = False
        ) # pyright: ignore[reportCallIssue]
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
    ) # pyright: ignore[reportCallIssue]

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
                ]), # pyright: ignore[reportCallIssue]
                
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
                ]), # pyright: ignore[reportCallIssue]
                html.Div(
                    id = {
                        'type': 'result-table', 'purpose': 'container',
                        'supersection': 'optim', 'section': 'tabledraw',
                        'key': 'table_postopt_metamodel', 'subindex': 0
                    }
                ), # pyright: ignore[reportCallIssue]
                dbc.Row(
                    id = {'type': 'input-container', 'supersection': 'optim', 'section': 'optim'}
                ), # pyright: ignore[reportCallIssue]
            ] + optim_process_components(**kwargs)
        )
        
    ]) # pyright: ignore[reportCallIssue]

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
        ), # pyright: ignore[reportCallIssue]
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        ) # pyright: ignore[reportCallIssue]
    ])

    dsa_config = create_dsa_configuration_editor()

    optim_config = create_optim_configuration_editor(**kwargs)

    results_section = [
        html.Div([
            dcc.Loading([
                config_dict['layout_results_header'](**kwargs),
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
                ]), # pyright: ignore[reportCallIssue]
            
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
                    ), # pyright: ignore[reportCallIssue]
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
                                id = {'type': 'plot-container', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-tornado-plot'},
                            )
                        ],
                        width = 12
                    ), # pyright: ignore[reportCallIssue]
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
            ), # pyright: ignore[reportCallIssue]
            html.Progress(
                id={'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')},
                className='resize-handle resize-handle-progress',
                style = {'display': 'none'}
            ),
            dbc.Tooltip(
                'DSA Running',
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
                    dsa_config
                ), # pyright: ignore[reportCallIssue]
                html.Hr(),
                dbc.Row(
                    optim_config
                ), # pyright: ignore[reportCallIssue]
                html.Hr()
            ] 
            + results_section
            + clayouts.user_action_components()
            + clayouts.model_run_components(**kwargs)
            + clayouts.finance_run_components(**kwargs)
            + clayouts.metamodel_process_components()
            + dsa_process_components(**kwargs)
            + background_callback_error_handler_components()
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
    )

@register_page_layout('dsa')
def _create_dsa_configuration_layout(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_dsa_layout(
        **layout_registry.get_dsa_layout_config(
            selected_model
        )
    )
