from dash import dcc, html
import dash_bootstrap_components as dbc

def create_indicative_net_energy_card():
    """
    A Bootstrap card holding plots to help with generation and consumption sizing.
    """
    return dbc.Card([
        dbc.CardBody([
            html.Details([
                html.Summary(
                    html.H5(
                        ['Indicative net energy']
                        ),
                ),
                dbc.Row([
                    dbc.Col(
                        dcc.Graph(
                            id={'type': 'feedback-graph', 'section': 'feedback', 'key': 'estimated-annual-energy'},
                            config={'displayModeBar': False},
                            style={
                                'height': '120px',
                                'border': '1px solid #dee2e6',
                                'borderRadius': '0.5rem',
                                'backgroundColor': 'transparent'
                            }
                        )
                    ),
                    dbc.Col(
                        dcc.Graph(
                            id={'type': 'feedback-graph', 'section': 'feedback', 'key': 'estimated-maximum-daily-energy'},
                            config={'displayModeBar': False},
                            style={
                                'height': '120px',
                                'border': '1px solid #dee2e6',
                                'borderRadius': '0.5rem',
                                'backgroundColor': 'transparent'
                            }
                        )
                    )
                ])
            ])
        ])
    ])
