from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelframework.newsegssensitivity import common as sensitivity

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
            ), # pyright: ignore[reportCallIssue]

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
                                        id = {
                                            'type': 'action-button', 'purpose': 'request-process',
                                            'supersection': 'deterministic', 'section': 'run',
                                            'key': 'deterministic_run_metamodel', 'subindex': 0,
                                        },
                                        style = {
                                            'margin-left': '5px',
                                            'border-radius': '50%',
                                            'display': 'inline',
                                        },
                                        title = 'Run single configuration',
                                    ), # pyright: ignore[reportCallIssue]

                                    # Run project button
                                    dbc.Button(
                                        html.I(
                                            className = icons.get_icon('deterministic-run-project', style_name = 'raw'),
                                            style={'display': 'inline'}
                                        ),
                                        color = 'primary',
                                        id = {
                                            'type': 'action-button', 'purpose': 'request-process',
                                            'supersection': 'deterministic', 'section': 'run',
                                            'key': 'deterministic_run_project', 'subindex': 0,
                                        },
                                        style = {
                                            'margin-left': '5px',
                                            'border-radius': '50%',
                                            'display': 'inline',
                                        },
                                        title = 'Run all configurations',
                                    ), # pyright: ignore[reportCallIssue]
                                ],
                            ),
                            className = 'results-title-block'
                        ),
                        html.Div([
                            dbc.Button(
                                html.I(
                                    className = icons.get_icon('config-1', style_name = 'raw'),
                                    style={'display': 'inline'}
                                ),
                                color='primary',
                                id = {'type': 'config-hdrfocus-btn', 'index': 0},
                                outline = False
                            ) # pyright: ignore[reportCallIssue]
                        ],
                        id = {
                            'type': 'metamodel-input-container', 'purpose': 'container',
                            'supersection': 'configurations', 'section': 'configuration-header-selector',
                            'key': 'results-header-metamodel-input-container', 'subindex': 0
                            },
                        className = 'configuration-selector-hdrcontainer'
                        ),

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
                            ), # pyright: ignore[reportCallIssue]

                            html.H5("Per year", style={'display': 'inline-block', 'verticalAlign': 'middle'}),
                            daq.ToggleSwitch(style={'display': 'inline-block',
                                                    'verticalAlign': 'middle',
                                                    'padding': "10px"},
                                            id={'type': 'annual-horizon-toggle', 'page': kwargs.get('page_type', 'None')},),
                            html.H5('To horizon',style={'display': 'inline-block', 'verticalAlign': 'middle'})
                        ],
                        id = 'annual-horizon-toggle-container',
                        className = 'annual-horizon-toggle-hdrcontainer'

                        ),
                    ]), # pyright: ignore[reportCallIssue]
                    dbc.Row(
                        [
                            dcc.Graph(
                                id = 'graph-timeseries',
                                style = {
                                    'height': '300px',
                                }
                            ),
                            
                        ],
                        id = 'timeseries-graph-container',
                        style = {
                            'display': 'none'
                            },
                    ), # pyright: ignore[reportCallIssue]
                    dcc.Store({
                        'type': 'postaction-trigger', 'purpose': 'manualtrigger',
                        'supersection': 'global', 'section': 'tabledraw',
                        'key': 'timeseriesupdate', 'subindex': 0
                    }, data = 0),
                ]), # pyright: ignore[reportCallIssue]
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
            id = {'type': 'dsa-prerun-button', 'page': kwargs.get('page_type', 'None')},
            title = 'Start DSA run',
            disabled = False,
        ), # pyright: ignore[reportCallIssue]
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color = 'secondary',
            id = {'type': 'results-predownload-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa'},
            outline = True,
            title = 'Download DSA results',
        ), # pyright: ignore[reportCallIssue]
        dcc.Upload(
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-upload', style_name = 'raw'),
                    style = {'display': 'inline'}       
                ),
            
                color = 'secondary',
                id = {'type': 'results-upload-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa'},
                outline = True,
                title = 'Upload previous DSA results',
            ), # pyright: ignore[reportCallIssue]
            id = {'type': 'results-upload', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa'},
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
            ), # pyright: ignore[reportCallIssue]

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
                    ]), # pyright: ignore[reportCallIssue]
                    
                ]), # pyright: ignore[reportCallIssue]
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
        ), # pyright: ignore[reportCallIssue]
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color = 'secondary',
            id = {'type': 'results-predownload-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
            outline = True,
            title = 'Download PSA results',
        ), # pyright: ignore[reportCallIssue]
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
            ), # pyright: ignore[reportCallIssue]
            id = {'type': 'results-upload', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
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
            ), # pyright: ignore[reportCallIssue]
            
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
                    ]),     # pyright: ignore[reportCallIssue]
                ]), # pyright: ignore[reportCallIssue]
            ],
            className = 'drawer-title',
            )
        ],
    className = 'drawer-header',
    )