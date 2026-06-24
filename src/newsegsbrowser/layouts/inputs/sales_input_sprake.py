from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_sales_input_card():
    """
    HTML inputs for sales value (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-sales'), 'Sales'],
            className='card-title'),

            html.H4(
                id = {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-sales-smry'},
                className='card-subtitle'
            ),

            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'finance-config', 'section': 'sales_costs'},
                    className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])