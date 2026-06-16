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
            html.H4([
                'Total generation: ',
                icons.get_icon('gen-wind','p-1 my-1, ml-1', 'unpadded'),
                " = ",
                html.Span("0.0"),
                " kW; ",
                icons.get_icon('gen-pv','p-1 my-1, ml-1', 'unpadded'),
                " = ",
                html.Span("0.0"),
                " kWp"
            ],
            id = {'type': 'input-header', 'section': 'model-config', 'key': 'gen-smry'},
            className='card-subtitle'),
            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'gen-wind',
                            'Wind Capacity (kW rated)',
                            'input-model-config',
                            'wind_capacity',
                            section = 'gen_input',
                            max = 10000,
                            step = 5.0
                        )    
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'gen-pv',
                            'Solar PV Capacity (kWp)',
                            'input-model-config',
                            'pv_capacity',
                            section = 'gen_input',
                            max = 10000,
                            step = 5.0
                        )
                    )
                ])
            ])
        ])
    ])
