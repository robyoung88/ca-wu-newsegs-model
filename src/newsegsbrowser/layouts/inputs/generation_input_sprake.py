from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_generation_input_card():
    """
    A Bootstrap card holding inputs for generation config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('generation'), 'Generation'], className='card-title'),
            html.H4(
                id = {'type': 'input-header', 'section': 'model-config', 'key': 'gen-smry'},
                className='card-subtitle'
            ),
            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'model-config', 'section': 'gen_input'},
                    className = 'input-container model-config-input-container'
                )
            ])
        ])
    ],
    className = 'input-card'
    )
