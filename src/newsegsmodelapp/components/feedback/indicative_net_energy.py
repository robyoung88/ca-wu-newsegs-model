"""The graphs which give indicative feedback of the net energy of a site as its inputs are edited, from `EstimatedEnergyBalance`.
"""
from functools import partial

from dash import dcc, html
from dash_iconify import DashIconify
import plotly.express as px

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_indicative_net_energy_card():
    """
    A Bootstrap card holding plots to help with generation and consumption sizing.
    """
    return dbc.Card([
        dbc.CardBody([
            html.Details([
                html.Summary(
                    html.H5(
                        [
                            DashIconify(icon = 'bi:bar-chart', width = 24, className = 'd-inline-flex m-1'), 
                            html.H3('Indicative net energy', className = 'd-inline-flex')],
                        className = 'd-flex align-content-center flex-wrap m-0',
                    ),
                    style={
                        'listStyle': 'none',  # Removes marker in modern browsers
                        'cursor': 'pointer',
                        'userSelect': 'none',
                    },
                    className='summary-no-caret', # Hook for browser-specific caret hiding
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
                ],
                className = 'mt-3', # Adds spacing between title and graphs when expanded
                ),
            ])
        ],
        className = 'p-2', # Tightens CardBody padding
        )
    ])

_feedback_graph_bar = partial(
    px.bar,
    x = 'value',
    color = 'label',
    orientation = 'h'
)

_feedback_graph_layout = dict(
    height=120,
    margin={'l': 0, 'r': 0, 't': 28, 'b': 0},
    title={
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 12, 'family': 'Arial', 'color': '#212529', 'weight': 'bold'}
    },
    showlegend=False,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    bargap=0.75
)
