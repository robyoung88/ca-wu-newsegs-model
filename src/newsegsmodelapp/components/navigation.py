"""
Functions for building navigation layouts
"""

from typing import Any

from dash import html
import dash_bootstrap_components as dbc
from functools import partial

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

def create_nav_options(selected_model: str):
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

def create_nav_landing(selected_model: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-landing', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'landing'},
        title = 'Landing page',
        href = f'/{selected_model}/landing',
    )

def create_nav_system_config(selected_model: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-system-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'system-config'},
        title = 'Site configuration',
        href = f'/{selected_model}/site-config',
    )

def create_nav_buildings(selected_model: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-build-arch-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'build-arch'},
        title = 'Buildings',
        href = f'/{selected_model}/buildings',
    )

def create_nav_dsa(selected_model: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-dsa-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'dsa'},
        title = 'Sensitivity analysis',
        href = f'/{selected_model}/dsa',
    )

def create_nav_psa(selected_model: str):
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-psa-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'psa'},
        title = 'Probabilistic analysis',
        href = f'/{selected_model}/psa',
    )

def create_navigator_buttons_default(selected_model: str = 'sprake'):
    match selected_model:
        case 'sprake':
            return [
                #create_nav_options(selected_model),
                create_nav_landing(selected_model),
                create_nav_system_config(selected_model),
                create_nav_dsa(selected_model),
                create_nav_psa(selected_model),
            ]
        case _:
            return [
                create_nav_options(selected_model),
                create_nav_landing(selected_model),
                create_nav_system_config(selected_model),
                create_nav_buildings(selected_model),
                create_nav_dsa(selected_model),
                create_nav_psa(selected_model),
            ]

def create_navigation_component(selected_model: str = 'sprake'):
    return html.Div(
        create_navigator_buttons_default(selected_model),
        className = 'newsegs-navbar mt-1'
    )
