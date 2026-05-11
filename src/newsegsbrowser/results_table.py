import json

from dash import html, Patch, Input, Output, dcc, ALL, State, ctx, no_update
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

def create_single_configuration_selector_row(config_index, app = None):
    if config_index < 2:
        primary_container = html.H1
        show_remove = False
    else:
        primary_container = html.H2
        show_remove = True
    
    contents = [
        get_icon('config-'+str(config_index)),
    ]
    
    if app is None:
        config_name = 'Configuration Name'
    else:
        config_name = app.config_names[config_index - 1]
    
    if config_index < 2 and config_name == 'Configuration Name':
        contents.append(
            dcc.Input(
                placeholder = config_name,
                debounce = True,
                type = 'text',
                id = {'type': 'config-name-input', 'index': config_index},
                size = '20',
                style = {
                    "display": "inline",
                    "border": "none",
                    "outline": "none",
                    "padding": "5px 0",
                    "height": "auto",
                    "lineHeight": "1.5",
                    "background": "transparent" # Blends into page
                }
            )
        )
    else:
        contents.append(
            dcc.Input(
                value = config_name,
                debounce = True,
                type = 'text',
                id = {'type': 'config-name-input', 'index': config_index},
                size = '20',
                style = {
                    "display": "inline",
                    "border": "none",
                    "outline": "none",
                    "padding": "5px 0",
                    "height": "auto",
                    "lineHeight": "1.5",
                    "background": "transparent" # Blends into page
                }
            )
        )
    
    contents += [
        dbc.Button(
            html.I(
                className="bi bi-floppy",
                style={'display': 'inline'}
            ),
            color="primary",
            id = {'type': 'config-save-btn', 'index': config_index},
            outline=True,
        ),
        dbc.Button(
            html.I(
                className=get_icon('config-duplicate', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color="primary",
            id = {'type': 'config-dup-btn', 'index': config_index},
            outline=True,
        )
    ]

    if show_remove:
        contents.append(
            dbc.Button(
                html.I(
                    className=get_icon('config-remove', style_name = 'raw'),
                    style={'display': 'inline'}
                ),
                color="primary",
                id={'type': 'config-remove-btn', 'index': config_index},
                outline=True,
            )
        )
    
    return (
        dbc.Row([
            dbc.Col([
                primary_container(
                    contents
                )
            ])
        ],
        id={'type':'comparator-conf-row', 'index': config_index},
        )
    )

def create_configuration_selector():
    return html.Div([
        create_single_configuration_selector_row(1),
        html.Div([        
        ],
        id='comparator-selector-container',
        ),
        dbc.Row(
            dbc.Col([
                html.H2([
                    html.I(className="bi bi-arrow-return-right text-secondary", style={"marginLeft":"1.0rem", "marginRight":"1.0rem"}),
                    dbc.Button(html.I(className="bi bi-plus-circle"), color="primary", id='add-comparator-btn', outline=True, disabled=True, className="rounded-circle")
                ])
            ])
        ),
        dcc.Store(id='n_active_conf', data = '{"n": 1}')
    ])

def add_configuration_selection_callbacks(app):
    """
    Make the buttons on the configuration selector live.
    """
    @app.callback(
        Output('n_active_conf', 'data', allow_duplicate = True),
        Input({'type': 'config-name-input', 'index': ALL}, 'value'),
        prevent_initial_call=True
    )
    def rename_config(config_name):
        trig = ctx.triggered_id
        trigger_index = trig['index']

        app.config_names[trigger_index-1] = config_name[trigger_index-1]
        return no_update

    @app.callback(
        Output('comparator-selector-container', 'children'),
        Output('n_active_conf', 'data', allow_duplicate = True),
        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),
        State('n_active_conf', 'data'),
        prevent_initial_call=True
    )
    def add_duplicate_config(n_clicks,n_active):
        # Add the selector as the penultimate row
        n_conf = json.loads(n_active).get('n', 1) + 1
        
        trig = ctx.triggered_id
        if trig['type'] == 'config-dup-btn':
            trigger_index = trig['index']
            
            app.config_names.append(app.config_names[trigger_index-1] + " Copy")
        

        patched_comparator_selector = Patch()
        patched_comparator_selector.append(
            create_single_configuration_selector_row(n_conf, app)
        )

        return (
            patched_comparator_selector,
            json.dumps({'n': n_conf})
        )  
    return app
