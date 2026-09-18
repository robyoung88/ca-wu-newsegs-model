from typing import Any

import dash
import dash_bootstrap_components as dbc
from dash import html

from newsegsmodelapp.newsegsbrowser.layouts import layout_registry
from newsegsmodelapp.registers import register_page_layout

dbc_Container: Any = dbc.Container
dbc_Button: Any = dbc.Button
dbc_Card: Any = dbc.Card
dbc_CardBody: Any = dbc.CardBody
Div: Any = html.Div

def create_fourpane_layout(*args, **kwargs):
    return dbc_Container(
        [
            # Block A1: Left Pane Header
            html.Div(
                [
                    html.H4("Config Header", className="m-0"),
                    dbc_Button("Apply", color="primary", size="sm"),
                ],
                className="pane-header header-a1 bg-light p-3 border-bottom d-flex justify-content-between align-items-center",
            ),
            # Block C: Right Pane Header
            html.Div(
                [
                    html.H4("Results Header", className="m-0"),
                    dbc_Button("Export", color="secondary", outline=True, size="sm"),
                ],
                className="pane-header header-b1 bg-light p-3 border-bottom d-flex justify-content-between align-items-center",
            ),
            # Block B: Left Pane Content (Scrollable)
            html.Div(
                [
                    html.H6("Configuration Options"),
                    *[
                        dbc_Card(
                            dbc_CardBody(f"Configuration Option {i}"),
                            className="mb-3",
                        )
                        for i in range(1, 25)
                    ],
                ],
                className="pane-content content-a2 p-3 bg-white",
            ),
            # Block D: Right Pane Content (Scrollable)
            html.Div(
                [
                    html.H6("Generated Results"),
                    *[
                        dbc_Card(
                            dbc_CardBody(f"Result Item {i}"), className="mb-3"
                        )
                        for i in range(1, 25)
                    ],
                ],
                className="pane-content content-b2 p-3 bg-white",
            ),
        ],
        fluid=True,
        className="dash-container p-0",
    )

@register_page_layout('layout')
def _(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_fourpane_layout(
        **layout_registry.get_layout_layout_config(selected_model)
    )
