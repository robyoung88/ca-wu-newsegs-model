"""
Create a landing layout for an app.
"""
from dash import dcc, html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsmodelapp.components import navigation
from newsegsmodelapp.newsegsbrowser.layouts import common as clayouts, layout_registry
from newsegsmodelapp.registers import register_page_layout

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
    ],
    width = config_dict['width_body']
    ) # pyright: ignore[reportCallIssue]
    
    assumptions = dbc.Col([
        dbc.Row(html.H4('Model block diagram')), # pyright: ignore[reportCallIssue]
        dbc.Row(
        # Make the image fill the column width responsively but not expand beyond it
            html.Img(
                src=config_dict['model_diagram'],
                style={
                    'width': '100%',
                    'height': 'auto',
                    'objectFit': 'contain',
                    'display': 'block'
                }
            ),
        ), # pyright: ignore[reportCallIssue]
        dbc.Row(
            dcc.Markdown(config_dict['assumptions_text']),
        ), # pyright: ignore[reportCallIssue]
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

@register_page_layout('landing')
def _create_landing_layout(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_landing_layout(
        **layout_registry.get_landing_layout_config(
            selected_model
        )
    )
