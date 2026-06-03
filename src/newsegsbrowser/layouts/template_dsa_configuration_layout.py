"""
Functions for creating a deterministic sensitivity analysis layout
"""
from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser.layouts import navigation
from src.newsegsbrowser.layouts.common import NULL_LAYOUT

def create_dsa_header():
    return html.Div([
        dbc.Row([
            dbc.Col(
                html.H1(
                    [
                        'Deterministic Sensitivity Analysis',
                        html.Br(),
                        html.Span('Site: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'site-name'}),
                    ]
                )
            )
        ]),
        dbc.Row([
            dbc.Col([
                html.H2(
                    [
                        html.Span('Configuration: '),
                        html.Span(id = {'type': 'generic_text', 'section': 'any', 'key': 'configuration-name'})
                    ]
                )
            ])
        ])
    ])

DEFAULT_LAYOUT_DSA = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_head': create_dsa_header,
    'width_head': 11,

}

def create_dsa_layout(*args, **kwargs):
    config_dict = DEFAULT_LAYOUT_DSA.copy()
    config_dict.update(kwargs)

    header = dbc.Row([
        dbc.Col(
            html.Div(
                config_dict['layout_navigation']()
            ),
            class_name = 'newsegs-navbar-vertical collapsed',
            width = config_dict['width_navigation'],
        ),
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        )
    ])
    

    return dbc.Container(
        html.Div(
            [
                header,
                html.Hr(),
            ],
            
            #id = 'main-content-pane'
        ),
        fluid = True,
        #id = 'app-layout-wrapper'
    )