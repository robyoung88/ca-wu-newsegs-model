from dash import dcc, html
import dash_daq as daq

from newsegsmodelapp.components.configuration_selector import create_header_metamodel_input_container
from newsegsmodelapp.components import icons
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_results_header(page_type, **kwargs):
    """
    HTML separating the results and providing controls for setting result format per annum or
    to horizon
    """
    return html.Div(
        [
            html.Div(
                id={'type': 'resize-handle', 'page': page_type}, 
                className='resize-handle resize-handle-ok'
            ),
            dbc.Tooltip(
                'Results up-to-date',
                id = {'type': 'result-tooltip', 'page': page_type},
                target = {'type': 'resize-handle', 'page': page_type}
            ), 

            html.Div(
                dbc.Container([
                    dbc.Row([
                        html.Div(
                            html.H1(
                                [
                                    icons.get_icon('results'), 
                                    'Results',

                                    # Run single button
                                    dbc.Button(
                                        html.I(
                                            className = icons.get_icon('deterministic-run-metamodel', style_name = 'raw'),
                                            style={'display': 'inline'}
                                        ),
                                        color = 'primary',
                                        id = 'btn-action-deterministic-run-metamodel',
                                        className = 'p-2',
                                        style = {
                                            "boxSizing": "border-box",
                                            "width": "42px",
                                            "height": "42px",
                                            'margin-left': '5px',
                                            'border-radius': '50%',
                                            'display': 'inline',
                                        },
                                        title = 'Run single configuration',
                                    ), 

                                    # Run project button
                                    dbc.Button(
                                        html.I(
                                            className = icons.get_icon('deterministic-run-project', style_name = 'raw'),
                                            style={'display': 'inline'}
                                        ),
                                        color = 'primary',
                                        id = 'btn-action-deterministic-run-project',
                                        className = 'p-2',
                                        style = {
                                            "boxSizing": "border-box",
                                            "width": "42px",
                                            "height": "42px",
                                            'margin-left': '5px',
                                            'border-radius': '50%',
                                            'display': 'inline',
                                        },
                                        title = 'Run all configurations',
                                    ), 
                                ],
                            ),
                            className = 'results-title-block'
                        ),

                        create_header_metamodel_input_container('configurations'),
                        
                        html.Div([
                            dbc.Button(
                                html.I(
                                    className = icons.get_icon('show-graph', style_name = 'raw'),
                                    style = {'display': 'inline'}
                                ),
                                color = 'primary',
                                id = 'btn-show-timeseries',
                                outline = True,
                                style = {'margin-right': '10px'}
                            ), 

                            html.H5("Per year", style={'display': 'inline-block', 'verticalAlign': 'middle'}),
                            daq.ToggleSwitch(style={'display': 'inline-block',
                                                    'verticalAlign': 'middle',
                                                    'padding': "10px"},
                                            id={'type': 'annual-horizon-toggle', 'page': page_type},),
                            html.H5('To horizon',style={'display': 'inline-block', 'verticalAlign': 'middle'})
                        ],
                        id = 'annual-horizon-toggle-container',
                        className = 'annual-horizon-toggle-hdrcontainer'

                        ),
                    ]),
                    dbc.Row(
                        [
                            dcc.Loading(
                                dcc.Graph(
                                    id = 'graph-timeseries',
                                    style = {
                                        'height': '300px',
                                    }
                                ),
                                delay_show = 300,
                            ),
                            
                            
                        ],
                        id = 'timeseries-graph-container',
                        style = {
                            'display': 'none'
                            },
                    ), 
                    dcc.Store({
                        'type': 'postaction-trigger', 'purpose': 'manualtrigger',
                        'supersection': 'global', 'section': 'tabledraw',
                        'key': 'timeseriesupdate', 'subindex': 0
                    }, data = 0),
                    # Id of the model whose results are drawn in graph-timeseries
                    dcc.Store(id = 'timeseries-rendered-model-id'),
                    # x-axis range requested by clicking a date in a result grid
                    dcc.Store(id = 'timeseries-zoom-request'),
                ]), 
            className = 'drawer-title'
            ),
        ],
    className = 'drawer-header'
    )

def create_results_header_dsa(**kwargs):
    button_container_children = [
        dbc.Button(
            'Run DSA',
            color = 'primary',
            id = 'btn-dsa-prerun',
            title = 'Start DSA run',
            disabled = False,
        ), 
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color = 'secondary',
            id = 'btn-dsa-result-predownload',
            outline = True,
            title = 'Download DSA results',
        ), 
        dcc.Upload(
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-upload', style_name = 'raw'),
                    style = {'display': 'inline'}       
                ),
                color = 'secondary',
                id = 'btn-upload-dsa-result',
                outline = True,
                title = 'Upload previous DSA results',
            ), 
            id = 'upload-dsa-result',
            multiple = False,
            enable_folder_selection = False,
            accept = '.csv,.xlsx,.zip',
            className = 'upload-button',
        )
    ]

    return html.Div(
        [
            html.Div(
                id={'type': 'resize-handle', 'page': kwargs.get('page_type', 'None')}, 
                className='resize-handle resize-handle-ok'
            ),
            dbc.Tooltip(
                'Results up-to-date',
                id = {'type': 'result-tooltip', 'page': kwargs.get('page_type', 'None')},
                target = {'type': 'resize-handle', 'page': kwargs.get('page_type', 'None')}
            ),

            html.Div(
                dbc.Container([
                    dbc.Row([
                        html.Div(
                            html.H1(
                                [icons.get_icon('results'), 'DSA Results'],
                            ),
                            className = 'results-header-title-container'
                        ),
                        html.Div(
                            button_container_children,
                            className = 'results-header-button-container'
                        )
                    ]),
                    
                ]),
            className = 'drawer-title',
            )
        ],
    className = 'drawer-header',
    )

def create_results_header_psa(**kwargs):
    button_container_children = [
        dbc.Button(
            'Run PSA',
            color = 'primary',
            id = 'btn-psa-prerun',
            disabled = False,
        ), 
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color = 'secondary',
            id = 'btn-psa-result-predownload',
            #id = {'type': 'results-predownload-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
            outline = True,
            title = 'Download PSA results',
        ), 
        dcc.Upload(
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-upload', style_name = 'raw'),
                    style = {'display': 'inline'}
                ),
            
                color = 'secondary',
                id = {'type': 'results-upload-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
                outline = True,
                title = 'Upload previous PSA results',
            ), 
            id = 'upload-psa-result',
            #id = {'type': 'results-upload', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
            multiple = False,
            enable_folder_selection = False,
            accept = '.csv,.xlsx,.zip',
            className = 'upload-button',
        )
    ]

    return html.Div(
        [
            html.Div(
                id={'type': 'resize-handle', 'page': kwargs.get('page_type', 'None')}, 
                className='resize-handle resize-handle-ok'
            ),
            
            dbc.Tooltip(
                'Results up-to-date',
                id = {'type': 'result-tooltip', 'page': kwargs.get('page_type', 'None')},
                target = {'type': 'resize-handle', 'page': kwargs.get('page_type', 'None')}
            ),
            
            html.Div([
                dbc.Container([
                    dbc.Row([
                        html.Div(
                            html.H1(
                                [icons.get_icon('results'), 'PSA Results']
                            ),
                            className = 'results-header-title-container'
                        ),
                        html.Div(
                            button_container_children,
                            className = 'results-header-button-container'
                        )
                    ]),
                ]),
            ],
            className = 'drawer-title',
            )
        ],
    className = 'drawer-header',
    )