from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser import icons
from src.newsegsbrowser import common as browser

def create_building_consumption_input_card():
    """
    A Bootstrap card holding inputs for building consumption config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('consumption-building'), "Building Consumption"], 
            className='card-title'),
            
            html.H4([
                'Site size: ',
                html.Span("0"),
                " units"
            ],
            id = {'type': 'input-header', 'section': 'model-config', 'key': 'bc-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-nunits',
                            'No. of households',
                            'input-model-config',
                            'n_units',
                            section = 'bc_input',
                            max = 1000,
                            step = 1
                        ),
                    ]),
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-hlp',
                            'HLP (W/m²/K)',
                            'input-model-config',
                            'hlp',
                            section = 'bc_input',
                            max = 3.0,
                            step = 0.1
                        ),
                    ]),
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-gfa',
                            'Mean GFA (m²/household)',
                            'input-model-config',
                            'gfa',
                            section = 'bc_input',
                            max = 300,
                            step = 1
                        ),
                    ]),
                    # TODO: Output Fabric Energy Efficiency here
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-dhw-ref',
                            'Reference hot water demand (kWh/day)',
                            'input-model-config',
                            'ref_daily_consumption',
                            section = 'bc_input',
                            max = 10.0,
                            step = 0.1
                        ),
                    ]),
                    dbc.Row([
                        browser.create_numeric_card_input_compound_key(
                            'consumption-building-dhw-var',
                            'Seasonal variation (%)',
                            'input-model-config',
                            'seasonal_variance',
                            section = 'bc_input',
                            max = 100.0,
                            step = 1
                        ),
                    ])
                    # TODO: Output annual DHW demand
                ])
            ])
        ])
    ])