from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser.common import get_icon

def create_tbl_head(n_configs):
    return [
        html.Thead(
            html.Tr([
                html.Th(""),
                html.Th("")
            ] + [
                html.Th(get_icon(f'config-{x+1}')) for x in range(n_configs)
            ])
        )
    ]

def create_configuration_selector():
    return html.Div([
        dbc.Row([
        dbc.Col(
            html.H1([
                get_icon('config-1'),
                html.Span("Configuration Name", contentEditable="true", id='config-name-input', style={"padding": "10px"}),
                dbc.Button(html.I(className="bi bi-floppy", style={'display': 'inline'}), color="primary", id='config-save-btn', outline=True)                    
            ])
        )
    ]),
    dbc.Row(
        dbc.Col([
            html.H2([
                html.I(className="bi bi-arrow-return-right text-secondary", style={"marginLeft":"1.0rem", "marginRight":"1.0rem"}),
                dbc.Button(html.I(className="bi bi-plus-circle"), color="primary", id='add-comparator-btn', outline=True, disabled=True, className="rounded-circle")
            ])
            
        ],
        id='comparator-selector-container')
    )])
