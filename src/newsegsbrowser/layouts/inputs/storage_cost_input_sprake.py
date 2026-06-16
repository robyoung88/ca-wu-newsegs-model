from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_storage_cost_input_card():
    """
    HTML inputs for storage costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-storage'), 'Storage Costs'],
            className='card-title'),

            html.H4([
                "Capital cost = £",
                html.Span("0"),
                "; Ongoing costs = £",
                html.Span("0"),
                "/yr"
            ],
            id = {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-stor-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'storage',
                            'BESS Capex (£/kWh)',
                            'input-finance-config',
                            'bess_capex_per_kwh',
                            section = 'unit_costs',
                            max = 10000,
                            step = 50
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            ['storage', 'cost-recurrent'],
                            'BESS Ongoing (£/kWh/yr)',
                            'input-finance-config',
                            'bess_om_per_kwh_year',
                            section = 'unit_costs',
                            max = 5000,
                            step = 10
                        )
                    ),
                ])
            ])
        ])
    ])