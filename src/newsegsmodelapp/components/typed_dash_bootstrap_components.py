"""Forgiving typing for dash bootstrap components.

Gets rid of the Pylance errors being unable to resolve difference between module and function.
"""
from typing import Any

import dash_bootstrap_components as dbc

Badge: Any = dbc.Badge
Button: Any = dbc.Button
Card: Any = dbc.Card
CardBody: Any = dbc.CardBody
Col: Any = dbc.Col
Collapse: Any = dbc.Collapse
Container: Any = dbc.Container
Input: Any = dbc.Input
InputGroup: Any = dbc.InputGroup
Modal: Any = dbc.Modal
ModalBody: Any = dbc.ModalBody
ModalFooter: Any = dbc.ModalFooter
ModalHeader: Any = dbc.ModalHeader
ModalTitle: Any = dbc.ModalTitle
Navbar: Any = dbc.Navbar
Progress: type[dbc._components.Progress]  = dbc.Progress
Row: Any = dbc.Row
Select: Any = dbc.Select
Switch: Any = dbc.Switch
Table: Any = dbc.Table
Toast: Any = dbc.Toast
Tooltip: Any = dbc.Tooltip
