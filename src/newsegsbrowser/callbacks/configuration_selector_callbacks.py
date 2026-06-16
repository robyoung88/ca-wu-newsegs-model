import base64
import copy
import json

from dash import ALL, ctx, Dash, Input, no_update, Output, Patch, State
from dash.exceptions import PreventUpdate
import pathvalidate

from util import jsonfuncs
from newsegsbrowser import common as browser
from newsegsbrowser.layouts.results import configuration_selector
from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance

def config_to_dict(name, mdl: newsegsmodel.NewsegsModel, fnc: newsegsfinance.NewsegsFinance):
    """
    Encapsulate a model and finance configuration in a dictionary.
    """
    
    odict = {
        'config_name': name,
        'model_config': mdl.to_dict(),
        'finance_config': fnc.to_dict(),
    }

    return odict

def add_configuration_selection_callbacks(app: Dash):
    """
    Make the buttons on the configuration selector live.
    """
    @app.callback(
        Output('store-configurations', 'data', allow_duplicate = True),
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
        
        if configurations is None or selected_config is None:
            return NUP

        selected_config = json.loads(selected_config)
        
        trigger_index = trig['index']
        if config_name[trigger_index] is None:
            return NUP
        
        w_conf = json.loads(configurations[trigger_index])
        w_conf['name'] = config_name[trigger_index]
        configurations[trigger_index] = json.dumps(w_conf)
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

        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),

        Output('store-model-interface-configurations', 'data', allow_duplicate = True),
        Output('store-finance-interface-configurations', 'data', allow_duplicate = True),
        
        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),

        State('store-model-interface-configurations', 'data'),
        State('store-finance-interface-configurations', 'data'),

        State({'type': 'config-focus-btn', 'index': ALL}, 'id'),
        State({'type': 'config-hdrfocus-btn', 'index': ALL}, 'id'),

        prevent_initial_call=True
    )
    def add_duplicate_config(
        n_clicks, 
        configurations, 
        selected_config,
        store_model_interface_configurations,
        store_finance_interface_configurations,
        focus_btn_ids,
        header_focus_btn_ids
    ):
        # Add the selector as the penultimate row
        if configurations is None:
            raise PreventUpdate()
        
        n_conf = len(configurations)

        NUP = (
            no_update, 
            no_update, 
            [no_update] * len(focus_btn_ids), 
            [no_update] * len(header_focus_btn_ids), 
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
            ref_config = json.loads(configurations[trigger_index])
            mdl = app.duplicate_model(ref_config['model_id'])
            fnc = app.duplicate_finance(ref_config['finance_id'], mdl.id)

            store_model_interface_configurations[mdl.id] = copy.copy(
                store_model_interface_configurations.get(
                    ref_config['model_id']
                )
            )
            store_model_interface_configurations[mdl.id]['model_id'] = mdl.id

            store_finance_interface_configurations[fnc.id] = copy.copy(
                store_finance_interface_configurations.get(
                    ref_config['finance_id']
                )
            )
            store_finance_interface_configurations[fnc.id]['finance_id'] = fnc.id

            new_config = browser.compose_configuration(
                ref_config['name'] + " Copy",
                mdl,
                fnc,
            )

            configurations.append(json.dumps(new_config))
            
            selected_config = new_config.copy()
            selected_config['config_index'] = len(configurations) - 1

            # Let's copy over the results
            mdl_ref = app.models.get(ref_config['model_id'])
            mdl._generation_result = copy.copy(mdl_ref._generation_result)
            mdl.generation._dirty = False
            mdl._grid_result = copy.copy(mdl_ref._grid_result)
            mdl.grid._dirty = False
            mdl._cs_result = copy.copy(mdl_ref._cs_result)
            mdl.consumption_storage._dirty = False
            mdl._dirty = False
            
            # Because of the different uuid, the caches will not recognise this model,
            # or its finance, but just for info:
            print(f'model is duplicated from {mdl_ref.id} to {mdl.id} and dirty is {mdl.dirty}')

            fnc._dirty = False

        else:
            return NUP
        
        # Now for all the UI stuff

        patched_comparator_selector = Patch()
        patched_comparator_selector.append(
            configuration_selector.create_single_configuration_selector_row(
                n_conf-1,
                configurations,
                selected_config
            )
        )

        patched_header_comparator_selector = Patch()
        patched_header_comparator_selector.append(
            configuration_selector.create_config_selector_headerbutton(
                n_conf-1, 
                selected_config
            )
        )

        return (
            patched_comparator_selector,
            patched_header_comparator_selector,

            update_outlines,
            update_outlines,

            configurations,
            json.dumps(selected_config),

            json.dumps(store_model_interface_configurations),
            json.dumps(store_finance_interface_configurations)
        )  
    
    @app.callback(
        Output('comparator-selector-container', 'children', allow_duplicate = True),
        Output('config-selector-hdrcontainer', 'children', allow_duplicate = True),
        
        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),

        Input({'type': 'config-remove-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        
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

        if n_clicks[nclick_i] is None: # pyright: ignore[reportPossiblyUnboundVariable]
            return NUP

        selected_config = json.loads(selected_config)
        dropped = json.loads(configurations.pop(trigger_index))
        if selected_config['config_index'] == trigger_index:
            selected_config = json.loads(configurations[trigger_index-1])
            selected_config['config_index'] = trigger_index - 1
        
        safe_drop = True
        for conf in configurations:
            if json.loads(conf)['model_id'] == dropped['model_id']:
                safe_drop = False
        
        if safe_drop:
            app.remove_model(dropped['model_id'])
        
        safe_drop = True
        for conf in configurations:
            if json.loads(conf)['finance_id'] == dropped['finance_id']:
                safe_drop = False
        
        if safe_drop:
            app.remove_finance(dropped['finance_id'])

        n_conf = len(configurations)

        contents = [configuration_selector.create_single_configuration_selector_row(i, configurations, selected_config) for i in range(n_conf)]
        hdr_contents = [configuration_selector.create_config_selector_headerbutton(i, selected_config) for i in range(n_conf)]

        return (
            contents,
            hdr_contents,

            configurations,
            json.dumps(selected_config)
        )

    @app.callback(
        Output({'type': 'config-focus-btn', 'index': ALL}, 'outline', allow_duplicate = True),
        Output({'type': 'config-hdrfocus-btn', 'index': ALL}, 'outline', allow_duplicate = True),

        Output('store-selected-configuration', 'data', allow_duplicate = True),

        Input({'type': 'config-focus-btn', 'index': ALL}, 'n_clicks'),
        Input({'type': 'config-hdrfocus-btn', 'index': ALL}, 'n_clicks'),
        
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),

        State({'type': 'config-focus-btn', 'index': ALL}, 'id'),
        State({'type': 'config-hdrfocus-btn', 'index': ALL}, 'id'),

        prevent_initial_call = True
    )
    def set_focussed_config(
        n_clicks, 
        n_clicks_hdr, 
        configurations, 
        selected_config,
        focus_btn_ids,
        header_focus_btn_ids
        ):
        if configurations is None:
            raise PreventUpdate()
        
        n_conf = len(configurations)
        NUP = ([no_update] * len(focus_btn_ids), [no_update] * len(header_focus_btn_ids), no_update)
        
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
        
        selected_config = json.loads(configurations[trigger_index])
        selected_config['config_index'] = trigger_index
        
        return (
            [False if i == (trigger_index) else True for i in range(n_conf)],
            [False if i == (trigger_index) else True for i in range(n_conf)],
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

        config = json.loads(configurations[trigger_index])

        mdl = app.models.get(config['model_id'])
        fnc = app.finances.get(config['finance_id'])
        
        odict = config_to_dict(config['name'], mdl, fnc)
        fn = odict.get('config_name','model_configuration') + ".json"
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
        
        working_conf = json.loads(configurations[trigger_index])
        mdl = app.models.get(working_conf['model_id'])
        fnc = app.finances.get(working_conf['finance_id'])

        cfg = config_jsons[trigger_index]
        ctype, cstr = cfg.split(',')
        cfg = json.loads(base64.b64decode(cstr))

        mdl.sync_with_dict(cfg['model_config'])
        fnc.sync_with_dict(cfg['finance_config'])
        working_conf['name'] = cfg['config_name']

        selected_config = working_conf.copy()
        selected_config['config_index'] = trigger_index
        configurations[trigger_index]  = json.dumps(selected_config)
        
        contents = [configuration_selector.create_single_configuration_selector_row(i, configurations, selected_config) for i in range(n_conf)]

        return (
            contents,
            [False if i == (trigger_index) else True for i in range(n_conf)],
            configurations,
            json.dumps(selected_config)
        )

    return app
