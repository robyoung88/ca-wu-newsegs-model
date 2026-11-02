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
    """Create the navigation button of a page.

    A link to `/{model_type}/{page_id}`.

    Args:
        model_type: The model type (e.g. `sprake`); `default` for the fallback.
        page_id: Id of the page.
        nav_label: See the description.
        nav_icon: See the description.

    Returns:
        The button.
    """
    return create_navbutton(
        nav_icon,
        id = {'type': 'btn-nav', 'label': page_id},
        title = nav_label,
        href = f'/{model_type}/{page_id}',
    )

# REVIEW (unreferenced): no references to `create_nav_options` found in src/, scripts/ or data/.
def create_nav_options(model_type: str):
    """Create the options button.

    Args:
        model_type: The model type (e.g. `sprake`); `default` for the fallback.

    Returns:
        The button.
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
    """Create the navigation buttons of pages, and the button linking to the documentation.

    All registered pages unless `pages` lists those to show.

    Args:
        model_type: The model type (e.g. `sprake`); `default` for the fallback.
        pages: See the description.

    Returns:
        List of buttons.
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
    """Create the navigation bar.

    Args:
        model_type: The model type (e.g. `sprake`); `default` for the fallback.
        pages: See the description.

    Returns:
        The navigation bar.
    """
    return html.Div(
        create_navigator_buttons(model_type, pages),
        className = 'newsegs-navbar mt-1'
    )
