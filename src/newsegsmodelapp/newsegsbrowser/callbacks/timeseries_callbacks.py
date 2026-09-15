import json
import time

from dash import ALL, ctx, Dash, Input, no_update, Output, Patch, State
from dash.exceptions import PreventUpdate
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from plotly_resampler import FigureResampler

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash

resampler = FigureResampler(make_subplots(specs=[[{"secondary_y": True}]]))

def add_result_timeseries_callbacks(app: NewsegsDash):
    resampler.register_update_graph_callback(
        app=app,
        graph_id="graph-timeseries",
    )


    @app.callback(
        Output('timeseries-graph-container', 'style'),
        Output('btn-show-timeseries', 'outline'),
        Output({
            'type': 'postaction-trigger', 'purpose': 'manualtrigger',
            'supersection': 'global', 'section': 'tabledraw',
            'key': 'timeseriesupdate', 'subindex': 0
        }, 'data'),
        Input('btn-show-timeseries', 'n_clicks'),
        State('timeseries-graph-container', 'style'),
        State('active-project-id', 'data'),
        prevent_initial_call = True
    )
    def toggle_timeseries_visibility(n_clicks, current_style, active_project_id):
        if n_clicks is None:
            raise PreventUpdate

        if current_style.get('display') == 'none':
            r_containerstyle = {
                'display': 'block',
            }
            r_btnoutline = False
        else:
            r_containerstyle = {
                'display': 'none',
            }
            r_btnoutline = True
        return r_containerstyle, r_btnoutline, time.time_ns()
    
    @app.callback(
        Output('graph-timeseries', 'figure', allow_duplicate = True),

        Input({
            'type': 'postaction-trigger', 'purpose': 'manualtrigger',
            'supersection': 'global', 'section': 'tabledraw',
            'key': 'timeseriesupdate', 'subindex': 0
        }, 'data'),
        Input({
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': 'tabledraw',
            'key': 'table_generation', 'subindex': 0
        }, 'data'),

        Input('active-project-id', 'data'),
        State('timeseries-graph-container', 'style'),

        prevent_initial_call = True
    )
    def show_model_timeseries(
        trigger_1,
        trigger_2,
        active_project_id,
        container_style
    ):
        if active_project_id is None:
            raise PreventUpdate

        
        if container_style.get('display') == 'none':
            raise PreventUpdate

        proj = app.project_provider.get_project(active_project_id)
        mm = proj.get_focussed_metamodel()
        try:
            _ = mm.model.get_grid_result()
        except AttributeError:
            mm.model.reattach_results(app.results_provider)

        mdl = mm.model

        genr = mdl.get_generation_result()
        cs = mdl.get_consumption_storage_result()
        if genr is None or cs is None:
            raise PreventUpdate

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

        fig = FigureResampler(
            make_subplots(specs=[[{'secondary_y': True}]])
        )

        fig.register_update_graph_callback(app, 'graph-timeseries')
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
                   
                    name = vn
                ),
                hf_x = df.index,
                hf_y = df.loc[:,vn],
                secondary_y = False
            )
        
        df2_varnames = [
            'BESS - SoC'
        ]
        for vn in df2_varnames:
            fig.add_trace(
                go.Scattergl(  
                    name = vn
                ),
                hf_x = df2.index,
                hf_y = df2.loc[:,vn],
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
        Output('graph-timeseries', 'relayoutData', allow_duplicate=True),
        Input({'type': 'link-event-date', 'date': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def zoom_to_event(event_datetime_click):

        triggered_id = ctx.triggered_id
        if triggered_id is None or isinstance(triggered_id, str):# or not callback_utils.get_triggered_value(): # n_clicks does not seem to be held
            raise PreventUpdate

        eventdate = pd.Timestamp(triggered_id['date'], tz ='utc')
        window_start = eventdate - pd.Timedelta(days=0.5)
        window_end = eventdate + pd.Timedelta(days=1.5)
        #fig_patch = Patch()
        #fig_patch['layout']['xaxis'] = {'range': (window_start, window_end), 'autoscale': False}
        return {
            'xaxis.range[0]': window_start,
            'xaxis.range[1]': window_end
        }
        return fig_patch
    
    @app.callback(
        Output('graph-timeseries', 'relayoutData', allow_duplicate=True),
        Input({'type': 'link-event-daterange', 'datetime_start': ALL, 'datetime_end': ALL}, 'n_clicks'),
        prevent_initial_call = True
    )
    def zoom_to_daterange(event_datetime_click):

        triggered_id = ctx.triggered_id
        if triggered_id is None or isinstance(triggered_id, str):# or not callback_utils.get_triggered_value():
            raise PreventUpdate

        window_start = pd.Timestamp(triggered_id['datetime_start'], tz ='utc') - pd.Timedelta(days=0.5)
        window_end = pd.Timestamp(triggered_id['datetime_end'], tz ='utc') + pd.Timedelta(days=0.5)
        
        return {
            'xaxis.range[0]': window_start,
            'xaxis.range[1]': window_end
        }
        # fig_patch = Patch()
        # fig_patch['layout']['xaxis'] = {'range': (window_start, window_end), 'autoscale': False}
        
        # return fig_patch

    return app
