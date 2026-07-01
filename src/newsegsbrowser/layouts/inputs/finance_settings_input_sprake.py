from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_finance_settings_input_card():
    """
    HTML inputs for general finance settings (e.g. discount rates)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('finance-settings'), 'Finance Settings'],
            className='card-title'),

            html.H4(
                id = {'type': 'input-header', 'section': 'finance-config', 'key': 'fnc-smry'},
                className='card-subtitle'
            ),

            html.Details([
                html.Summary(""),
                html.Div(
                id = {'type': 'input-container', 'supersection': 'finance-config', 'section': 'finance_settings'},
                className = 'input-container model-config-input-container'
                )
            ])
        ]),
    ])