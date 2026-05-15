import json
import datetime
import copy
import base64

import pathvalidate

from dash import html, Patch, Input, Output, dcc, ALL, State, ctx, no_update
import dash_bootstrap_components as dbc

from src.util import jsonfuncs
from src.newsegsbrowser.common import get_icon
from src.newsegsmodel import sprakemodel
from src.newsegsfinance import sprakefinance

def config_to_dict(app, config_index: int | None = None):
    """
    Encapsulate a model and finance configuration in a dictionary.
    """
    if config_index is None:
        config_index = app.selected_config
    
    odict = {
        'config_name': app.config_names[config_index],
        'model_config': app.models[config_index].to_dict(),
        'finance_config': app.finances[config_index].to_dict(),
    }

    return odict

def config_from_dict(app, cfg, config_index: int | None = None):
    """
    Given a model and finance configuration, update the live config
    """
    if config_index is None:
        config_index = app.selected_config
    
    if config_index >= len(app.models) or config_index >= len(app.finances):
        return None
    
    nm = app.config_names[config_index] 
    app.config_names[config_index] = cfg.get('config_name', nm)

    try:
        app.models[config_index].sync_with_dict(cfg.get('model_config'))
    except ValueError as e:
        print(e)
        return False

    try:
        app.finances[config_index].sync_with_dict(cfg.get('finance_config'))
    except ValueError as e:
        print(e)
        return False
    
    app.finances[config_index].set_model(app.models[config_index])
    app.models[config_index].run()

    return True       

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

