from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_gen_cost_input_card():
    """
    HTML inputs for generation costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-generation'), 'Generation Costs'],
            className='card-title'),

            html.H4([
                "Capital cost = £",
                html.Span("0"),
                "; Ongoing costs = £",
                html.Span("0"),
                "/yr"
            ],
            id = {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-gen-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div(#[
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         'gen-wind',
                    #         'Wind Capex (£/kW)',
                    #         'input-finance-config',
                    #         'wind_capex_per_kw',
                    #         section = 'unit_costs',
                    #         max = 10000,
                    #         step = 50
                    #     )
                    # ),
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         ['gen-wind','cost-recurrent'],
                    #         'Wind Ongoing (£/kW/yr)',
                    #         'input-finance-config',
                    #         'wind_om_per_kw_year',
                    #         section = 'unit_costs',
                    #         max = 5000,
                    #         step = 10
                    #     )
                    # ),
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         'gen-pv',
                    #         'Solar PV Capex (£/kWp)',
                    #         'input-finance-config',
                    #         'pv_capex_per_kw',
                    #         section = 'unit_costs',
                    #         max = 10000,
                    #         step = 50
                    #     )
                    # ),
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         ['gen-pv','cost-recurrent'],
                    #         'Solar PV Ongoing (£/kWp/yr)',
                    #         'input-finance-config',
                    #         'pv_om_per_kw_year',
                    #         section = 'unit_costs',
                    #         max = 5000,
                    #         step = 10
                    #     )
                    # ),
                #]
                id = {'type': 'input-container', 'supersection': 'finance-config', 'section': 'gen_costs'},
                className = 'input-container model-config-input-container'
                )
            ])
        ]),
    ])
