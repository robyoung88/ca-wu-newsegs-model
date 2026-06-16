from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_direct_consumption_input_card():
    """
    A Bootstrap card holding inputs for direct consumption config
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('consumption-direct'), 'Direct Consumption'],
            className='card-title'),
            
            html.H4([
                icons.get_icon('consumption-direct-appliance'),
                " = ",
                html.Span("0.0"),
                " kWh/yr/household; ",
                icons.get_icon('consumption-direct-ev'),
                " = ",
                html.Span("0.0"),
                " kWh/yr/household"
            ],
            id = {'type': 'input-header', 'section': 'model-config', 'key': 'dc-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'consumption-direct-appliance-reduction',
                            'High-efficiency appliances consumption reduction (fraction)',
                            'input-model-config',
                            'efficiency_reduction',
                            section = 'dc_input',
                            max = 1,
                            step = 0.05
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'consumption-direct-ev-anncharge',
                            'Residential charging per EV (kWh/yr)',
                            'input-model-config',
                            'annual_residential_consumption_per_ev',
                            section = 'dc_input',
                            max = 4000,
                            step = 0.05,
                            placeholder = 2000
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'consumption-direct-ev-nperunit',
                            'EVs per household (n)',
                            'input-model-config',
                            'n_evs_per_household',
                            section = 'dc_input',
                            max = 3,
                            step = 0.05,
                            placeholder = 0.2
                        )
                    ),
                ])
            ])
        ])
    ])
