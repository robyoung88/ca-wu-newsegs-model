from abc import ABCMeta
from dataclasses import dataclass
from typing import Callable, Union

import dash

DashChildComponent = Union[str | dash.development.base_component.Component | list[str | dash.development.base_component.Component]]

@dataclass
class LayoutConfiguration:
    page_type: str
    model_type: str = 'default'

@dataclass
class Page():
    id: str
    nav_label: str
    nav_icon: DashChildComponent
    layout: Callable
    default_configuration: LayoutConfiguration
    attach_callbacks: Callable[[dash.Dash], None] = lambda x: None
