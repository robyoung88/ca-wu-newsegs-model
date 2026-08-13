import base64
import copy
import json
import logging
from typing import cast, Any

from dash import ALL, ctx, Dash, Input, no_update, Output, Patch, State
from dash.exceptions import PreventUpdate
import pathvalidate

from newsegsmodelframework.util import jsonfuncs
from newsegsmodelapp.newsegsbrowser import common as browser
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager

logger = logging.getLogger(__name__)

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

def add_configuration_selection_callbacks(app: Dash, acm: NewsegsBrowserCacheManager) -> Dash:
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
        mm_working = cast(NewsegsMetaModel, acm.metamodels.get(w_conf['metamodel_id']))
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

            mm = acm.metamodels.get(ref_config['metamodel_id'])

            try:
                mm_dup = browser.duplicate_metamodel(
                    ref_config['metamodel_id'],
                    configurations,
                    acm
                )
            except (TypeError, ValueError) as e:
                logger.error(str(e))
                return NUP
            
            new_selected_config = None
            for idx, jconf in enumerate(configurations):
                conf = json.loads(jconf)
                if conf.get('metamodel_id') == mm_dup.id:
                    new_selected_config = conf
                    new_selected_config['config_index'] = idx
                    break
            
            if new_selected_config is not None:
                selected_config = new_selected_config
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
        
        browser.safe_remove_metamodel(dropped['metamodel_id'], configurations, acm)

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

        mm = acm.metamodels[config['metamodel_id']]
        odict = metamodel_to_dict(mm)

        fn = odict.get('config_name','metamodel_configuration') + ".json"
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

        cfg = config_jsons[trigger_index]
        ctype, cstr = cfg.split(',')
        cfg = json.loads(base64.b64decode(cstr))

        try:
            working_mm = browser.metamodel_from_configuration_file(
                cfg,
                working_conf,
                configurations,
                acm,
                overwrite_selected_config = True
            )
        except Exception as e:
            logger.error(e)
            return (
                configurations,
                no_update
            )
      
        if working_mm is None:
            return (
                configurations,
                no_update
            )
        
        selected_config = working_mm.to_config()
        configurations[trigger_index]  = json.dumps(selected_config)
        selected_config['config_index'] = trigger_index

        return (
            configurations,
            json.dumps(selected_config)
        )
    
    # DOWNLOAD RESULTS
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'det-download-confirm'},
                    'is_open'
                )
            },
            'download': {
                'datas': Output(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'det'},
                    'data'
                )
            },
            'toast': {
                'children': Output(
                    {'type': 'result-download-feedback-toast', 'page': ALL, 'key': 'det'},
                    'children'
                ),
                'is_opens': Output(
                    {'type': 'result-download-feedback-toast', 'page': ALL, 'key': 'det'},
                    'is_open'
                ),
            },
            'information': {
                'values': Output(
                    {'type': 'result-download-information', 'page': ALL, 'key': 'det'},
                    'data'
                ),
            }
        },
        inputs = {
            'results_download_button': {
                'n_clicks': Input({'type': 'results-download-btn', 'page': ALL, 'key': 'det'}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-btn', 'page': ALL, 'key': 'det-download-confirm'},
                    'n_clicks'
                )
                
            },
            'results_predownload_button': {
                'n_clicks': Input({'type': 'results-predownload-btn', 'page': 'model_configuration', 'key': ALL}, 'n_clicks'),
            },
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'det-download-confirm'},
                    'id'
                )
            },
            'options': {
                'values': State(
                    {'type': 'det-result-download-option', 'page': ALL, 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'det-result-download-option', 'page': ALL, 'key': ALL},
                    'id'
                )
            },
            'download': {
                'ids': State(
                    {'type': 'results-download-component', 'page': ALL, 'key': 'det'},
                    'id'
                )
            },
            'toast': {
                'ids':  State(
                    {'type': 'result-download-feedback-toast', 'page': ALL, 'key': 'det'},
                    'id'
                ),
            },
            'information': {
                'values': State(
                    {'type': 'result-download-information', 'page': ALL, 'key': 'det'},
                    'data'
                ),
                'ids': State(
                    {'type': 'result-download-information', 'page': ALL, 'key': 'det'},
                    'id'
                ),
            },
            'configurations': State('store-configurations', 'data'),
        },
        prevent_initial_call = True
    )
    def confirm_det_results_download(
        results_download_button,
        modal_close_button,
        results_predownload_button,
        modal,
        options,
        download,
        toast,
        information,
        configurations,
    ):
        
        n_modals = len(modal['ids'])
        n_downloads = len(download['ids'])
        n_toast = len(toast['ids'])
        n_information = len(information['ids'])
        rval: dict[str, Any] = dict(
            modal = dict(is_opens = [no_update] * n_modals),
            download = dict(datas = [no_update] * n_downloads),
            toast = dict(
                children = [no_update] * n_toast,
                is_opens = [no_update] * n_toast
            ),
            information = dict(
                values = [no_update] * n_information
            )
        )

        trig_id = ctx.triggered_id
        
        if trig_id is None:
            return rval
        trig_val = ctx.triggered
        if len(trig_val) > 1 or trig_val[0].get('value') is None:
            return rval
        
        match trig_id.get('type'):
            case 'results-predownload-btn':
                config_index_str = trig_id.get('key')
                rval['modal']['is_opens'] = [True] * n_modals
                rval['information']['values'] = [config_index_str] * n_information
                return rval
            case 'results-download-btn':
                rval['modal']['is_opens'] = [False] * n_modals
                if n_information == 0:
                    rval['toast']['children'] = ['Unable to determine configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                config_index_str = information['values'][0]
                if config_index_str is None:
                    rval['toast']['children'] = ['Unable to determine configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                config_index = int(str(config_index_str).lstrip('config-'))-1
                if config_index >= len(configurations):
                    rval['toast']['children'] = ['Configuration index out of range'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                
                config = json.loads(configurations[config_index])
                mm = acm.metamodels.get(config.get('metamodel_id'))
                if mm is None:
                    rval['toast']['children'] = ['Could not retrieve metamodel'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                
                if mm.model.dirty or mm.finance.dirty:
                    rval['toast']['children'] = ['Deterministic results not run for current configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                
                page = trig_id.get('page')
                
                opts = browser.get_options(
                    options['ids'],
                    options['values'],
                    page,
                    ['contents-option', 'format-option']
                )
                
                to_export = browser.export_results(
                    'det',
                    config,
                    acm,
                    opts.get('contents-option', 'result'),
                    opts.get('format-option', 'csv')
                )

                if to_export is None:
                    rval['toast']['children'] = ['Deterministic results not available for current configuration'] * n_toast
                    rval['toast']['is_opens'] = [True] * n_toast
                    return rval
                
                for idx, id in enumerate(download['ids']):
                    if id['page'] == page:
                        rval['download']['datas'][idx] = to_export
            case _:
                rval['modal']['is_opens'] = [False] * n_modals
        return rval

    return app
