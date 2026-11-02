"""Types of the pages of the app: `Page` and `LayoutConfiguration`.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Union

import dash

DashChildComponent = Union[str | dash.development.base_component.Component | list[str | dash.development.base_component.Component]]
ComponentType = dash.development.base_component.ComponentType

@dataclass
class LayoutConfiguration:
    """Settings that control how a page layout is drawn for a model type.

    Pages subclass this to add their own settings; the layout function of the page is
    called with the configuration registered for the model type being displayed.
    """
    page_type: str
    model_type: str = 'default'

@dataclass
class Page():
    """A page of the app.

    Attributes:
        id: Last element of the page URL (`/{model_type}/{id}`).
        nav_label: Title of the page's navigation button.
        nav_icon: Content of the page's navigation button.
        layout: Function returning the page content for a layout configuration.
        default_configuration: Configuration used for model types without their own.
        attach_callbacks: Called once when the app is created to bind the page's callbacks.
    """
    id: str
    nav_label: str
    nav_icon: DashChildComponent
    layout: Callable[[LayoutConfiguration], ComponentType]
    default_configuration: LayoutConfiguration
    attach_callbacks: Callable[['NewsegsDash'], None] = lambda x: None # pyright: ignore[reportUndefinedVariable]
