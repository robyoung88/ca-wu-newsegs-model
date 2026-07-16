"""
Callbacks for handling optimisation requests
"""

import json
import logging
from typing import Any

from dash import ALL, Dash, Input, Output, State, ctx, no_update

from newsegsbrowser import common as browser
from newsegssensitivity import opt

logger = logging.getLogger(__name__)

def add_opt_run_callbacks(app: Dash):
    @app.callback(
        output = {
            'plot': {
                'figures': Output(
                    {'type': 'plot', 'page': ALL, 'key': 'opt-marginal-statistic'},
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
                    {'type': 'dropdown-opt-statistic', 'page': ALL, 'key': 'opt-marginal-statistic'},
                    'value'
                )
            }
        },
        state = {
            'plot': {
                'ids': State(
                    {'type': 'plot', 'page': ALL, 'key': 'opt-marginal-statistic'},
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
            plot = dict(
                figures = [no_update] * n_figures
            ),
            store = dict(
                datas = [no_update] * n_stores
            )
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
        mm = app.metamodels.get(selected_configuration.get('metamodel_id'))

        match trig_id.get('type'):
            case 'optim-marginal-plot-button':
                varid = f'{trig_id['section']}.{trig_id['key']}.{trig_id['subindex']}'
                rval['store']['datas'] = [varid] * len(store['datas'])
                
                stat = statistic_dropdown['values'][0]
            case 'dropdown-opt-statistic':
                if n_stores == 0:
                    return rval
                stat = val
                varid = store['datas'][0]
            case _:
                raise ValueError(f'Unrecognised trigger type: {trig_id}')         

        section, key, subindex = varid.rsplit('.', 3)
        print (varid)

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

        print (lower, upper, res)

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

        print (mm.variables.get(varid))

        if mm.variables.get(varid) is None:
            # TODO: Feedback
            logger.error('variable not found: %s', varid)
            return rval

        plot_df = opt.evaluate_statistic_across_margin(
            mm, varid, stat, lower, upper, res
        )

        fig = opt.statistic_across_margin_plot(plot_df, mm)
        rval['plot']['figures'] = [fig] * n_figures

        return rval
        
    return app
