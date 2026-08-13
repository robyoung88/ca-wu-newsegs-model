from dash import html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser import common as browser

def create_direct_consumption_input_card():
    """
    A Bootstrap card holding inputs for direct consumption config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('consumption-direct'), 'Direct Consumption'],
            className='card-title'),
            
            html.H4(
                id = {'type': 'input-header', 'section': 'model-config', 'key': 'dc-smry'},
                className='card-subtitle'
            ),

            html.Details([
                html.Summary(""),
                html.Div(
                id = {'type': 'input-container', 'supersection': 'model-config', 'section': 'dc_input'},
                className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])
