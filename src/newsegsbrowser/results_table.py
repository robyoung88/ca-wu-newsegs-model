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
                className = get_icon('config-focus', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color = 'primary',
            id = {'type': 'config-focus-btn', 'index': config_index},
            outline = True if config_index > 1 else False,
        ),
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
        # This seems redundant with the copy functionality, so removing it for now
        #dbc.Row(
        #    dbc.Col([
        #        html.H2([
        #            html.I(className="bi bi-arrow-return-right text-secondary", style={"marginLeft":"1.0rem", "marginRight":"1.0rem"}),
        #            dbc.Button(html.I(className="bi bi-plus-circle"), color="primary", id='add-comparator-btn', outline=True, disabled=True, className="rounded-circle")
        #        ])
        #    ])
        #),
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
        if trig is None:
            return no_update
        trigger_index = trig['index']
        if config_name[trigger_index-1] is None:
            return no_update

        app.config_names[trigger_index-1] = config_name[trigger_index-1]
        return no_update

    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('n_active_conf', 'data', allow_duplicate = True),
        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),
        State('n_active_conf', 'data'),
        prevent_initial_call=True
    )
    def add_duplicate_config(n_clicks,n_active):
        # Add the selector as the penultimate row
        trig = ctx.triggered_id
        if trig is None or n_clicks is None:
            return no_update, no_update

        n_conf = json.loads(n_active).get('n', 1) + 1

        if trig['type'] == 'config-dup-btn':
            trigger_index = trig['index']

            if n_clicks[trigger_index-1] is None:
                return no_update, no_update
            
            app.config_names.append(app.config_names[trigger_index-1] + " Copy")
        
        else:
            return no_update, no_update

        patched_comparator_selector = Patch()
        patched_comparator_selector.append(
            create_single_configuration_selector_row(n_conf, app)
        )

        return (
            patched_comparator_selector,
            json.dumps({'n': n_conf})
        )  
    
    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('n_active_conf', 'data', allow_duplicate = True),
        Input({'type': 'config-remove-btn', 'index': ALL}, 'n_clicks'),
        State('n_active_conf', 'data'),
        State({'type': 'config-remove-btn', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def remove_config(n_clicks, n_active, ids):
        trig = ctx.triggered_id
        if trig is None:
            return no_update, no_update
        
        if trig['type'] == 'config-remove-btn':
            trigger_index = trig['index']
            if trigger_index == 1:
                return no_update, no_update
        else:
            return no_update, no_update

        # There are not necessarily as many "config-remove-btn" items
        # as there are trigger indices (or at least they may not go as
        # high). To check that the n_clicks for the triggered button is
        # not actually none, we need to deference its index to its position
        # in the n_clicks list.
        for i in range(len(n_clicks)):
            if ids[i].get('index') == trigger_index:
                nclick_i = i
                break
        if n_clicks[nclick_i] is None:
            return no_update, no_update
        
        # Pop the name, decrement the index, and update the children
        dropped = app.config_names.pop(trigger_index-1)
        # TODO: Drop the model and finance as appropriate
        n_conf = len(app.config_names)

        if n_conf > 1:
            contents = [create_single_configuration_selector_row(i, app) for i in range(2, n_conf+1)]
        else:
            contents = []
        return (
            contents,
            json.dumps({'n': n_conf})
        )

    @app.callback(
        Output({'type': 'config-focus-btn', 'index': ALL}, 'outline'),
        Input({'type': 'config-focus-btn', 'index': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def set_focussed_config(n_clicks):
        trig = ctx.triggered_id
        n_conf = len(app.config_names)
        if trig is None:
            return [no_update] * n_conf
        
        trigger_index = trig['index']
        # Should always be as many buttons as configurations, so can
        # use the index directly
        if n_clicks[trigger_index-1] is None:
            return [no_update] * n_conf

        # TODO: set the app focussed configuration here. Also trigger watchers
        
        return (
            [False if i == (trigger_index-1) else True for i in range(n_conf)]
        )

    return app
