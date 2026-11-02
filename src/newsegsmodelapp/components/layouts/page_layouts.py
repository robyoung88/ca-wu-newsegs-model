"""Layouts of whole pages.
"""
from typing import Union

import dash
from dash import html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

DashComponent = Union[str | dash.development.base_component.Component | list[str|dash.development.base_component.Component]]

def fourpane_layout(
    a1_contents: DashComponent,
    b1_contents: DashComponent,
    a2_contents: DashComponent,
    b2_contents: DashComponent,
):
    """The four-pane layout of the pages: two panes, each with a header.

    Args:
        a1_contents: Contents of the header of the left pane.
        b1_contents: Contents of the header of the right pane.
        a2_contents: Contents of the left pane.
        b2_contents: Contents of the right pane.

    Returns:
        The layout.
    """
    return dbc.Container(
        [
            # Block A1: Left Pane Header
            html.Div(
                a1_contents,
                className="pane-header header-a1 bg-light px-3 pt-0 pb-1 border-bottom d-flex justify-content-between align-items-start",
            ),
            # Block B1: Right Pane Header
            html.Div(
                b1_contents,
                className="pane-header header-b1 bg-light px-3 pt-0 pb-1 border-bottom d-flex justify-content-between align-items-start",
            ),
            # Block A2: Left Pane Content (Scrollable)
            html.Div(
                a2_contents,
                className="pane-content content-a2 p-3 bg-white",
            ),
            # Block B2: Right Pane Content (Scrollable)
            html.Div(
                b2_contents,
                className="pane-content content-b2 p-3 bg-white",
            ),
        ],
        fluid=True,
        className="dash-container p-0",
    )
