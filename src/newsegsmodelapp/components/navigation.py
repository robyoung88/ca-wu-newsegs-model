"""
Functions for building navigation layouts
"""

from typing import Sequence

from dash import html
from functools import partial

from newsegsmodelapp import registers
from newsegsmodelapp.components import icons
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

DOCS_URL = '/documentation/'
"""Where the app serves the documentation (see `documentation` in `app.py`)."""

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
    """Create newsegs model navbutton.

    TODO: Add a description.

    Args:
        model_type: TODO.
        page_id: TODO.
        nav_label: TODO.
        nav_icon: TODO.

    Returns:
        TODO.
    """
    return create_navbutton(
        nav_icon,
        id = {'type': 'btn-nav', 'label': page_id},
        title = nav_label,
        href = f'/{model_type}/{page_id}',
    )

def create_nav_options(model_type: str):
    """Create nav options.

    TODO: Add a description.

    Args:
        model_type: TODO.

    Returns:
        TODO.
    """
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

def create_docs_button():
    """A button linking to the documentation index.

    The documentation is served as separate HTML pages, so the link must be an ordinary
    (external) link rather than Dash client-side navigation.
    """
    return create_navbutton(
        html.I(
            className = icons.get_icon('nav-help', style_name = 'raw'),
            style = {'display': 'inline'}
        ),
        id = {'type': 'btn-nav', 'label': 'documentation'},
        title = 'Documentation',
        href = DOCS_URL,
        external_link = True,
        class_name = 'newsegs-navbar-button newsegs-nav-button newsegs-docs-button p-1',
    )

def create_navigator_buttons(
        model_type: str = 'default',
        pages: Sequence[str] | None = None,
    ):
    """Create navigator buttons.

    TODO: Add a description.

    Args:
        model_type: TODO.
        pages: TODO.

    Returns:
        TODO.
    """
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
    ] + [create_docs_button()]

def create_navigation_component(
        model_type: str = 'default',
        pages: Sequence[str] | None = None,
    ):
    """Create navigation component.

    TODO: Add a description.

    Args:
        model_type: TODO.
        pages: TODO.

    Returns:
        TODO.
    """
    return html.Div(
        create_navigator_buttons(model_type, pages),
        className = 'newsegs-navbar mt-1'
    )
