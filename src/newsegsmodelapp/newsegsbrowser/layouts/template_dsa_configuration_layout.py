"""
Functions for creating a deterministic sensitivity analysis layout
"""
from typing import cast

from dash import dcc, html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import STATICDATA
from newsegsmodelapp.newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsmodelapp.newsegsbrowser.components.layout import navigation
from newsegsmodelapp.newsegsbrowser.layouts.common import NULL_LAYOUT
from newsegsmodelapp.newsegsbrowser.layouts import common as clayouts
from newsegsmodelapp.newsegsbrowser import variable_dash_component as var_dc
from newsegsmodelframework.newsegssensitivity import optim
from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.newsegsbrowser.layouts.results import results_header

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
                        id = {'type': 'optim-run-option', 'page': kwargs.get('page_type', 'None'), 'key': 'optim-marginal-statistic'}
                    ),
                ]), # pyright: ignore[reportCallIssue]
                
                dbc.Row([
                    dcc.Graph(
                        id = {'type': 'plot', 'page': kwargs.get('page_type', 'None'), 'key': 'optim-marginal-statistic'},
                        style= {
                            'height': '590px',
                            'border': '1px solid #dee2e6',
                            'borderRadius': '0.5rem',
                            'backgroundColor': 'transparent'
                        }
                    )
                ]), # pyright: ignore[reportCallIssue]
                dbc.Row(
                    id = {'type': 'input-container', 'supersection': 'optim', 'section': 'optim'}
                ), # pyright: ignore[reportCallIssue]
                dcc.Store(
                    id = {'type': 'store-optim-marginal-statistic-plot', 'page': kwargs.get('page_type', 'None')},
                    data = None,
                ),
                dbc.Modal(
                    [
                        dbc.ModalHeader(dbc.ModalTitle('Start system optimisation')), # pyright: ignore[reportCallIssue]
                        dbc.ModalBody([
                            html.H3('Automatically optimise system size'),
                            html.P((
                                'This automated process can take a substantial amount of time, ' \
                                'dependent on the complexity of the model, the number of ' \
                                'parameters to be optimised, and the optimisation method. '
                                'Before running, we advise taking the following steps:' \
                            )),
                            html.P((
                                '- Check the measure you want to optimise against - ' \
                                ' discounting can have a major impact on the location of the ' \
                                ' optimal point.'
                            )),
                            html.P((
                                '- Look at the marginal values of the measure against each of the ' \
                                'parameters. If the plot does not show a "peak" within the range then ' \
                                'it is likely to move to the bound of its range. Check if that ' \
                                'bound is plausible (e.g. can 4 MW of wind generation be exported ' \
                                'from the site, and is it physically big enough?). It is preferable ' \
                                'to set the value of these parameters and remove them from ' \
                                'optimisation, as gradient methods tend not to work well at the ' \
                                'boundary.'
                            )),
                            html.P((
                                '- All optimisation methods are sensitive to the starting parameter ' \
                                'values. Check that the current value is close to the "peak" in the ' \
                                'marginal plot to avoid getting trapped in a local maximum. However, ' \
                                'in complex cases where the interaction between parameters has a ' \
                                'strong and inconsistent impact on the measure, it is not guaranteed ' \
                                'that you will find the "global" maximum over the N-dimensional ' \
                                'parameter volume.'
                            )),
                            html.P((
                                '- The optimisation method can impact how long it takes to find ' \
                                'the optimal point, if it can be found at all. The default ' \
                                '(Nelder-Mead) is good at finding the optimum, but not as robust as ' \
                                'L-BFGS-B to a "rough" function. Powell optimisation is extremely '
                                'robust and simple, but requires a lot of function evaluations.'
                            )),
                            html.H3('Optimisation method:'),
                            dcc.Dropdown(
                                options = optim.OPTIMISATION_METHODS,
                                value = optim.OPTIMISATION_METHODS[0],
                                searchable = False,
                                multi = False,
                                clearable = False,
                                id = {'type': 'optim-run-option', 'page': kwargs.get('page_type', 'None'), 'key': 'optim-method'},
                                persistence = True
                            ),
                        ]), # pyright: ignore[reportCallIssue]
                        dbc.ModalFooter([
                            dbc.Button(
                                'OK',
                                id = {'type': 'optim-run-btn', 'page': kwargs.get('page_type', 'None')},
                                n_clicks = 0
                            ), # pyright: ignore[reportCallIssue]
                            dbc.Button(
                                'Cancel',
                                id = {'type': 'modal-close-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'optim-run-confirm'},
                                className = 'ms-auto',
                                n_clicks = 0
                            ) # pyright: ignore[reportCallIssue]
                        ])
                    ],
                    id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'optim-run-confirm'},
                    is_open = False,
                    size = 'xl',
                ),
                dbc.Toast(
                    ['Optimisation unsuccessful'],
                    id = {'type': 'feedback-toast', 'page': kwargs.get('page_type', 'None'), 'key': 'optim'},
                    header = 'Optimisation exit',
                    icon = 'warning',
                    dismissable = True,
                    is_open = False,
                    duration = 5000,
                    style = {'position': 'fixed', 'top': 66, 'right': 10, 'width': 350},
                ), # pyright: ignore[reportCallIssue]
                dcc.Store(id={'type': 'trigger', 'page': kwargs.get('page_type', 'None'), 'key': 'optim-run-postprocess'}, data = []),
            ]
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
                    ), # pyright: ignore[reportCallIssue]
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
