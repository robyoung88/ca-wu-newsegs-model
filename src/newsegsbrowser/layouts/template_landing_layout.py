"""
Create a landing layout for an app.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc

from src.newsegsbrowser.layouts import navigation

def create_landing_header():
    return html.H1('A NewSEGS model')

DEFAULT_LAYOUT_CONFIGURATION = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_head': create_landing_header,
    'width_head': 11,
    'body_text': 'Some text',
    'assumptions_text': '#Assumptions\nSome assumptions text',
    'model_type': 'default'
}

def create_landing_layout(*args, **kwargs):

    config_dict = DEFAULT_LAYOUT_CONFIGURATION.copy()
    config_dict.update(kwargs)

    header = dbc.Row([
        dbc.Col(
            config_dict['layout_navigation'](),
            width = config_dict['width_navigation'],
            class_name = 'newsegs-navbar-vertical flex-shrink-1',
        ),
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        )
    ])

    body = dbc.Row([
        dbc.Col([
            dcc.Markdown(config_dict['body_text'])
        ])
    ])

    assumptions = dbc.Row([
        dbc.Col([
            dcc.Markdown(config_dict['assumptions_text']),
            
            f'The model type is {config_dict["model_type"]}',
            #dcc.Store(id = 'store-selected-configuration'),
        ])
    ])

    return html.Div([
        header,
        html.Hr(),
        body,
        html.Hr(),
        assumptions
    ])
