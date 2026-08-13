from dash import html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser import common as browser

def create_building_consumption_input_card():
    """
    A Bootstrap card holding inputs for building consumption config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('consumption-building'), "Building Consumption"], 
            className='card-title'),
            
            html.H4(
                id = {'type': 'input-header', 'section': 'model-config', 'key': 'bc-smry'},
                className='card-subtitle'
            ),
            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'model-config', 'section': 'bc_input'},
                    className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])