"""
Functions for building navigation layouts
"""

from dash import html
import dash_bootstrap_components as dbc
from functools import partial

from src.newsegsbrowser import icons

create_navbutton = partial(
    dbc.Button,
    color = 'secondary',
    class_name = 'newsegs-nav-button btn-block',    
)

def create_nav_landing():
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-landing', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'landing'},
        title = 'Landing page',
        href = '/landing',
    )

def create_nav_system_config():
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-system-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'system-config'},
        title = 'Site configuration',
        href = '/site-config',
    )

def create_nav_buildings():
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-build-arch-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'build-arch'},
        title = 'Buildings',
        href = '/buildings',
    )

def create_nav_dsa():
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-dsa-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'dsa'},
        title = 'Sensitivity analysis',
        href = 'dsa',
    )

def create_nav_psa():
    return create_navbutton(
        [
            html.I(
                className = icons.get_icon('nav-psa-config', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
        ],
        id = {'type': 'btn-nav', 'label': 'psa'},
        title = 'Probabilistic analysis',
        href = 'psa',
    )

def create_navigator_buttons_default():
    return [
        create_nav_landing(),
        create_nav_system_config(),
        create_nav_buildings(),
        create_nav_dsa(),
        create_nav_psa(),
    ]