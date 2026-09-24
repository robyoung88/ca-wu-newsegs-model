from typing import Any

import dash
from dash import html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_fourpane_layout(*args, **kwargs):
    return dbc.Container(
        [
            # Block A1: Left Pane Header
            html.Div(
                [
                    html.H4("Config Header", className="m-0"),
                    dbc.Button("Apply", color="primary", size="sm"),
                ],
                className="pane-header header-a1 bg-light p-3 border-bottom d-flex justify-content-between align-items-center",
            ),
            # Block C: Right Pane Header
            html.Div(
                [
                    html.H4("Results Header", className="m-0"),
                    dbc.Button("Export", color="secondary", outline=True, size="sm"),
                ],
                className="pane-header header-b1 bg-light p-3 border-bottom d-flex justify-content-between align-items-center",
            ),
            # Block B: Left Pane Content (Scrollable)
            html.Div(
                [
                    html.H6("Configuration Options"),
                    *[
                        dbc.Card(
                            dbc.CardBody(f"Configuration Option {i}"),
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
                        dbc.Card(
                            dbc.CardBody(f"Result Item {i}"), className="mb-3"
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
