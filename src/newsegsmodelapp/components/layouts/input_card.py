"""The card which holds inputs.
"""
import dash
from dash import dcc, html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_input_card(
    supersection: str,
    section: str,
    title: list[dash.development.base_component.Component | str],
    className: str | None = None
):
    """Create a card to hold inputs.

    The body is an input container, filled by callbacks with the inputs registered for the supersection and section.

    Args:
        supersection: The supersection (e.g. the page or group of inputs).
        section: The interface section of the variable.
        title: Title of the card.
        className: Further CSS classes.

    Returns:
        The card.
    """
    if className is not None:
        container_class_name = 'input-container ' + className
    else:
        container_class_name = 'input-container'

    return dbc.Card([
        dbc.CardBody([
            html.H2(
                title, 
                className='card-title'
            ),

            dcc.Loading(
                html.H4(
                    id = {'type': 'input-section-header', 'supersection': supersection, 'section': section},
                    className='card-subtitle'
                ),
                delay_show = 500,
                delay_hide = 500,
                overlay_style={"visibility":"visible", "filter": "blur(1px)"},
                custom_spinner=html.H1(''),
            ),
            
            
            html.Details([
                html.Summary(""),
                dcc.Loading(
                    html.Div(
                        id = {'type': 'input-container', 'supersection': supersection, 'section': section},
                        className = container_class_name
                    ),
                    delay_show = 500,
                    delay_hide = 500,
                    overlay_style={"visibility":"visible", "filter": "blur(1px)"},
                    custom_spinner=html.H1(''),
                )
                
            ]),

            dcc.Interval(
                id = {
                    'type': 'input-container-hydration-interval', 
                    'supersection': supersection, 
                    'section': section
                },
                n_intervals = 1,
                disabled = False,
                max_intervals = 1,
                interval = 50,
            )
        ])
    ])
