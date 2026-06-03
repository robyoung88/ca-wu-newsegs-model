from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser import icons
from src.newsegsbrowser import common as browser

def create_sales_input_card():
    """
    HTML inputs for sales value (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-sales'), 'Sales'],
            className='card-title'),

            html.H4([
                icons.get_icon('cost-residents'),
                " = £",
                html.Span("0", id="cost-sales-smry-residents"),
                "/yr; ",
                icons.get_icon('cost-export'),
                " = £",
                html.Span("0", id="cost-sales-smry-export"),
                "/yr"
            ],
            id = {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-sales-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-residents-standing',
                            'Standing charge (£/household/day)',
                            'input-finance-config',
                            'resident_sc_per_unit_day',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-residents-perunit',
                            'Per unit charge (£/kWh)',
                            'input-finance-config',
                            'resident_var_per_unit',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                    ),
                    dbc.Row(
                        browser.create_numeric_card_input_compound_key(
                            'cost-export',
                            'Grid export - mean per unit (£/kWh)',
                            'input-finance-config',
                            'grid_export_var_per_unit',
                            section = 'unit_costs',
                            max = 10,
                            step = 0.01
                        )
                    ),
                ])
            ])
        ])
    ])