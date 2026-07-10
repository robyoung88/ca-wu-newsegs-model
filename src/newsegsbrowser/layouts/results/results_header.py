from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsbrowser import icons
from newsegssensitivity import common as sensitivity

def create_results_header(**kwargs):
    """
    HTML separating the results and providing controls for setting result format per annum or
    to horizon
    """
    autorun = kwargs.get('autorun_model', True)
    autorun_icon = 'autorun-true' if autorun else 'autorun-stop'
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
                        html.H1(
                            [
                                icons.get_icon('results'), 
                                'Results',
                                dbc.Button(
                                    html.I(
                                        className = icons.get_icon(autorun_icon, style_name = 'raw'),
                                        style={'display': 'inline'}
                                    ),
                                    color = 'primary' if autorun else 'secondary',
                                    id = {'type': 'autorun-btn', 'page': kwargs.get('page_type', 'None')},
                                    outline = not(autorun),
                                    style = {
                                        'margin-left': '5px',
                                        'border-radius': '50%',
                                    }
                                )
                            ],
                            className = 'results-title-block'
                        ),
                        html.Span([
                            dbc.Button(
                                html.I(
                                    className = icons.get_icon('config-1', style_name = 'raw'),
                                    style={'display': 'inline'}
                                ),
                                color='primary',
                                id = {'type': 'config-hdrfocus-btn', 'index': 0},
                                outline = False
                            )
                        ],
                        id = {'type': 'metamodel-input-container', 'supersection': 'configurations', 'section': 'configuration-header-selector'},
                        #id = 'config-selector-hdrcontainer',
                        className = 'configuration-selector-hdrcontainer'
                        ),

                        html.Span([
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
                                            id='annual-horizon-toggle'),
                            html.H5('To horizon',style={'display': 'inline-block', 'verticalAlign': 'middle'})
                        ],
                        id = 'annual-horizon-toggle-container',
                        className = 'annual-horizon-toggle-hdrcontainer'

                        ),
                    ]),
                    dbc.Row(
                        [
                            dcc.Graph(
                                id = 'graph-timeseries',
                                style = {
                                    'height': '300px',
                                }
                            )
                        ],
                        id = 'timeseries-graph-container',
                        style = {
                            'display': 'none'
                            },
                    )
                ]),
            className = 'drawer-title'
            ),
        ],
    className = 'drawer-header'
    )

def create_results_header_dsa(**kwargs):
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
                        html.H1(
                            [icons.get_icon('results'), 'DSA Results'],
                            style = {
                                'float': 'left',
                                'width':'75%'
                            }
                        ),
                        html.Span(
                            dbc.Button(
                                'Run DSA',
                                color = 'primary',
                                id = {'type': 'dsa-prerun-button', 'page': kwargs.get('page-type', 'None')},
                                disabled = False,
                                style = {
                                    'display': 'inline',
                                }
                            ),
                            style = {
                                'float': 'right',
                                'width': '25%'
                            }
                        )
                    ]),
                    dbc.Row([
                        dcc.Dropdown(
                            options = [
                                {'label': v, 'value': k} for k, v in sensitivity.DSA_STATISTIC_LABELS.items()
                            ],
                            value = list(sensitivity.DSA_STATISTIC_LABELS.keys())[0],
                            id = {'type': 'dsa-results-statistic-dropdown', 'page': kwargs.get('page_type', 'None')},
                            searchable = False,
                            clearable = False,
                        )
                    ])
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
            id = {'type': 'psa-prerun-button', 'page': kwargs.get('page_type', 'None')},
            disabled = False,
        ),
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color = 'secondary',
            id = {'type': 'results-predownload-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
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
            id = {'type': 'results-upload', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
            multiple = False,
            enable_folder_selection = False,
            accept = '.csv',
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
                #dbc.Container([
                    #dbc.Row([
                        html.Div(
                            html.H1(
                                [icons.get_icon('results'), 'PSA Results']
                            ),
                            className = 'psa-results-header-title-container'
                        ),
                        html.Div(
                            button_container_children,
                            className = 'psa-results-header-button-container'
                        )
                    #]),
                    
                #]),
            ],
            className = 'drawer-title',
            )
        ],
    className = 'drawer-header',
    )