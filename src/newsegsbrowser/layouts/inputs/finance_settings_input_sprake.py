from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser import icons
from src.newsegsbrowser import common as browser

def create_finance_settings_input_card():
    """
    HTML inputs for general finance settings (e.g. discount rates)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('finance-settings'), 'Finance Settings'],
            className='card-title'),

            html.H4([
                icons.get_icon('finance-settings-benefit-discount'),
                " = ",
                html.Span("0%"),
                "; ",
                icons.get_icon('finance-settings-cost-discount'),
                " = ",
                html.Span("0%"),
            ],
            id = {'type': 'input-header', 'section': 'finance-config', 'key': 'fnc-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'finance-settings-benefit-discount',
                            'Benefit discount rate (%)',
                            'input-finance-config',
                            'benefit_discount_rate',
                            section = None,
                            max = 100,
                            step = 1
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'finance-settings-cost-discount',
                            'Benefit discount rate (%)',
                            'input-finance-config',
                            'cost_discount_rate',
                            section = None,
                            max = 100,
                            step = 1
                        )
                    )
                ])
            ])
        ]),
    ])