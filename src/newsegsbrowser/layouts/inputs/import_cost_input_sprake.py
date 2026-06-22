from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_import_cost_input_card():
    """
    HTML inputs for import costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-import'), 'Import Costs'],
            className='card-title'),

            html.H4([
                "Fixed costs = £",
                html.Span("0", id="cost-import-smry-fixed"),
                "/yr; Ongoing costs = £",
                html.Span("0", id="cost-import-smry-ongoing"),
                "/yr"
            ],
            {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-import-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div(#[
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         'cost-import-fixed',
                    #         'Fixed costs for backup (£/site/day)',
                    #         'input-finance-config',
                    #         'grid_import_sc_per_day',
                    #         section = 'unit_costs',
                    #         max = 10000,
                    #         step = 10
                    #     )
                    # ),
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         'cost-import-perunit',
                    #         'Per-unit costs for backup (£/kWh)',
                    #         'input-finance-config',
                    #         'grid_import_var_per_unit',
                    #         section = 'unit_costs',
                    #         max = 10,
                    #         step = 0.01
                    #     )
                    # ),
                #]
                id = {'type': 'input-container', 'supersection': 'finance-config', 'section': 'import_costs'},
                className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])