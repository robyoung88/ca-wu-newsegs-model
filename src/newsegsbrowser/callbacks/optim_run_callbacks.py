"""
Callbacks for handling optimisation requests
"""

import json
import logging
from typing import Any, MutableMapping, cast

from dash import ALL, Dash, Input, Output, Patch, State, ctx, no_update

from newsegsbrowser import common as browser
from newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager
from newsegsbrowser.postprocess import postprocess_utils
from newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegssensitivity import optim

logger = logging.getLogger(__name__)

def add_optim_run_callbacks(app: Dash, acm: NewsegsBrowserCacheManager) -> Dash:
    @app.callback(
        output = {
            'plot': {
                'figures': Output(
                    {'type': 'plot', 'page': ALL, 'key': 'optim-marginal-statistic'},
                    'figure'
                )
            },
            'store': {
                'datas': Output(
                    {'type': 'store-optim-marginal-statistic-plot', 'page': ALL},
                    'data'
                )
            },
        },
        inputs = {
            'plot_button': {
                'n_clicks': Input(
                    {'type': 'optim-marginal-plot-button', 'section': ALL, 'key': ALL, 'subindex': ALL},
                    'n_clicks'
                )
            },
            'statistic_dropdown': {
                'values': Input(
                    {'type': 'optim-run-option', 'page': ALL, 'key': 'optim-marginal-statistic'},
                    'value'
                )
            }
        },
        state = {
            'plot': {
                'ids': State(
                    {'type': 'plot', 'page': ALL, 'key': 'optim-marginal-statistic'},
                    'id'
                )
            },
            'lower_bound': {
                'values': State(
                    {'type': 'input-optimbound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'input-optimbound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                ),
            },
            'upper_bound': {
                'values': State(
                    {'type': 'input-optimbound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'input-optimbound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                ),
            },
            'resolution': {
                'values': State(
                    {'type': 'input-optim-plotintervals', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'input-optim-plotintervals', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                ),
            },
            'store': {
                'datas': State(
                    {'type': 'store-optim-marginal-statistic-plot', 'page': ALL},
                    'data'
                )
            },
            'selected_configuration': State('store-selected-configuration', 'data'),
        },
        prevent_initial_call = True
    )
    def plot_marginal_statistic(
        plot_button,
        statistic_dropdown,
        plot,
        lower_bound,
        upper_bound,
        resolution,
        store,
        selected_configuration
    ):
        # print(ctx.triggered_id)

        n_figures = len(plot['ids'])
        n_stores = len(store['datas'])

        rval: dict[str, Any] = dict(
            plot = dict(figures = [no_update] * n_figures),
            store = dict(datas = [no_update] * n_stores)
        )
        if n_figures == 0:
            return rval
        
        trig_id = ctx.triggered_id
        if trig_id is None:
            return rval
        
        val = None
        for prop in ctx.triggered:
            pid = json.loads(prop['prop_id'].rsplit('.', 1)[0])
            if pid == trig_id:
                val = prop['value']
                break
        
        if val is None:
            return rval
        
        if len(lower_bound['ids']) == 0 or len(upper_bound['ids']) == 0 or len(resolution['ids']) == 0:
            logger.warning('No bounds or resolution input elements found')
            return rval

        selected_configuration = json.loads(selected_configuration)
        mm = acm.metamodels[selected_configuration.get('metamodel_id')]

        match trig_id.get('type'):
            case 'optim-marginal-plot-button':
                varid = f'{trig_id['section']}.{trig_id['key']}.{trig_id['subindex']}'
                rval['store']['datas'] = [varid] * len(store['datas'])
                
                stat = statistic_dropdown['values'][0]
            case 'dropdown-optim-statistic':
                if n_stores == 0:
                    return rval
                stat = val
                varid = store['datas'][0]
            case _:
                raise ValueError(f'Unrecognised trigger type: {trig_id}')         

        section, key, subindex = varid.rsplit('.', 3)

        lower = browser.get_variable_keyed_data(
            section, key, int(subindex), 
            lower_bound['ids'], lower_bound['values']
        )
        upper = browser.get_variable_keyed_data(
            section, key, int(subindex), 
            upper_bound['ids'], upper_bound['values']
        )
        res = browser.get_variable_keyed_data(
            section, key, int(subindex), 
            resolution['ids'], resolution['values']
        )

        if lower is None or upper is None or res is None:
            # TODO: Maybe give some feedback here?
            return rval

        if lower == upper:
            # TODO: Maybe give some feedback here?
            return rval
        if lower > upper:
            temp = lower
            lower = upper
            upper = temp
        
        res = int(res)
        if res <= 0:
            return rval
        if res > 20:
            # TODO: Feedback
            res = 20

        if mm.variables.get(varid) is None:
            # TODO: Feedback
            logger.error('variable not found: %s', varid)
            return rval

        plot_df = optim.evaluate_statistic_across_margin(
            mm, varid, stat, lower, upper, res
        )

        fig = optim.statistic_across_margin_plot(plot_df, mm)
        rval['plot']['figures'] = [fig] * n_figures

        return rval
    
    # Pre-run modal control
    @app.callback(
        output = {
            'modal': {
                'is_opens': Output(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'optim-run-confirm'},
                    'is_open'
                )
            }
        },
        inputs = {
            'optim_run_button': {
                'n_clicks': Input({'type': 'optim-run-btn', 'page': ALL}, 'n_clicks'),
            },
            'modal_close_button': {
                'n_clicks': Input(
                    {'type': 'modal-close-btn', 'page': ALL, 'key': 'optim-run-confirm'},
                    'n_clicks'
                )
            },
            'optim_prerun_button': {
                'n_clicks': Input({'type': 'optim-prerun-btn', 'page': ALL}, 'n_clicks'),
            }
        },
        state = {
            'modal': {
                'ids': State(
                    {'type': 'modal-confirm', 'page': ALL, 'key':'optim-run-confirm'},
                    'id'
                )
            }
        },
        prevent_initial_call = True
    )
    def confirm_optim_run(
        optim_run_button,
        modal_close_button,
        optim_prerun_button,
        modal,
    ):
        n_modals = len(modal['ids'])
        if n_modals == 0:
            return dict(modal = dict(is_opens = []))
        trig_id = ctx.triggered_id
        if trig_id is None:
            return dict(modal = dict(is_opens = [no_update] * n_modals))
        
        if trig_id.get('type') == 'optim-prerun-btn':
            return dict(modal = dict(is_opens = [True] * n_modals))
        else:
            return dict(modal = dict(is_opens = [False] * n_modals))
        
    @app.callback(
        output = {
            'prequeue': Output('prequeue-action-user', 'data', allow_duplicate = True),
            'toast': {
                'is_opens': Output(
                    {'type': 'feedback-toast', 'page': ALL, 'key': 'optim'}, 
                    'is_open', allow_duplicate = True
                ),
                'children': Output(
                    {'type': 'feedback-toast', 'page': ALL, 'key': 'optim'}, 
                    'children', allow_duplicate = True
                ),
            }
        },
        inputs = {
            'run_button': {
                'n_clicks': Input({'type': 'optim-run-btn', 'page': ALL}, 'n_clicks'),
            }
        },
        state = {
            'option': {
                'ids': State({'type': 'optim-run-option', 'page': ALL, 'key': ALL}, 'id'),
                'values': State({'type': 'optim-run-option', 'page': ALL, 'key': ALL}, 'value'),
            },
            'toggle': {
                'values': State(
                    {'type': 'toggle-optim-variable', 'section': ALL, 'key': ALL, 'subindex': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'toggle-optim-variable', 'section': ALL, 'key': ALL, 'subindex': ALL},
                    'id'
                ),
            },
            'lower_bound': {
                'values': State(
                    {'type': 'input-optimbound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'input-optimbound-lower', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                ),
            },
            'upper_bound': {
                'values': State(
                    {'type': 'input-optimbound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'input-optimbound-upper', 'section': ALL, 'key': ALL, 'subindex': ALL, 'parameter_index': ALL, 'vector_location': ALL},
                    'id'
                ),
            },
            'toast': {
                'ids': State(
                    {'type': 'feedback-toast', 'page': ALL, 'key': 'optim'}, 
                    'id'
                ),
            },
            'selected_configuration': State('store-selected-configuration', 'data')
        },
        prevent_initial_call = True
    )
    def start_optim_run(
        run_button,
        option,
        toggle,
        lower_bound,
        upper_bound,
        selected_configuration,
        toast
    ):
        n_toast = len(toast['ids'])
        rval: dict[str, Any] = {
            'prequeue': no_update, 
            'toast':{'is_opens':[no_update]*n_toast, 'children':[no_update]*n_toast}
        }
        trig_id = ctx.triggered_id
        if trig_id is None:
            return rval
        
        val = None
        for prop in ctx.triggered:
            pid = json.loads(prop['prop_id'].rsplit('.', 1)[0])
            if pid == trig_id:
                val = prop['value']
                break
        if val is None:
            return rval
        
        if selected_configuration is None:
            return rval
        selected_configuration = json.loads(selected_configuration)

        vars = {}
        for idx, include_ in enumerate(toggle['values']):
            if include_:
                id = toggle['ids'][idx]
                varid = f'{id['section']}.{id['key']}.{id['subindex']}'
                if not varid in vars.keys():
                    lower = browser.get_variable_keyed_data(
                        id['section'],id['key'], id['subindex'],
                        lower_bound['ids'], lower_bound['values']
                    )
                    upper = browser.get_variable_keyed_data(
                        id['section'],id['key'], id['subindex'],
                        upper_bound['ids'], upper_bound['values']
                    )
                    if lower is None or upper is None:
                        continue
                    if not lower < upper:
                        continue
                    vars[varid] = optim.OptimVariable(varid, lower = lower, upper = upper)

        if len(vars) == 0:
            rval['toast']['is_opens'] = [True] * n_toast
            rval['toast']['children'] = ['Optimisation not run - no variables selected with valid bounds']
            return rval
        
        page = trig_id.get('page')
        opts = browser.get_options(
            option['ids'],
            option['values'],
            page,
            ['optim-marginal-statistic', 'optim-method']
        )
        
        request = browser.optim_run_request(
            metamodel_id = selected_configuration.get('metamodel_id'), 
            debounce = False,
            variables = list(vars.values()),
            target = opts['optim-marginal-statistic'],
            method = opts['optim-method']
        )

        prequeue_patch = Patch()
        prequeue_patch.append(
            json.dumps(
                request.as_dict()
            )
        )
        rval['prequeue'] = prequeue_patch
        logger.info('patching metamodel process prequeue with %s', request.as_dict())
        return rval
    
    
    @app.callback(
        output = dict(
            toast = dict(
                is_opens = Output(
                    {'type': 'feedback-toast', 'page': ALL, 'key': 'optim'}, 
                    'is_open', allow_duplicate = True
                ),
                children = Output(
                    {'type': 'feedback-toast', 'page': ALL, 'key': 'optim'}, 
                    'children', allow_duplicate = True
                )
            ),
            selected_configuration = Output('store-selected-configuration', 'data', allow_duplicate = True),
            configurations = Output('store-configurations', 'data', allow_duplicate = True),
        ),
        inputs = dict(
            trigger = dict(
                values = Input({'type': 'trigger', 'page': ALL, 'key': 'optim-run-postprocess'}, 'data'),
                ids = State({'type': 'trigger', 'page': ALL, 'key': 'optim-run-postprocess'}, 'id'))
        ),
        state = dict(
            toast = dict(
                ids = State(
                    {'type': 'feedback-toast', 'page': ALL, 'key': 'optim'}, 
                    'id'
                )
            ),
            configurations = State('store-configurations', 'data')
        ),
        prevent_initial_call = True,
    )
    def handle_opt_complete(
        trigger,
        toast,
        configurations,
    ):
        n_toast = len(toast['ids'])
        rval: dict[str, Any] = dict(
            toast = dict(
                is_opens = [no_update] * n_toast,
                children = [no_update] * n_toast,
            ),
            selected_configuration = no_update,
            configurations = no_update
        )
        
        trig_id = ctx.triggered_id
        if trig_id is None:
            return rval
        
        val = None
        for prop in ctx.triggered:
            pid = json.loads(prop['prop_id'].rsplit('.', 1)[0])
            if pid == trig_id:
                val = prop['value']
                break
        
        if val is None or isinstance(val, float):
            return rval
        
        if isinstance(val, list):
            if len(val) > 1:
                logger.error('Handling > 1 optimisation result, trimming to last')
                val = val[-1]
            elif len(val) == 0:
                return rval
            else:
                val = val[0]

        process_request = json.loads(val)
        mm = cast(NewsegsMetaModel, acm.metamodels.get(process_request.get('metamodel_id')))
        if mm is None:
            logger.warning('Unable to recover metamodel after optimisation: %s', process_request.get('metamodel_id'))
            return rval
        result_id = postprocess_utils.get_optim_result_id(postprocess_utils.RESULT_CACHE_PREFIXES['optim_results'], mm.id)
        logger.info('Recovering result: %s', result_id)

        opt = acm.results.get(result_id)
        if opt is None:
            logger.warning('Unable to recover optimisation result: %s', result_id)
            rval['toast']['is_opens'] = [True] * n_toast
            rval['toast']['children'] = ['Optimisation has not returned a result'] * n_toast
            acm.remove_metamodel(mm.id, True)
            return rval
        
        if opt.success:
            rval['toast']['is_opens'] = [True] * n_toast
            rval['toast']['children'] = ['Optimisation was successful'] * n_toast

            # Add the metamodel to the config list and set it as the active configuration
            mm.name = mm.name + " - Opt"
            mm_dict = mm.to_config()
            configurations.append(json.dumps(mm_dict))
            rval['configurations'] = configurations

            mm_dict['config_index'] = len(configurations) - 1
            rval['selected_configuration'] = json.dumps(mm_dict)
        else:
            msg = f'Optimisation was not a success: {opt.message}' + \
                '\n Try again with a different method, variables or bounds.' + \
                str(opt)

            rval['toast']['is_opens'] = [True] * n_toast
            rval['toast']['children'] = [msg] * n_toast
            acm.remove_metamodel(mm.id, True)

        return rval
        
    return app

def optim_metamodel_process(
    set_progress,
    process_request: dict[str, Any],
    mm: NewsegsMetaModel,
    cache: MutableMapping[str, Any]
):
    vars = [optim.OptimVariable(**x) for x in process_request['variables']]
    opt = optim.run_optimisation(
        mm,
        vars,
        target = process_request.get('target'), # pyright: ignore[reportArgumentType]
        method = process_request.get('method') # pyright: ignore[reportArgumentType]
    )
    optim_result_id = postprocess_utils.assign_optim_results(mm, opt)
    cache[optim_result_id] = opt
