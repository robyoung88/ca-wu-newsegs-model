import base64
import copy
import json
from typing import cast, Any

from dash import ALL, ctx, Dash, Input, no_update, Output, Patch, State
from dash.exceptions import PreventUpdate
import pathvalidate

from util import jsonfuncs
from newsegsbrowser import common as browser
from newsegsbrowser.layouts.results import configuration_selector
from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance
from newsegsmetamodel import NewsegsMetaModel

def metamodel_to_dict(mm: NewsegsMetaModel) -> dict[str, Any]:
    """
    Encapsulate a model and finance configuration in a dictionary.
    """
    odict = {
        'config_name': mm.name,
        'metamodel': mm.to_dict(),
        'model': mm.model.to_dict(),
        'finance': mm.finance.to_dict()
    }
    return odict

def add_configuration_selection_callbacks(app: Dash):
    """
    Make the buttons on the configuration selector live.
    """

    # RENAME
    @app.callback(
        Input({'type': 'config-name-input', 'index': ALL}, 'value'),
        
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call=True
    )
    def rename_config(config_name, configurations, selected_config):
        NUP = None#no_update
        trig = ctx.triggered_id
        if trig is None:
            return NUP
        if len(ctx.triggered) > 1:
            return NUP
        
        if configurations is None or selected_config is None:
            return NUP
        
        trigger_index = trig['index']
        if config_name[trigger_index] is None:
            return NUP
        
        w_conf = json.loads(configurations[trigger_index])
        mm_working = cast(NewsegsMetaModel, app.metamodels.get(w_conf['metamodel_id']))
        if mm_working is None:
            raise ValueError(f'selected metamodel cannot be located: {w_conf['metamodel_id']}')

        mm_working.name = config_name[trigger_index]
        # Do not update configurations to prevent a circular callback - rely on sync_config to
        # do the work and beware accessing names directly from configurations
        
        return None
    
    # DUPLICATE
    @app.callback(
        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),
        
        Input({'type': 'config-dup-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),

        prevent_initial_call=True
    )
    def add_duplicate_config(
        n_clicks, 
        configurations,
        selected_config,
    ):
        # Add the selector as the penultimate row
        if configurations is None:
            raise PreventUpdate()
        
        n_conf = len(configurations)

        NUP = (
            no_update,
            no_update,
        )

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

        if trig['type'] == 'config-dup-btn':
            trigger_index = trig['index']

            if n_clicks[trigger_index] is None:
                return NUP

            # Make the copy
            ref_config = json.loads(configurations[trigger_index])
            
            mm_dup = cast(NewsegsMetaModel, app.duplicate_metamodel(ref_config['metamodel_id']))
            mdl = mm_dup.model
            fnc = mm_dup.finance

            mm_dup.name = mm_dup.name + " Copy"
            new_config = mm_dup.to_config()

            configurations.append(json.dumps(new_config))
            
            selected_config = new_config.copy()
            selected_config['config_index'] = len(configurations) - 1

            # Let's copy over the results
            mdl_ref = app.models.get(ref_config['model_id'])
            if hasattr(mdl_ref, '_generation_result'):
                mdl._generation_result = copy.copy(mdl_ref._generation_result) # pyright: ignore[reportAttributeAccessIssue]
                mdl.generation._dirty = False
            if hasattr(mdl_ref, '_grid_result'):
                mdl._grid_result = copy.copy(mdl_ref._grid_result) # pyright: ignore[reportAttributeAccessIssue]
                mdl.grid._dirty = False
            if hasattr(mdl_ref, '_cs_result')    :
                mdl._cs_result = copy.copy(mdl_ref._cs_result) # pyright: ignore[reportAttributeAccessIssue]
                mdl.consumption_storage._dirty = False
            mdl._dirty = False
            
            # Because of the different uuid, the caches will not recognise this model,
            # or its finance, but just for info:
            print(f'model is duplicated from {mdl_ref.id} to {mdl.id} and dirty is {mdl.dirty}')

            fnc._dirty = False

        else:
            return NUP

        return (
            configurations,
            json.dumps(selected_config),
        )  
    
    # REMOVE
    @app.callback(
        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),

        Input({'type': 'config-remove-btn', 'index': ALL}, 'n_clicks'),
        State('store-configurations', 'data'),
        State('store-selected-configuration', 'data'),
        
        State({'type': 'config-remove-btn', 'index': ALL}, 'id'),
        prevent_initial_call=True
    )
    def remove_config(
        n_clicks, 
        configurations, 
        selected_config, 
        ids
    ):
        NUP = (
            no_update, 
            no_update
        )

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

        # Always safe to drop the metamodel, just don't necessarily remove the children
        app.remove_metamodel(dropped['metamodel_id'], False)

        return (
            configurations,
            json.dumps(selected_config)
        )

    # FOCUS
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

    # DOWNLOAD CONFIG
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

        mm = app.models.get(config['metamodel_id'])
        odict = metamodel_to_dict(mm)

        fn = odict.get('config_name','model_configuration') + ".json"
        fn = pathvalidate.sanitize_filename(fn)
        
        return dict(
            content = json.dumps(odict, cls = jsonfuncs.NumpyEncoder, sort_keys=False, indent=4), 
            filename = fn
        )

    # UPLOAD CONFIG
    @app.callback(
        Output('store-configurations', 'data', allow_duplicate = True),
        Output('store-selected-configuration', 'data', allow_duplicate = True),
        
        Input({'type': 'config-upload', 'index': ALL}, 'contents'),
        State('store-configurations', 'data'),
        prevent_initial_call = True
    )
    def upload_config_json(config_jsons, configurations):
        if configurations is None:
            raise PreventUpdate()
        NUP = (
            no_update, 
            no_update
        )

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

        working_mm = app.metamodel.get(working_conf['metamodel_id'])
        mdl = working_mm.model
        fnc = working_mm.finance

        cfg = config_jsons[trigger_index]
        ctype, cstr = cfg.split(',')
        cfg = json.loads(base64.b64decode(cstr))

        mm_id = working_mm.id
        mdl_id = mdl.id
        fnc_id = fnc.id
        working_mm.update(cfg['metamodel'])
        mdl.update(cfg['model'])
        fnc.update(cfg['finance'])
        
        # Caution - this will invalidate the results
        working_mm.id = mm_id
        mdl.id = mdl_id
        fnc.id = fnc_id
        fnc.set_model(mdl)
        working_mm.model = mdl
        working_mm.finance = fnc
        
        selected_config = working_mm.to_config()
        configurations[trigger_index]  = json.dumps(selected_config)
        selected_config['config_index'] = trigger_index

        return (
            configurations,
            json.dumps(selected_config)
        )

    return app
