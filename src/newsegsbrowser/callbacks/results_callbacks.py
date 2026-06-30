import json

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

    return app