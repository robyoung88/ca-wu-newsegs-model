"""
Functions for creating a deterministic sensitivity analysis layout
"""
from dash import dcc, html

from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components.dsa_process_components import dsa_process_components
from newsegsmodelapp.components.page_layouts import fourpane_layout
from newsegsmodelapp.components import navigation, result_group_containers
from newsegsmodelapp.newsegsbrowser.layouts import layout_registry

from newsegsmodelapp.registers import register_page_layout
from newsegsmodelframework.newsegssensitivity import optim

from newsegsmodelapp.components import  results_header
from newsegsmodelapp.components.optim_process_components import optim_process_components
from newsegsmodelframework.newsegssensitivity import common as sensitivity
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_dsa_header(**kwargs):
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

DEFAULT_LAYOUT_DSA = {
    'layout_navigation': navigation.create_navigation_component,
    'width_navigation': 1,
    'layout_top': create_dsa_header,

    'layout_results_header': results_header.create_results_header_dsa,

}

def create_dsa_layout(*args, **kwargs):
    config_dict = DEFAULT_LAYOUT_DSA.copy()
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

    dsa_config = create_dsa_configuration_editor()

    optim_config = create_optim_configuration_editor(**kwargs)

    a2_contents = [
        dsa_config,
        optim_config,
    ]

    b1_contents = [
        dbc.Container(
            [
                dbc.Row(
                    config_dict['layout_results_header'](**kwargs),
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
        #dcc.Loading([
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
            section = 'tabledraw',
            supersection = 'dsa',
            # overlay_style = {
            #     'visibility': 'visible',
            #     'filter': 'blur(2px)',
            #     'display': 'block',
            # },
            # delay_show = 200,
            # delay_hide = 200,
            # id = 'loading-results',
            # parent_className = 'drawer-loading-container',
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
                'DSA Running',
                id = {'type': 'progress-tooltip', 'page': kwargs.get('page_type', 'None')},
                target = {'type': 'progress-bar', 'page': kwargs.get('page_type', 'None')}
            ),
            
        ] + dsa_process_components(**kwargs)

    
    return fourpane_layout(
        a1_contents,
        b1_contents,
        a2_contents,
        b2_contents,
    )

@register_page_layout('dsa')
def _create_dsa_configuration_layout(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_dsa_layout(
        **layout_registry.get_dsa_layout_config(
            selected_model
        )
    )