def create_config_selector_headerbutton(config_index, app = None):
    if app is not None and app.selected_config == (config_index - 1):
        do_outline = False
    else:
        do_outline = True

    contents = dbc.Button(
        html.I(
            className = get_icon('config-{}'.format(config_index), style_name = 'raw'),
            style={'display': 'inline'}
        ),
        color='primary',
        id = {'type': 'config-hdrfocus-btn', 'index': config_index},
        outline = do_outline
    )

    return contents

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
        is_selected = True
    else:
        config_name = app.config_names[config_index - 1]
        is_selected = app.selected_config == (config_index-1)
    
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
                className=get_icon('config-duplicate', style_name = 'raw'),
                style={'display': 'inline'}
            ),
            color="primary",
            id = {'type': 'config-dup-btn', 'index': config_index},
            outline=True,
            title = 'Duplicate configuration'
        ),
        dbc.Button(
            html.I(
                className = get_icon('config-download', style_name = 'raw'),
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
                            className = get_icon('config-upload', style_name = 'raw'),
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
                className = get_icon('results-download', style_name = 'raw'),
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
        
        html.Div([        
            create_single_configuration_selector_row(1),
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
        dcc.Download(id='download-config-json'),
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
        NUP = no_update
        trig = ctx.triggered_id
        if trig is None:
            return NUP
        if len(ctx.triggered) > 1:
            return NUP
        
        trigger_index = trig['index']
        if config_name[trigger_index-1] is None:
            return NUP

        app.config_names[trigger_index-1] = config_name[trigger_index-1]
        return NUP

    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('config-selector-hdrcontainer', 'children', allow_duplicate = True),
        Output('n_active_conf', 'data', allow_duplicate = True),
        Output('live-config-watcher', 'data', allow_duplicate = True),
        Output('model-run-watcher', 'data', allow_duplicate = True),
        Output({'type': 'config-focus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),
        State('n_active_conf', 'data'),
        State('model-run-watcher', 'data'),
        prevent_initial_call=True
    )
    def add_duplicate_config(n_clicks, n_active, mdl_run_hashes):
        # Add the selector as the penultimate row
        n_conf = len(app.config_names)
        NUP = (no_update, no_update, no_update, no_update, [no_update] * n_conf, [no_update] * n_conf)
        
        update_outlines = [True] * n_conf

        trig = ctx.triggered_id
        if trig is None or n_clicks is None:
            return NUP
        # After construction of a new button, ctx.triggered will contain
        # the full list, not just the triggering button, though the triggering id is arbitrary
        # Therefore reject if the list is longer than 1; if rejecting on first construction,
        # the above should catch
        if len(ctx.triggered) > 1:
            return NUP

        n_conf = json.loads(n_active).get('n', 1) + 1

        if trig['type'] == 'config-dup-btn':
            trigger_index = trig['index']

            if n_clicks[trigger_index-1] is None:
                return NUP

            app.config_names.append(app.config_names[trigger_index-1] + " Copy")
            mdl_ref = app.models[trigger_index - 1]
            mdl = sprakemodel.SprakeModel(mdl_ref)
            # Do a manual copy of results
            mdl._generation_result = copy.copy(mdl_ref._generation_result)
            mdl._grid_result = copy.copy(mdl_ref._grid_result)
            mdl._cs_result = copy.copy(mdl_ref._cs_result)
            mdl._dirty = False
            # We also want the cached functions to respond, so, at risk:
            mdl.last_run = mdl_ref.last_run
            #mdl._last_hash = mdl_ref._last_hash
            app.models.append(mdl)
            fnc = sprakefinance.SprakeFinance(app.finances[trigger_index - 1])
            fnc.set_model(app.models[-1])
            fnc._dirty = False
            app.finances.append(fnc)
            app.selected_config = n_conf-1

            if mdl_run_hashes is None:
                mdl_run_hashes = [None] * len(app.config_names)
            else:
                mdl_run_hashes = json.loads(mdl_run_hashes)
            
            mdl_run_hashes.append(hash(mdl))
            mdl_run_hashes = json.dumps(mdl_run_hashes)
        else:
            return NUP
        
        patched_comparator_selector = Patch()
        patched_comparator_selector.append(
            create_single_configuration_selector_row(n_conf, app)
        )

        patched_header_comparator_selector = Patch()
        patched_header_comparator_selector.append(
            create_config_selector_headerbutton(n_conf, app)
        )

        return (
            patched_comparator_selector,
            patched_header_comparator_selector,
            json.dumps({'n': n_conf}),
            json.dumps(str(datetime.datetime.now())),
            mdl_run_hashes,
            update_outlines,
            update_outlines
        )  
    
    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('config-selector-hdrcontainer', 'children', allow_duplicate = True),
        Output('n_active_conf', 'data', allow_duplicate = True),
        Input({'type': 'config-remove-btn', 'index': ALL}, 'n_clicks'),
        State('n_active_conf', 'data'),
        State({'type': 'config-remove-btn', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def remove_config(n_clicks, n_active, ids):
        NUP = (no_update, no_update, no_update)

        trig = ctx.triggered_id
        if trig is None:
            return NUP
        # After construction of a new button, ctx.triggered will contain
        # the full list, not just the triggering button, though the triggering id is arbitrary
        # Therefore reject if the list is longer than 1; if rejecting on first construction,
        # the above should catch
        if len(ctx.triggered) > 1:
            return NUP
        
        if trig['type'] == 'config-remove-btn':
            trigger_index = trig['index']
            if trigger_index == 1:
                return NUP
        else:
            return NUP

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
            return NUP
        
        # Pop the name, decrement the index, and update the children
        dropped = app.config_names.pop(trigger_index-1)
        if app.selected_config == trigger_index - 1:
            if app.selected_config > 0:
                app.selected_config -= 1
        app.finances.pop(trigger_index - 1)
        app.models.pop(trigger_index - 1)

        # TODO: Set the outline characteristics of the focus button if we go back to 0
        # TODO: Instruct app to update results tables

        n_conf = len(app.config_names)

        if n_conf > 0:
            contents = [create_single_configuration_selector_row(i, app) for i in range(1, n_conf+1)]
        else:
            contents = []

        hdr_contents = [create_config_selector_headerbutton(i, app) for i in range(1, n_conf + 1)]

        return (
            contents,
            hdr_contents,
            json.dumps({'n': n_conf})
        )

    @app.callback(
        Output({'type': 'config-focus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output('live-config-watcher', 'data', allow_duplicate = True),
        Output('model-run-watcher', 'data', allow_duplicate = True),
        Input({'type': 'config-focus-btn', 'index': ALL}, 'n_clicks'),
        Input({'type': 'config-hdrfocus-btn', 'index': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def set_focussed_config(n_clicks, n_clicks_hdr):
        n_conf = len(app.config_names)
        NUP = ([no_update] * n_conf, [no_update] * n_conf, no_update, no_update)
        
        trig = ctx.triggered_id
        if trig is None:
            return NUP
        # After construction of a new button, ctx.triggered will contain
        # the full list, not just the triggering button, though the triggering id is arbitrary
        # Therefore reject if the list is longer than 1; if rejecting on first construction,
        # the above should catch
        if len(ctx.triggered) > 1:
            return NUP

        trigger_index = trig['index']
        # Should always be as many buttons as configurations, so can
        # use the index directly
        if trig['type'] == 'config-focus-btn':
            if n_clicks[trigger_index-1] is None:
                return NUP
        elif trig['type'] == 'config-hdrfocus-btn':
            if n_clicks_hdr[trigger_index-1] is None:
                return NUP

        app.selected_config = trigger_index - 1
        
        return (
            [False if i == (trigger_index-1) else True for i in range(n_conf)],
            [False if i == (trigger_index-1) else True for i in range(n_conf)],
            json.dumps(str(datetime.datetime.now())),
            json.dumps(str(datetime.datetime.now()))
        )

    @app.callback(
        Output('download-config-json', 'data'),
        Input({'type': 'config-download-btn', 'index': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def download_config_json(n_clicks):
        NUP = no_update

        trig = ctx.triggered_id
        if trig is None:
            return NUP
        # After construction of a new button, ctx.triggered will contain
        # the full list, not just the triggering button, though the triggering id is arbitrary
        # Therefore reject if the list is longer than 1; if rejecting on first construction,
        # the above should catch
        if len(ctx.triggered) > 1:
            return NUP

        trigger_index = trig['index']
        
        if n_clicks[trigger_index-1] is None:
            return NUP
        
        odict = config_to_dict(app, trigger_index - 1)
        fn = odict.get('config_name') + ".json"
        fn = pathvalidate.sanitize_filename(fn)
        return dict(
            content = json.dumps(odict, cls = jsonfuncs.NumpyEncoder, sort_keys=False, indent=4), 
            filename = fn
        )

    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output('live-config-watcher', 'data', allow_duplicate = True),
        Output('model-run-watcher', 'data', allow_duplicate = True),
        Input({'type': 'config-upload', 'index': ALL}, 'contents'),
        prevent_initial_call = True
    )
    def upload_config_json(config_jsons):
        n_conf = len(app.config_names)
        NUP = (no_update, [no_update] * n_conf, no_update, no_update)

        trig = ctx.triggered_id
        if trig is None:
            return NUP
        # After construction of a new button, ctx.triggered will contain
        # the full list, not just the triggering button, though the triggering id is arbitrary
        # Therefore reject if the list is longer than 1; if rejecting on first construction,
        # the above should catch
        if len(ctx.triggered) > 1:
            return NUP
        
        trigger_index = trig['index']
        if config_jsons[trigger_index-1] is None:
            return NUP
        
        cfg = config_jsons[trigger_index - 1]
        ctype, cstr = cfg.split(',')
        cfg = json.loads(base64.b64decode(cstr))

        ok = config_from_dict(app, cfg, trigger_index-1)

        if not ok:
            return NUP
        
        contents = [create_single_configuration_selector_row(i, app) for i in range(1, n_conf+1)]

        return (
            contents,
            [False if i == (trigger_index-1) else True for i in range(n_conf)],
            json.dumps(str(datetime.datetime.now())),
            json.dumps(str(datetime.datetime.now()))
        )

    return app
