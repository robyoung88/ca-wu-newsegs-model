from dash import html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser import common as browser

def create_model_settings_input_card():
    """
    HTML inputs for general model settings (e.g. time horizon)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('model-settings'), 'Model Settings'],
            className='card-title'),

            html.H4(
                id = {'type': 'input-header', 'section': 'model-config', 'key': 'mc-smry'},
                className='card-subtitle'
            ),

            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'model-config', 'section': 'mc_input'},
                    className = 'input-container model-config-input-container'
                )
            ])
        ]),
    ])
