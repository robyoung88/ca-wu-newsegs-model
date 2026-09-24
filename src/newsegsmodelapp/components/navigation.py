"""
Functions for building navigation layouts
"""

from typing import Any, Sequence

from dash import html
import dash_bootstrap_components as dbc
from functools import partial

from newsegsmodelapp import registers
from newsegsmodelapp.newsegsbrowser import icons

dbc_Button: Any = dbc.Button

create_optionsbutton = partial(
    dbc_Button,
    color = 'info',
    class_name = 'newsegs-navbar-button newsegs-options-button p-1',
)

create_navbutton = partial(
    dbc_Button,
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

def create_nav_landing(model_type: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-landing', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'landing'},
        title = 'Landing page',
        href = f'/{model_type}/landing',
    )

def create_nav_system_config(model_type: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-system-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'system-config'},
        title = 'Site configuration',
        href = f'/{model_type}/site-config',
    )

def create_nav_buildings(model_type: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-build-arch-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'build-arch'},
        title = 'Buildings',
        href = f'/{model_type}/buildings',
    )

def create_nav_dsa(model_type: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-dsa-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'dsa'},
        title = 'Sensitivity analysis',
        href = f'/{model_type}/dsa',
    )

def create_nav_psa(model_type: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-psa-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'psa'},
        title = 'Probabilistic analysis',
        href = f'/{model_type}/psa',
    )

def create_navigator_buttons_default(model_type: str = 'sprake'):
    match model_type:
        case 'sprake':
            return [
                #create_nav_options(model_type),
                create_nav_landing(model_type),
                create_nav_system_config(model_type),
                create_nav_dsa(model_type),
                create_nav_psa(model_type),
            ]
        case _:
            return [
                create_nav_options(model_type),
                create_nav_landing(model_type),
                create_nav_system_config(model_type),
                create_nav_buildings(model_type),
                create_nav_dsa(model_type),
                create_nav_psa(model_type),
            ]

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
