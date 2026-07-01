import json

from dash import dcc, html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons

def create_config_selector_headerbutton(
    config_index,
    selected_config = None
):
    if selected_config is not None and selected_config['config_index'] == config_index:
        do_outline = False
    else:
        do_outline = True

    contents = dbc.Button(
        html.I(
            className = icons.get_icon('config-{}'.format(config_index+1), style_name = 'raw'),
            style={'display': 'inline'}
        ),
        color='primary',
        id = {'type': 'config-hdrfocus-btn', 'index': config_index},
        outline = do_outline
    )

    return contents

def create_single_configuration_selector_row(
    config_index, 
    configurations = None,
    selected_config = None):
    if config_index < 1:
        primary_container = html.H1
        show_remove = False
    else:
        primary_container = html.H2
        show_remove = True
    
    contents = list(
        icons.get_icon('config-'+str(config_index+1)),
    )
    
    if configurations is None:
        config_name = 'Configuration Name'
    else:
        config_name = json.loads(configurations[config_index])['name']
    if selected_config is None:
        is_selected = True
    else:
        is_selected = selected_config['config_index'] == config_index
    
    if config_name == 'Configuration Name':
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
                className = icons.get_icon('config-focus', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color = 'primary',
            id = {'type': 'config-focus-btn', 'index': config_index},
            outline = not(is_selected),
            title = 'Focus configuration',
        ),
        # temporarily disabling save until we get the database back-end
        #dbc.Button(
        #    html.I(
        #        className="bi bi-floppy",
        #        style={'display': 'inline'}
        #    ),
        #    color="primary",
        #    id = {'type': 'config-save-btn', 'index': config_index},
        #    outline=True,
        #    title = 'Save configuration',
        #),
        dbc.Button(
            html.I(
                className = icons.get_icon('config-duplicate', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color="primary",
            id = {'type': 'config-dup-btn', 'index': config_index},
            outline=True,
            title = 'Duplicate configuration'
        ),
        dbc.Button(
            html.I(
                className = icons.get_icon('config-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color='secondary',
            id = {'type': 'config-download-btn', 'index': config_index},
            outline = True,
            title = 'Download configuration as json'
        ),
        html.Span(
            html.Span(
                dcc.Upload(
                    dbc.Button(
                        html.I(
                            className = icons.get_icon('config-upload', style_name = 'raw'),
                            style = {'display': 'inline'}
                        ),
                        color='secondary',
                        id = {'type': 'config-upload-btn', 'index': config_index},
                        outline = True,
                        title = 'Overwrite configuration with uploaded json',
                        #style = {
                        #    'margin-top': '10px'
                        #}
                    ),
                    id = {'type': 'config-upload', 'index': config_index},
                    multiple = False,
                    enable_folder_selection = False,
                    accept = '.json',
                ),
                style = {
                    'display': 'inline',
                    'float': 'left'
                },
            ),
            style = {'display': 'inline-block', 'vertical-align': 'top',},
        ),
        
        dbc.Button(
            html.I(
                className = icons.get_icon('results-download', style_name = 'raw'),
                style = {'display': 'inline'}
            ),
            color='secondary',
            id = {'type': 'results-download-btn', 'index': config_index},
            outline = True,
            title = 'Download results as spreadsheet'
        ),
    ]

    if show_remove:
        contents.append(
            dbc.Button(
                html.I(
                    className = icons.get_icon('config-remove', style_name = 'raw'),
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
        
        html.Div([        
            create_single_configuration_selector_row(0),
        ],
        id='comparator-selector-container',
        ),
        dcc.Download(id='download-config-json'),
        dcc.Store(id='n_active_conf', data = '{"n": 1}')
    ])