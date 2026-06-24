"""
Functions for creating a deterministic sensitivity analysis layout
"""
import os
import json
from typing import cast

from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import STATICDATA
from newsegsbrowser.layouts import navigation
from newsegsbrowser.layouts.common import NULL_LAYOUT
from newsegsbrowser.layouts import common as clayouts
from newsegsbrowser import variable_dash_component as var_dc
from newsegsvariable import variable

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

def create_dsa_configuration_editor():
    return dbc.Col([
        html.Div([
            html.H2(
                'DSA Configuration',
                style = {'display': 'inline-flex',
                         'margin-right': '20px'}
            ),
            dbc.Button('Run DSA'),
            ],
            style = {'vertical-align': 'baseline'}
            ),
        html.Div(
            id = {'type': 'input-container', 'supersection': 'dsa', 'section': 'dsa'}
        )
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
                config_dict['layout_navigation'](config_dict.get('selected_model'))
            ),
            class_name = 'newsegs-navbar-vertical collapsed',
            width = config_dict['width_navigation'],
        ),
        dbc.Col(
            config_dict['layout_head'](),
            width = config_dict['width_head']
        )
    ])

    dsa_config = create_dsa_configuration_editor()
    
    print ('making dsa page')
    print (kwargs.get('selected_model'))
    print (kwargs.get('page_type'))

    return dbc.Container(
        html.Div(
            ([
                header,
                html.Hr(),
                dbc.Row(
                    dsa_config
                ),
            ] 
            + clayouts.user_action_components()
            + clayouts.model_run_components()
            + clayouts.finance_run_components()
            + clayouts.metamodel_process_components()
            + clayouts.post_page_load_components(
                kwargs.get('selected_model'),
                kwargs.get('page_type')
                )
            ),
            
            
            id = 'main-content-pane'
        ),
        fluid = True,
        id = 'app-layout-wrapper'
    )