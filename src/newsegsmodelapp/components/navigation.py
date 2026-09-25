"""
Functions for building navigation layouts
"""

from typing import Sequence

from dash import html
from functools import partial

from newsegsmodelapp import registers
from newsegsmodelapp.components import icons
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

create_optionsbutton = partial(
    dbc.Button,
    color = 'info',
    class_name = 'newsegs-navbar-button newsegs-options-button p-1',
)

create_navbutton = partial(
    dbc.Button,
    color = 'secondary',
    class_name = 'newsegs-navbar-button newsegs-nav-button p-1',    
)

def create_newsegs_model_navbutton(model_type, page_id, nav_label, nav_icon):
    return create_navbutton(
        nav_icon,
        id = {'type': 'btn-nav', 'label': page_id},
        title = nav_label,
        href = f'/{model_type}/{page_id}',
    )

def create_nav_options(model_type: str):
    return create_optionsbutton(
        [
            html.I(
                className = icons.get_icon('nav-options', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-options', 'label': 'options'},
        title = 'Options',
    )

def create_navigator_buttons(
        model_type: str = 'default',
        pages: Sequence[str] | None = None,
    ):
    if pages is None:
        pages = [x for x in registers.PAGE_REGISTER.keys()]
    page_objs = [registers.get_page(x) for x in pages]
    return [
        create_newsegs_model_navbutton(
            model_type,
            x.id,
            x.nav_label,
            x.nav_icon
        ) for x in page_objs
    ]

def create_navigation_component(
        model_type: str = 'default',
        pages: Sequence[str] | None = None,
    ):
    return html.Div(
        create_navigator_buttons(model_type, pages),
        className = 'newsegs-navbar mt-1'
    )
