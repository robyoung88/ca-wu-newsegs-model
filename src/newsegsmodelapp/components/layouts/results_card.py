"""Results card module.

TODO: Describe the purpose of the module.
"""
import dash
from dash import html
import dash_bootstrap_components as dbc

def create_results_table_card(
    supersection: str,
    section: str,
    key: str = 'toplevel',
    title: list[dash.development.base_component.Component | str] = [''],
    className: str | None = None,
    header_section: str | None = None,
    header_key: str | None = None,
):
    """Create results table card.

    TODO: Add a description.

    Args:
        supersection: TODO.
        section: TODO.
        key: TODO.
        title: TODO.
        className: TODO.
        header_section: TODO.
        header_key: TODO.

    Returns:
        TODO.
    """
    header_section = section if header_section is None else header_section
    header_key = key if header_key is None else header_key
    if className is not None:
        container_class_name = 'result-container ' + className
    else:
        container_class_name = 'result-container'

    return dbc.Card([
        dbc.CardBody([
            html.H2(
                title, 
                className='card-title'
            ),
            
            html.H4(
                id = {
                    'type': 'result-section-header', 'purpose': 'header',
                    'supersection': supersection, 'section': header_section,
                    'key': header_key, 'subindex': 0
                },
                className='card-subtitle'
            ),

            html.Div(
                id = {
                    'type': 'result-container', 'purpose': 'container',
                    'supersection': supersection, 'section': section,
                    'key': key, 'subindex': 0
                },
                className = container_class_name
            ),
        ]) # pyright: ignore[reportCallIssue]
    ],
    ) # pyright: ignore[reportCallIssue]
