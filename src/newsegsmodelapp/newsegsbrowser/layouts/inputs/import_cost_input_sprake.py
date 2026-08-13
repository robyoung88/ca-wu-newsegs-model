from dash import html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser import common as browser

def create_import_cost_input_card():
    """
    HTML inputs for import costs (Sprake model)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost-import'), 'Import Costs'],
            className='card-title'),

            html.H4(
                id = {'type': 'input-header', 'section': 'finance-config', 'key': 'cost-import-smry'},
                className='card-subtitle'
            ),

            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': 'finance-config', 'section': 'import_costs'},
                    className = 'input-container model-config-input-container'
                )
            ])
        ])
    ])