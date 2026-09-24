from __future__ import annotations

from abc import ABCMeta
from dataclasses import dataclass
from typing import Callable, Union

import dash

DashChildComponent = Union[str | dash.development.base_component.Component | list[str | dash.development.base_component.Component]]
ComponentType = dash.development.base_component.ComponentType

@dataclass
class LayoutConfiguration:
    page_type: str
    model_type: str = 'default'

@dataclass
class Page():
    id: str
    nav_label: str
    nav_icon: DashChildComponent
    layout: Callable[[LayoutConfiguration], ComponentType]
    default_configuration: LayoutConfiguration
    attach_callbacks: Callable[['NewsegsDash'], None] = lambda x: None # pyright: ignore[reportUndefinedVariable]
