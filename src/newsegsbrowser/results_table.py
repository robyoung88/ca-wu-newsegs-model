import json
import datetime
import copy
import base64
import uuid

import pathvalidate

from dash import html, Patch, Input, Output, dcc, ALL, State, ctx, no_update
from dash.exceptions import PreventUpdate
import dash_bootstrap_components as dbc

from src.util import jsonfuncs
from src.newsegsbrowser.common import get_icon
from src.newsegsmodel import sprakemodel
from src.newsegsfinance import sprakefinance

def config_to_dict(name, mdl: sprakemodel.SprakeModel, fnc: sprakefinance.SprakeFinance):
    """
    Encapsulate a model and finance configuration in a dictionary.
    """
    
    odict = {
        'config_name': name,
        'model_config': mdl.to_dict(),
        'finance_config': fnc.to_dict(),
    }

    return odict      

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
            className = get_icon('config-{}'.format(config_index+1), style_name = 'raw'),
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
    
    contents = [
        get_icon('config-'+str(config_index+1)),
    ]
    
    if configurations is None:
        config_name = 'Configuration Name'
    else:
        config_name = configurations[config_index]['name']
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
            create_single_configuration_selector_row(0),
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
        Output('store-configurations', 'data'),
        Output('store-selected-configuration', 'data'),
        Input({'type': 'config-name-input', 'index': ALL}, 'value'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def rename_config(config_name, configurations, selected_config):
        NUP = no_update
        trig = ctx.triggered_id
        if trig is None:
            return NUP
        if len(ctx.triggered) > 1:
            return NUP
        
        configurations = json.loads(configurations)
        selected_config = json.loads(selected_config)
        
        trigger_index = trig['index']
        if config_name[trigger_index] is None:
            return NUP
        
        configurations[trigger_index]['name'] = config_name[trigger_index]
        if selected_config['config_index'] == trigger_index:
            selected_config['name'] = config_name[trigger_index]
            rval = (json.dumps(configurations), json.dumps(selected_config))
        else:
            rval = (json.dumps(configurations), no_update)
        
        return rval

    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('config-selector-hdrcontainer', 'children', allow_duplicate = True),
        
        Output({'type': 'config-focus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),

        #Output('live-config-watcher', 'data', allow_duplicate = True),
        #Output('store-model-completed-run', 'data', allow_duplicate=True),

        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),

        Output('store-model-interface-configurations', 'data'),
        Output('store-finance-interface-configurations', 'data'),
        
        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),

        State('store-model-interface-configurations', 'data'),
        State('store-finance-interface-configurations', 'data'),

        prevent_initial_call=True
    )
    def add_duplicate_config(
        n_clicks, 
        configurations, 
        selected_config,
        store_model_interface_configurations,
        store_finance_interface_configurations
    ):
        # Add the selector as the penultimate row
        if configurations is None:
            raise PreventUpdate()
        
        configurations = json.loads(configurations)
        n_conf = len(configurations)

        NUP = (
            no_update, 
            no_update, 
            [no_update] * n_conf, 
            [no_update] * n_conf, 
            #no_update, 
            #no_update,
            no_update,
            no_update,
            no_update,
            no_update
        )
        
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

        n_conf += 1

        if store_model_interface_configurations is None:
            store_model_interface_configurations = {}
        else:
            store_model_interface_configurations = json.loads(
                store_model_interface_configurations
            )

        if store_finance_interface_configurations is None:
            store_finance_interface_configurations = {}
        else:
            store_finance_interface_configurations = json.loads(
                store_finance_interface_configurations
            )

        if trig['type'] == 'config-dup-btn':
            trigger_index = trig['index']

            if n_clicks[trigger_index] is None:
                return NUP

            # Make the copy
            ref_config = configurations[trigger_index]
            mdl = app.duplicate_model(ref_config['model_uuid'])
            fnc = app.duplicate_finance(ref_config['finance_uuid'])

            store_model_interface_configurations[mdl.uuid] = copy.copy(store_model_interface_configurations.get(ref_config['model_uuid']))
            store_model_interface_configurations[mdl.uuid]['model_uuid'] = mdl.uuid

            store_finance_interface_configurations[fnc.uuid] = copy.copy(store_finance_interface_configurations.get(ref_config['finance_uuid']))
            store_finance_interface_configurations[fnc.uuid]['finance_uuid'] = fnc.uuid

            # TODO: move compose_configuration to a utility module so it can be shared
            new_config = {
                'uuid': str(uuid.uuid4()),
                'name': ref_config['name'] + " Copy",
                'model_uuid': mdl.uuid,
                'finance_uuid': fnc.uuid
            }

            configurations.append(new_config)
            print('after append')
            print(configurations)
            selected_config = new_config.copy()
            selected_config['config_index'] = len(configurations) - 1

            # Let's copy over the results
            mdl_ref = app.get_model(ref_config['model_uuid'])
            mdl._generation_result = copy.copy(mdl_ref._generation_result)
            mdl.generation._dirty = False
            mdl._grid_result = copy.copy(mdl_ref._grid_result)
            mdl.grid._dirty = False
            mdl._cs_result = copy.copy(mdl_ref._cs_result)
            mdl.consumption_storage._dirty = False
            mdl._dirty = False
            
            # Because of the different uuid, the caches will not recognise this model,
            # or its finance, but just for info:
            mdl.last_run = mdl_ref.last_run
            print(f'model is duplicated from {mdl_ref.uuid} to {mdl.uuid} and dirty is {mdl.dirty}')

            fnc.model = mdl
            fnc._dirty = False

        else:
            return NUP
        
        # Now for all the UI stuff

        patched_comparator_selector = Patch()
        patched_comparator_selector.append(
            create_single_configuration_selector_row(
                n_conf-1, 
                configurations, 
                selected_config
            )
        )

        patched_header_comparator_selector = Patch()
        patched_header_comparator_selector.append(
            create_config_selector_headerbutton(
                n_conf-1, 
                selected_config
            )
        )

        #mdl_completed_run = json.dumps(
        #    {
        #        'model_uuid': mdl.uuid,
        #        'model_last_run': str(mdl.last_run),
        #        'model_hash': hash(mdl)
        #    }
        #)

        return (
            patched_comparator_selector,
            patched_header_comparator_selector,

            update_outlines,
            update_outlines,

            #json.dumps(str(datetime.datetime.now())),
            #mdl_completed_run,

            json.dumps(configurations),
            json.dumps(selected_config),

            json.dumps(store_model_interface_configurations),
            json.dumps(store_finance_interface_configurations)
        )  
    
    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('config-selector-hdrcontainer', 'children', allow_duplicate = True),
        
        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),

        #Output('n_active_conf', 'data', allow_duplicate = True),
        Input({'type': 'config-remove-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        #State('n_active_conf', 'data'),
        State({'type': 'config-remove-btn', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def remove_config(n_clicks, configurations, selected_config, ids):
        NUP = (no_update, no_update, no_update, no_update)

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
            if trigger_index == 0:
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

        configurations = json.loads(configurations)
        selected_config = json.loads(selected_config)
        dropped = configurations.pop(trigger_index)
        if selected_config['config_index'] == trigger_index:
            selected_config = configurations[trigger_index-1].copy()
            selected_config['config_index'] = trigger_index - 1
        
        safe_drop = True
        for conf in configurations:
            if conf['model_uuid'] == dropped['model_uuid']:
                safe_drop = False
        
        if safe_drop:
            app.remove_model(dropped['model_uuid'])
        
        safe_drop = True
        for conf in configurations:
            if conf['finance_uuid'] == dropped['finance_uuid']:
                safe_drop = False
        
        if safe_drop:
            app.remove_finance(dropped['finance_uuid'])

        n_conf = len(configurations)

        
        contents = [create_single_configuration_selector_row(i, configurations, selected_config) for i in range(n_conf)]
        hdr_contents = [create_config_selector_headerbutton(i, selected_config) for i in range(n_conf)]

        return (
            contents,
            hdr_contents,

            json.dumps(configurations),
            json.dumps(selected_config)
        )

    @app.callback(
        Output({'type': 'config-focus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        
        Output('store-model-completed-run', 'data', allow_duplicate = True),

        Output('store-selected-configuration', 'data', allow_duplicate = True),

        Input({'type': 'config-focus-btn', 'index': ALL}, 'n_clicks'),
        Input({'type': 'config-hdrfocus-btn', 'index': ALL}, 'n_clicks'),
        
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def set_focussed_config(n_clicks, n_clicks_hdr, configurations, selected_config):
        if configurations is None:
            raise PreventUpdate()
        
        configurations = json.loads(configurations)
        n_conf = len(configurations)
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
            if n_clicks[trigger_index] is None:
                return NUP
        elif trig['type'] == 'config-hdrfocus-btn':
            if n_clicks_hdr[trigger_index] is None:
                return NUP
        
        selected_config = json.loads(selected_config)
        if selected_config['config_index'] == trigger_index:
            return NUP
        
        selected_config = configurations[trigger_index].copy()
        selected_config['config_index'] = trigger_index

        mdl = app.get_model(selected_config['model_uuid'])

        mdl_completed_run = json.dumps(
            {
                'model_uuid': mdl.uuid,
                'model_last_run': str(mdl.last_run),
                'model_hash': hash(mdl)
            }
        )
        
        return (
            [False if i == (trigger_index) else True for i in range(n_conf)],
            [False if i == (trigger_index) else True for i in range(n_conf)],
            mdl_completed_run,
            json.dumps(selected_config)
        )

    @app.callback(
        Output('download-config-json', 'data'),
        Input({'type': 'config-download-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        prevent_initial_call = True
    )
    def download_config_json(n_clicks, configurations):
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
        
        if n_clicks[trigger_index] is None:
            return NUP

        config = json.loads(configurations)[trigger_index]


        mdl = app.get_model(config['model_uuid'])
        fnc = app.get_finance(config['finance_uuid'])
        
        odict = config_to_dict(config['name'], mdl, fnc)
        fn = odict.get('config_name') + ".json"
        fn = pathvalidate.sanitize_filename(fn)
        return dict(
            content = json.dumps(odict, cls = jsonfuncs.NumpyEncoder, sort_keys=False, indent=4), 
            filename = fn
        )

    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),

        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),
        
        Input({'type': 'config-upload', 'index': ALL}, 'contents'),
        State('store-configurations', 'data'),
        prevent_initial_call = True
    )
    def upload_config_json(config_jsons, configurations):
        if configurations is None:
            raise PreventUpdate()
        configurations = json.loads(configurations)
        n_conf = len(configurations)
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
        if config_jsons[trigger_index] is None:
            return NUP
        
        working_conf = configurations[trigger_index]
        mdl = app.get_model(working_conf['model_uuid'])
        fnc = app.get_finance(working_conf['finance_uuid'])

        cfg = config_jsons[trigger_index]
        ctype, cstr = cfg.split(',')
        cfg = json.loads(base64.b64decode(cstr))

        mdl.sync_with_dict(cfg['model_config'])
        fnc.sync_with_dict(cfg['finance_config'])
        working_conf['name'] = cfg['config_name']

        selected_config = working_conf.copy()
        selected_config['config_index'] = trigger_index
        configurations[trigger_index]  = selected_config
        
        contents = [create_single_configuration_selector_row(i, configurations, selected_config) for i in range(n_conf)]

        return (
            contents,
            [False if i == (trigger_index) else True for i in range(n_conf)],
            json.dumps(configurations),
            json.dumps(selected_config)
        )

    return app
