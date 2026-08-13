from dash import html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser import common as browser

def create_storage_cost_input_card():
    """
    HTML inputs for storage costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-storage'), 'Storage Costs'],
            className='card-title'),

            html.H4(
                id = {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-stor-smry'},
                className='card-subtitle'
            ),

            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'finance-config', 'section': 'stor_costs'},
                    className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])