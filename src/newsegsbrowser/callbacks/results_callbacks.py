import json

from dash import ALL, Dash, Input, Output, State, no_update

from src.newsegsbrowser.callbacks import callbacks_map

def add_result_header_callbacks(app: Dash):

    @app.callback(
        Output('gen-ressmry-container', 'children'),
        Input('res-gen', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def update_generation_results_header(
        res_trigger,
        ann_hori_toggle,
        selected_config,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_generation_results_header'](
            res_trigger,
            ann_hori_toggle,
            selected_config,
            app
        )
    
    @app.callback(
        Output('stor-ressmry-container', 'children'),
        Input('res-stor', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def update_storage_results_header(
        res_trigger,
        ann_hori_toggle,
        selected_config,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_storage_results_header'](
            res_trigger,
            ann_hori_toggle,
            selected_config,
            app
        )
    
    @app.callback(
        Output('cons-ressmry-container', 'children'),
        Input('res-cons', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def update_consumption_results_header(
        res_trigger,
        ann_hori_toggle,
        selected_config,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_consumption_results_header'](
            res_trigger,
            ann_hori_toggle,
            selected_config,
            app
        )
    
    @app.callback(
        Output('net-ressmry-container', 'children'),
        Input('res-net', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def update_net_results_header(
        res_trigger,
        ann_hori_toggle,
        selected_config,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_net_results_header'](
            res_trigger,
            ann_hori_toggle,
            selected_config,
            app
        )
    
    @app.callback(
        Output('finance-ressmry-container', 'children'),
        Input('res-finance-so-benefits', 'data'),
        Input('res-finance-so-costs', 'data'),
        Input('res-finance-so-value', 'data'),
        Input('annual-horizon-toggle', 'value'),
        State('store-selected-configuration', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call=True
    )
    def update_finance_results_header(
        res_benefits_trigger,
        res_costs_trigger,
        res_value_trigger,
        ann_hori_toggle,
        selected_config,
        selected_model
    ):
        return callbacks_map.CALLBACKS_MAP[selected_model]['update_finance_results_header'](
            res_benefits_trigger,
            res_costs_trigger,
            res_value_trigger,
            ann_hori_toggle,
            selected_config,
            app
        )
    
    return app
    
def add_result_table_callbacks(app):
    """
    Functions to synchronise the results table with model/finance results.
    """

    @app.callback(
        Output({'type': 'results-table', 'section': 'generation', 'key': ALL}, 'children'),
        Input('res-gen', 'data'),
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
        Input('res-stor', 'data'),
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
        Input('res-cons', 'data'),
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
        Input('res-net', 'data'),
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
        Input('res-finance-so-benefits', 'data'),
        Input('res-finance-so-costs', 'data'),
        Input('res-finance-so-value', 'data'),
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

    return app