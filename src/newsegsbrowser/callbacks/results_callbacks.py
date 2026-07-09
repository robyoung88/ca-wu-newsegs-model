import json
from typing import Any

from dash import ALL, Dash, Input, Output, State, no_update

from newsegsbrowser.callbacks import callbacks_map

def add_result_header_callbacks(app: Dash):

    @app.callback(
        Output({'type': 'result-header', 'section': ALL, 'key': ALL}, 'children', allow_duplicate = True),

        Input({'type': 'result-statistics', 'supersection': 'model-results', 'key': ALL}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State({'type': 'result-statistics', 'supersection': 'model-results', 'key': ALL}, 'id'),
        State({'type': 'result-header', 'section': ALL, 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True,
    )
    def update_model_result_headers(
        res_trigger,
        ann_hori_toggle,
        selected_config,
        result_trigger_ids,
        result_header_ids,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_model_result_headers'](
            res_trigger,
            ann_hori_toggle,
            selected_config,
            result_trigger_ids,
            result_header_ids,
            app
        )
    
    @app.callback(
        Output({'type': 'result-header', 'section': ALL, 'key': ALL}, 'children', allow_duplicate = True),

        Input({'type': 'result-statistics', 'supersection': 'finance-results', 'key': ALL}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State({'type': 'result-statistics', 'supersection': 'finance-results', 'key': ALL}, 'id'),
        State({'type': 'result-header', 'section': ALL, 'key': ALL}, 'id'),
        State('selected-model', 'data'),
        prevent_initial_call = True,
    )
    def update_finance_result_headers(
        res_trigger,
        ann_hori_toggle,
        selected_config,
        result_trigger_ids,
        result_header_ids,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_finance_result_headers'](
            res_trigger,
            ann_hori_toggle,
            selected_config,
            result_trigger_ids,
            result_header_ids,
            app
        )
    
    return app
    
def add_result_table_callbacks(app):
    """
    Functions to synchronise the results table with model/finance results.
    """

    @app.callback(
        Output({'type': 'results-table', 'section': 'generation', 'key': ALL}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'model-results', 'key': 'res-gen'}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State({'type': 'results-table', 'section': 'generation', 'key': ALL}, 'id'),
        State('store-configurations', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_gen_results_table_to_store(
        res_trigger,
        ann_hori_toggle,
        table_ids,
        store_configurations,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_gen_results_table_to_store'](
            res_trigger,
            ann_hori_toggle,
            table_ids,
            store_configurations,
            app
        )
    
    @app.callback(
        Output({'type': 'results-table', 'section': 'storage', 'key': ALL}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'model-results', 'key': 'res-stor'}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State({'type': 'results-table', 'section': 'storage', 'key': ALL}, 'id'),
        State('store-configurations', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_stor_results_table_to_store(
        res_trigger,
        ann_hori_toggle,
        table_ids,
        store_configurations,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_stor_results_table_to_store'](
            res_trigger,
            ann_hori_toggle,
            table_ids,
            store_configurations,
            app
        )
    
    @app.callback(
        Output({'type': 'results-table', 'section': 'consumption', 'key': ALL}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'model-results', 'key': 'res-cons'}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State({'type': 'results-table', 'section': 'consumption', 'key': ALL}, 'id'),
        State('store-configurations', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_cons_results_table_to_store(
        res_trigger,
        ann_hori_toggle,
        table_ids,
        store_configurations,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_cons_results_table_to_store'](
            res_trigger,
            ann_hori_toggle,
            table_ids,
            store_configurations,
            app
        )

    @app.callback(
        Output({'type': 'results-table', 'section': 'net', 'key': ALL}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'model-results', 'key': 'res-net'}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State({'type': 'results-table', 'section': 'net', 'key': ALL}, 'id'),
        State('store-configurations', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_net_results_table_to_store(
        res_trigger,
        ann_hori_toggle,
        table_ids,
        store_configurations,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_net_results_table_to_store'](
            res_trigger,
            ann_hori_toggle,
            table_ids,
            store_configurations,
            app
        )
    
    @app.callback(
        Output({'type': 'results-table', 'section': 'finance_so', 'key': ALL}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'finance-results', 'key': 'res-finance-so-benefits'}, 'data'),
        Input({'type': 'result-statistics', 'supersection': 'finance-results', 'key': 'res-finance-so-costs'}, 'data'),
        Input({'type': 'result-statistics', 'supersection': 'finance-results', 'key': 'res-finance-so-value'}, 'data'),
        Input('annual-horizon-toggle', 'value'),
        State({'type': 'results-table', 'section': 'finance_so', 'key': ALL}, 'id'),
        State('store-configurations', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def sync_fnc_so_table_to_store(
        ben_trigger,
        cost_trigger,
        value_trigger,
        ann_hori_toggle,
        table_ids,
        store_configurations,
        selected_model
    ):
        NUP = [no_update] * len(table_ids)

        if ben_trigger is None or cost_trigger is None or value_trigger is None:
            return NUP
        
        if not (ben_trigger == cost_trigger == value_trigger):
            return NUP
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_fnc_so_table_to_store'](
            ben_trigger,
            ann_hori_toggle,
            table_ids,
            store_configurations,
            app
        )
    
    # Update indicators above result section.
    # The finance results tables should be the last thing fired after a model
    # run, so using that as a trigger to check for status of the models is ok
    @app.callback(
        output = dict(
            result_indicator_values = dict(
                bars = Output(
                    {'type': 'resize-handle', 'page': ALL},
                    'className',
                    allow_duplicate = True,
                ),
                tooltips = Output(
                    {'type': 'result-tooltip', 'page': ALL},
                    'children',
                    allow_duplicate = True,
                )
            )
        ),

        inputs = dict(
            results_update_trigger = Input(
                {'type': 'result-statistics', 'supersection': 'finance-results',
                'key': 'res-finance-so-benefits'},
                'data'
            )
        ),

        state = dict(
            result_indicator_ids = dict(
                bars = State(
                    {'type': 'resize-handle', 'page': ALL},
                    'id'
                ),
                tooltips = State(
                    {'type': 'result-tooltip', 'page': ALL},
                    'id'
                ),
            ),
            configurations = State('store-configurations', 'data'),
        ),
        prevent_initial_call = True
    )
    def post_result_update_result_tooltip_model_conf(
        results_update_trigger,
        result_indicator_ids,
        configurations,
    ):
        """
        Update the model configuration result indicator header to show that the results are synced.
        """
        # print ('updating result header indicator')
        rval: dict[str, Any] = dict(
            result_indicator_values = dict(
                bars = [no_update] * len(result_indicator_ids['bars']),
                tooltips = [no_update] * len(result_indicator_ids['tooltips']),
            )
        )

        if (
            configurations is None 
            or len(configurations) == 0
            or results_update_trigger is None
        ):
            return rval
        
        model_conf_bar_idxs = [
            i for i, x in enumerate(result_indicator_ids['bars']) 
            if x['page'] in {'model_configuration'}
        ]
        model_conf_tooltip_idxs = [
            i for i, x in enumerate(result_indicator_ids['tooltips']) 
            if x['page'] in {'model_configuration'}
        ]

        if len(model_conf_bar_idxs) == len(model_conf_tooltip_idxs) == 0:
            return rval
        
        n_dirty_models = 0
        n_dirty_finances = 0
        for conf in configurations:
            conf_dict = json.loads(conf)
            mm = app.metamodels[conf_dict['metamodel_id']]
            n_dirty_models += int(mm.model.dirty)
            n_dirty_finances += int(mm.finance.dirty)
        
        if n_dirty_models != 0:
            for idx in model_conf_bar_idxs:
                rval['result_indicator_values']['bars'][idx] = 'resize-handle resize-handle-warning'
            for idx in model_conf_tooltip_idxs:
                rval['result_indicator_values']['tooltips'][idx] = f'{n_dirty_models} models require running'
        elif n_dirty_finances != 0:
            for idx in model_conf_bar_idxs:
                rval['result_indicator_values']['bars'][idx] = 'resize-handle resize-handle-warning'
            for idx in model_conf_tooltip_idxs:
                rval['result_indicator_values']['tooltips'][idx] = f'{n_dirty_finances} finances require running'
        else:
            for idx in model_conf_bar_idxs:
                rval['result_indicator_values']['bars'][idx] = 'resize-handle resize-handle-ok'
            for idx in model_conf_tooltip_idxs:
                rval['result_indicator_values']['tooltips'][idx] = 'Results updated'
        
        return rval

    @app.callback(
        Output({'type': 'result-table-container', 'page': ALL, 'key': 'dsa-results-table'}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'dsa-results', 'key': 'res-dsa-table'}, 'data'),
        Input({'type': 'dsa-results-statistic-dropdown', 'page': ALL}, 'value'),
        State({'type': 'result-table-container', 'page': ALL, 'key': 'dsa-results-table'}, 'id'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_dsa_results_table_to_store(
        dsa_table_trigger,
        dsa_statistic_dropdown_values,
        table_ids,
        selected_conf,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_dsa_results_table_to_store'](
            dsa_table_trigger,
            dsa_statistic_dropdown_values,
            table_ids,
            selected_conf,
            app
        )
    
    @app.callback(
        Output({'type': 'plot', 'page': ALL, 'key': 'dsa-tornado-plot'}, 'figure'),

        Input({'type': 'result-statistics', 'supersection': 'dsa-results', 'key': 'res-dsa-table'}, 'data'),
        Input({'type': 'dsa-results-statistic-dropdown', 'page': ALL}, 'value'),
        State({'type': 'plot', 'page': ALL, 'key': 'dsa-tornado-plot'}, 'id'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_dsa_tornado_to_store(
        dsa_table_trigger,
        dsa_statistic_dropdown_values,
        plot_ids,
        selected_conf,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_dsa_tornado_to_store'](
            dsa_table_trigger,
            dsa_statistic_dropdown_values,
            plot_ids,
            selected_conf,
            app
        )
    
    @app.callback(
        Output({'type': 'result-table-container', 'page': ALL, 'key': 'psa-results-table'}, 'children'),

        Input({'type': 'result-statistics', 'supersection': 'psa-results', 'key': 'res-psa-table'}, 'data'),
        State({'type': 'result-table-container', 'page': ALL, 'key': 'psa-results-table'}, 'id'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def sync_psa_results_table_to_store(
        psa_table_trigger,
        table_ids,
        selected_conf,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['sync_psa_results_table_to_store'](
            psa_table_trigger,
            table_ids,
            selected_conf,
            app
        )
    
    @app.callback(
        output = {
            'plot_header' : {
                'children': Output(
                    {'type': 'plot-header-container', 'page': ALL, 'key': 'psa-primary-plot'},
                    'children'
                )
            },
            'plot': {
                'figures' : Output(
                    {'type': 'plot', 'page': ALL, 'key': 'psa-primary-plot'},
                    'figure'
                )
            },
            'plot_container': {
                'children' : Output(
                    {'type': 'plot-container', 'page': ALL, 'key': 'psa-primary-plot'},
                    'children'
                )
            }
        },

        inputs = {
            'psa_table': {
                'trigger': Input(
                    {'type': 'result-statistics', 'supersection': 'psa-results', 'key': 'res-psa-table'},
                    'data'
                ),
            },
            'graph_selection_dropdown': {
                'values': Input(
                    {'type': 'psa-graph-selection-dropdown', 'page': ALL, 'key': 'psa-primary-plot'},
                    'value'
                ),
                'ids': State(
                    {'type': 'psa-graph-selection-dropdown', 'page': ALL, 'key': 'psa-primary-plot'},
                    'id'
                )
            },
            'plot_controls': {
                'values': Input(
                    {'type': 'psa-graph-plot-control', 'page': ALL, 'key': ALL},
                    'value'
                ),
                'ids': State(
                    {'type': 'psa-graph-plot-control', 'page': ALL, 'key': ALL},
                    'id'
                ),
            }
        },

        state = {
            'plot_header': {
                'ids': State(
                    {'type': 'plot-header-container', 'page': ALL, 'key': 'psa-primary-plot'},
                    'id'
                )
            },
            'plot': {
                'ids' : State(
                    {'type': 'plot', 'page': ALL, 'key': 'psa-primary-plot'},
                    'id'
                )
            },
            'plot_container': {
                'ids' : State(
                    {'type': 'plot-container', 'page': ALL, 'key': 'psa-primary-plot'},
                    'id'
                )
            },
            'selected_configuration': {
                'value': State('store-selected-configuration', 'data')
            },
            'selected_model': {
                'value': State('selected-model', 'data')
            }
        },

        prevent_initial_call = True
    )
    def sync_psa_primary_plot_to_store(
        psa_table,
        graph_selection_dropdown,
        plot_controls,
        plot_header,
        plot,
        plot_container,
        selected_configuration,
        selected_model,
    ):
        null_return = dict(
            plot_header = dict(children = [no_update] * len(plot_header['ids'])),
            plot = dict(figures = [no_update] * len(plot['ids'])),
            plot_container = dict(children = [no_update] * len(plot_container['ids'])),
        )

        return callbacks_map.CALLBACKS_MAP[selected_model['value']]['sync_psa_primary_plot_to_store'](
            psa_table,
            graph_selection_dropdown,
            plot_controls,
            plot_header,
            plot,
            plot_container,
            selected_configuration,
            app,
            null_return,
        )

    return app