from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsbrowser import icons

def create_results_header():
    """
    HTML separating the results and providing controls for setting result format per annum or
    to horizon
    """
    return html.Div(
        [
            html.Div(id='resize-handle'),

            html.Div(
                dbc.Container([
                    dbc.Row([
                        html.H1(
                            [icons.get_icon('results'), 'Results'],
                            style={
                                'display': 'inline-block',
                                'width':'33%',
                                'float': 'left'
                            }
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
                        id = 'config-selector-hdrcontainer',
                        className = 'configuration-selector-container'
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
                        style={
                            'display': 'inline-block',
                            'width':'33%',
                            'float': 'right',
                            "justifyContent": "flex-end",
                            "alignItems": "center",
                            'textAlign': 'right'
                        },
                        id='annual-horizon-toggle-container'
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
            id = 'drawer-title',
            ),
        ],
    id='drawer-header'
    )
