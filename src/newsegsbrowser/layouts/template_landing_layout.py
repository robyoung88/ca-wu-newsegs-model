"""
Create a landing layout for an app.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc
from dash_extensions import Mermaid

from newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsbrowser.layouts import navigation
from newsegsbrowser.layouts import common as clayouts

def create_landing_header(**kwargs):
    return html.H1(kwargs.get('head_text', ''))

DEFAULT_LAYOUT_CONFIGURATION = {
    'layout_navigation': navigation.create_navigator_buttons_default,
    'width_navigation': 1,
    'layout_head': create_landing_header,
    'width_head': 11,
    'width_body': 6,
    'width_assumptions': 6,
    'head_text': 'A NewSEGS model',
    'body_text': 'Some text',
    'model_diagram': '',
    'assumptions_text': '# Assumptions\nSome assumptions text',
    'model_type': 'default'
}

def create_landing_layout(*args, **kwargs):

    config_dict = DEFAULT_LAYOUT_CONFIGURATION.copy()
    config_dict.update(kwargs)

    header = dbc.Row([
        dbc.Col(
            config_dict['layout_navigation'](config_dict.get('selected_model','')),
            width = config_dict['width_navigation'],
            class_name = 'newsegs-navbar-vertical flex-shrink-1',
        ), # pyright: ignore[reportCallIssue]
        dbc.Col(
            config_dict['layout_head'](**kwargs),
            width = config_dict['width_head']
        ) # pyright: ignore[reportCallIssue]
    ])

    body = dbc.Col([
        dcc.Markdown(config_dict['body_text']),
        Mermaid(chart = config_dict['model_diagram']),
    ],
    width = config_dict['width_body']
    ) # pyright: ignore[reportCallIssue]
    
    assumptions = dbc.Col([
        dcc.Markdown(config_dict['assumptions_text']),
        
        f'The model type is {config_dict["model_type"]}',
        #dcc.Store(id = 'store-selected-configuration'),
    ]) # pyright: ignore[reportCallIssue]

    return html.Div(
        [
            header,
            html.Hr(),
            dbc.Container([
                dbc.Row([
                    body,
                    
                    assumptions
                ]), # pyright: ignore[reportCallIssue]
            ]) # pyright: ignore[reportCallIssue]
        ]
        + background_callback_error_handler_components()
        + clayouts.user_action_components()
        + clayouts.model_run_components(**kwargs)
        + clayouts.finance_run_components(**kwargs)
        + clayouts.metamodel_process_components()
    )
