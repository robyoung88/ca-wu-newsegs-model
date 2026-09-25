import dash
from dash import html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_input_card(
    supersection: str,
    section: str,
    title: list[dash.development.base_component.Component | str],
    className: str | None = None
):
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
            
            html.H4(
                id = {'type': 'input-section-header', 'supersection': supersection, 'section': section},
                className='card-subtitle'
            ),
            
            html.Details([
                html.Summary(""),
                html.Div(
                    id = {'type': 'input-container', 'supersection': supersection, 'section': section},
                    className = container_class_name
                )
            ])
        ])
    ])
