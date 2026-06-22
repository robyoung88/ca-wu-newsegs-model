from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser import common as browser

def create_model_settings_input_card():
    """
    HTML inputs for general model settings (e.g. time horizon)
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('model-settings'), 'Model Settings'],
            className='card-title'),

            html.H4([
                icons.get_icon('model-settings-time-horizon'),
                " = ",
                html.Span("10"),
                " years"
            ],
            id = {'type': 'input-header', 'section': 'model-config', 'key': 'mc-smry'},
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div(#[
                    # dbc.Row(
                    #     browser.create_numeric_card_input_compound_key(
                    #         'model-settings-time-horizon',
                    #         'Time horizon (years)',
                    #         'input-model-config',
                    #         'horizon',
                    #         section = 'mc_input',
                    #         max = 10,
                    #         step = 1
                    #     )
                    # ),
                #],
                id = {'type': 'input-container', 'supersection': 'model-config', 'section': 'mc_input'},
                className = 'input-container model-config-input-container'
                )
            ])
        ]),
    ])
