import json

from dash import ALL, ctx, Dash, Input, no_update, Output, Patch, State
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager

def add_result_timeseries_callbacks(app: Dash, acm: NewsegsBrowserCacheManager):

    @app.callback(
        Output('timeseries-graph-container', 'style'),
        Output('btn-show-timeseries', 'outline'),
        Output('store-selected-configuration', 'data', allow_duplicate = True),
        Input('btn-show-timeseries', 'n_clicks'),
        State('timeseries-graph-container', 'style'),
        State('store-selected-configuration', 'data'),
        prevent_initial_call = True
    )
    def toggle_timeseries_visibility(n_clicks, current_style, store_selected_configuration):
        NUP = no_update, no_update, no_update
        if n_clicks is None:
            return NUP

        if current_style.get('display') == 'none':
            r_containerstyle = {
                'display': 'block',
                #'height': '400px'
            }
            r_btnoutline = False
            r_ssc = store_selected_configuration
        else:
            r_containerstyle = {
                'display': 'none',
                #'height': '0px'
            }
            r_btnoutline = True
            r_ssc = no_update
        return r_containerstyle, r_btnoutline, r_ssc
    
    @app.callback(
        Output('graph-timeseries', 'figure', allow_duplicate = True),
        Input('trigger-postprocess-model-run', 'data'),
        Input('store-selected-configuration', 'data'),
        State('timeseries-graph-container', 'style'),
        prevent_initial_call = True
    )
    def show_model_timeseries(
        model_run_json,
        store_selected_configuration,
        container_style
    ):
        NUP = no_update
        if store_selected_configuration is None:
            return NUP
        
        if container_style.get('display') == 'none':
            return NUP
        
        if ctx.triggered_id == 'store-selected-configuration':
            model_id = json.loads(store_selected_configuration).get('model_id')
            if model_id is None:
                return NUP
            mdl = acm.models[model_id]
        elif ctx.triggered_id == 'trigger-postprocess-model-run':
            active_model_id = json.loads(store_selected_configuration).get('model_id')
            model_run = model_run_json
            do_continue = False
            if isinstance(model_run, list):
                for mr in model_run:
                    model_id = json.loads(mr).get('model_id')
                    if model_id == active_model_id:
                        do_continue = True
                        break
            elif isinstance(model_run, dict):
                model_id = model_run.get('model_id')
                if model_id == active_model_id:
                    do_continue = True
            else:
                model_id = json.loads(model_run).get('model_id')
                if model_id == active_model_id:
                    do_continue = True
            
            if not do_continue:
                return NUP
            mdl = acm.models[active_model_id]
        else:
            return NUP

        genr = mdl.get_generation_result()
        cs = mdl.get_consumption_storage_result()
        if genr is None or cs is None:
            return NUP

        df = (
            genr.meters_to_pandas()
            .join(cs.meters_to_pandas())
            .assign(
                gen_total = lambda df: df['wind_export'] + df['solar_export'],
                cons_total = lambda df: df['appliance_import'] + df['dhw_import'] + df['spaceheat_import'] + df['evcharge_import']
            )
            .loc[:, [
                'wind_export',
                'solar_export',
                'gen_total',
                'cons_total',
                'storage_import',
                'storage_export',
                'grid_import',
                'grid_export']]
            .rename(
                columns = {
                    'wind_export': 'Gen - Wind',
                    'solar_export': 'Gen - PV',
                    'gen_total': 'Gen - Total',
                    'cons_total': 'Cons - Total',
                    'storage_import': 'BESS - Imp.',
                    'storage_export': 'BESS - Exp.',
                    'grid_import': 'Grid - Imp',
                    'grid_export': 'Grid - Exp'
                }
            )
        )
        df2 = (
            cs.dsm_to_pandas()
            .rename(
                columns = {
                    'storage_soc': 'BESS - SoC'
                }
            )
        )

        #fig = px.line(df)

        fig = make_subplots(specs=[[{'secondary_y': True}]])
        df1_varnames = [
            'Gen - Wind',
            'Gen - PV',
            'Gen - Total',
            'Cons - Total',
            'BESS - Imp.',
            'BESS - Exp.',
            'Grid - Imp',
            'Grid - Exp'
        ]

        for vn in df1_varnames:
            fig.add_trace(
                go.Scattergl(
                    x = df.index,
                    y = df.loc[:,vn],
                    name = vn
                ),
                secondary_y = False
            )
        
        df2_varnames = [
            'BESS - SoC'
        ]
        for vn in df2_varnames:
            fig.add_trace(
                go.Scattergl(
                    x = df2.index,
                    y = df2.loc[:,vn],
                    name = vn
                ),
                secondary_y = True
            )
        
        fig.update_layout(
            height = 250,
            margin = {'l': 5, 'r': 5, 't': 5, 'b': 0},
            legend_y = 0,
            legend_yanchor = 'bottom'
        )
        return fig
    
    @app.callback(
        Output('graph-timeseries', 'figure', allow_duplicate=True),
        Input({'type': 'link-event-date', 'date': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def zoom_to_event(event_datetime_click):
        NUP = no_update
        if event_datetime_click is None:
            return NUP
        id = ctx.triggered
        if len(id) > 1:
            return NUP
        id = id[0]
        if id['value'] is None:
            return NUP
        
        try:
            pid = json.loads(id['prop_id'].rstrip('.n_clicks'))
        except json.JSONDecodeError:
            return NUP
        if pid['type'] != 'link-event-date':
            return NUP
        eventdate = pd.Timestamp(pid['date'], tz ='utc')
        window_start = eventdate - pd.Timedelta(days=0.5)
        window_end = eventdate + pd.Timedelta(days=1.5)
        fig_patch = Patch()
        fig_patch['layout']['xaxis'] = {'range': (window_start, window_end), 'autoscale': False}
        
        return fig_patch
    
    @app.callback(
        Output('graph-timeseries', 'figure', allow_duplicate=True),
        Input({'type': 'link-event-daterange', 'datetime_start': ALL, 'datetime_end': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def zoom_to_daterange(event_datetime_click):
        NUP = no_update
        if event_datetime_click is None:
            return NUP
        id = ctx.triggered
        if len(id) > 1:
            return NUP
        id = id[0]
        if id['value'] is None:
            return NUP
        
        try:
            pid = json.loads(id['prop_id'].rstrip('.n_clicks'))
        except json.JSONDecodeError:
            return NUP
        if pid['type'] != 'link-event-daterange':
            return NUP
        window_start = pd.Timestamp(pid['datetime_start'], tz ='utc') - pd.Timedelta(days=0.5)
        window_end = pd.Timestamp(pid['datetime_end'], tz ='utc') + pd.Timedelta(days=0.5)
        fig_patch = Patch()
        fig_patch['layout']['xaxis'] = {'range': (window_start, window_end), 'autoscale': False}
        
        return fig_patch

    return app
