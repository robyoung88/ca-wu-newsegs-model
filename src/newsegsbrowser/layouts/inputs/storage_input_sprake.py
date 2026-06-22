from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_storage_input_card():
    """
    A Bootstrap card holding inputs for storage config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('storage'), "Storage"], 
            className='card-title'),
            
            html.H4([
                'Storage capacity: ',
                html.Span("0.0"),
                " kWh"
            ],
            id = {'type': 'input-header', 'section': 'model-config', 'key': 'stor-smry'},
            className='card-subtitle'),
            
            html.Details([
                html.Summary(""),
                html.Div(#[
                    # dbc.Row([
                    #     browser.create_numeric_card_input_compound_key(
                    #         'storage',
                    #         'Storage Capacity (kWh)',
                    #         'input-model-config',
                    #         'storage_capacity',
                    #         section = 'stor_input',
                    #         max = 10000,
                    #         step = 5.0
                    #     ),
                    # ])
                #],
                id = {'type': 'input-container', 'supersection': 'model-config', 'section': 'stor_input'},
                className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])
