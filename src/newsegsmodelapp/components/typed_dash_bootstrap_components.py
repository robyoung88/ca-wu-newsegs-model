"""Forgiving typing for dash bootstrap components.

Gets rid of the Pylance errors being unable to resolve difference between module and function.
"""
from typing import Any

import dash_bootstrap_components as dbc

Button: Any = dbc.Button
Card: Any = dbc.Card
CardBody: Any = dbc.CardBody
Col: Any = dbc.Col
Collapse: Any = dbc.Collapse
Container: Any = dbc.Container
Input: Any = dbc.Input
InputGroup: Any = dbc.InputGroup
Navbar: Any = dbc.Navbar
Row: Any = dbc.Row
Select: Any = dbc.Select
