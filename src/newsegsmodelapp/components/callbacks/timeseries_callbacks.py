import logging
logger = logging.getLogger(__name__)
import time
from typing import cast

from dash import ALL, ctx, Input, no_update, Output, Patch, State
from dash.exceptions import PreventUpdate
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go
from plotly_resampler import FigureResampler

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.dash_extension import NewsegsDash


resampler = FigureResampler(make_subplots(specs=[[{"secondary_y": True}]]))
_resampler_model_id = None
"""Id of the model whose results are currently held by `resampler`"""

def _zoom_window(zoom: dict) -> list[str]:
    """
    The x-axis range around a zoomable result cell's {'start'[, 'end']}, as naive
    datetime strings; plotly-resampler localises these to the data's timezone.
    """
    start = pd.Timestamp(zoom['start'])
    window_start = start - pd.Timedelta(days=0.5)
    if zoom.get('end'):
        window_end = pd.Timestamp(zoom['end']) + pd.Timedelta(days=0.5)
    else:
        window_end = start + pd.Timedelta(days=1.5)
    return [x.strftime('%Y-%m-%d %H:%M:%S') for x in (window_start, window_end)]

def _relayout(x_range: list[str]) -> dict:
    return {'xaxis.range[0]': x_range[0], 'xaxis.range[1]': x_range[1]}

def _zoom_patch(x_range: list[str]) -> Patch:
    """
    A figure patch moving the x-axis to x_range, with the traces resampled for it.

    plotly-resampler's own patch only updates trace data, so the axis range is
    added here.
    """
    patch = resampler.construct_update_data_patch(_relayout(x_range))
    if not isinstance(patch, Patch):
        patch = Patch()
    patch['layout']['xaxis']['range'] = x_range
    patch['layout']['xaxis']['autorange'] = False
    return patch

def _build_figure(mdl) -> FigureResampler | None:
    """
    Replace the traces held by `resampler` with the model's timeseries.

    Returns None if the model has no results.
    """
    genr = mdl.get_generation_result()
    cs = mdl.get_consumption_storage_result()
    if genr is None or cs is None:
        return None

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

    # Clear previous traces; the update callback stays registered to `resampler`
    fig = resampler
    fig.replace(make_subplots(specs=[[{"secondary_y": True}]]))

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
        Output('timeseries-rendered-model-id', 'data'),
        Output('graph-timeseries', 'relayoutData', allow_duplicate = True),

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
        Input('timeseries-zoom-request', 'data'),

        State('timeseries-graph-container', 'style'),
        State('timeseries-rendered-model-id', 'data'),

        prevent_initial_call = True
    )
    def show_model_timeseries(
        trigger_manual,
        trigger_tables,
        active_project_id,
        zoom_request,
        container_style,
        rendered_model_id,
    ):
        """
        Draw the focussed configuration's timeseries, rebuilding only when the
        model shown or its results have changed, and apply any requested zoom.
        """
        global _resampler_model_id
        if active_project_id is None:
            raise PreventUpdate

        triggered_id = ctx.triggered_id
        results_changed = isinstance(triggered_id, dict) and triggered_id.get('key') == 'table_generation'

        if container_style.get('display') == 'none':
            if results_changed:
                # Rebuild when next shown
                return no_update, None, no_update
            raise PreventUpdate

        zoom_range = zoom_request.get('range') if triggered_id == 'timeseries-zoom-request' and zoom_request else None

        provider = cast(FromDatabaseNewsegsProjectProvider, app.project_provider)
        logger.debug('Getting lightweight project - Showing model timeseries')
        lproj = provider.get_lightweight_project(active_project_id)
        lmm = lproj.metamodels[lproj.focussed_metamodel_index]
        model_id = lmm.model.id

        # The graph keeps its figure while hidden, so only redraw when the model
        # or its results differ from those drawn (and held by the resampler)
        if not results_changed and rendered_model_id == model_id and _resampler_model_id == model_id:
            if zoom_range is None:
                raise PreventUpdate
            return _zoom_patch(zoom_range), no_update, no_update

        t0 = time.perf_counter()
        mdl = provider.metamodel_provider._em_provider.get_component(model_id)
        try:
            _ = mdl.get_grid_result()
        except AttributeError:
            mdl.reattach_results(app.results_provider)

        fig = _build_figure(mdl)
        if fig is None:
            raise PreventUpdate
        _resampler_model_id = model_id

        relayout = no_update
        if zoom_range is not None:
            fig.update_xaxes(range = zoom_range, autorange = False)
            # Have the resampler's update callback resample the traces for the range
            relayout = _relayout(zoom_range)

        t1 = time.perf_counter()
        logger.info(f'Timeseries plot created in {t1 - t0:.3f}s')
        return fig, model_id, relayout

    @app.callback(
        Output('timeseries-graph-container', 'style', allow_duplicate = True),
        Output('btn-show-timeseries', 'outline', allow_duplicate = True),
        Output('timeseries-zoom-request', 'data'),
        Input({'type': 'result-grid', 'table': ALL}, 'cellClicked'),
        prevent_initial_call = True
    )
    def zoom_to_result_cell(cells_clicked):
        """
        Show the timeseries and request a zoom to the date or date range clicked
        in a result grid, where a zoomable cell's value is {'label', 'start'[, 'end']}.
        """
        zoom = (callback_utils.get_triggered_value() or {}).get('value')
        if not isinstance(zoom, dict) or not zoom.get('start'):
            raise PreventUpdate

        return (
            {'display': 'block'},
            False,
            {'range': _zoom_window(zoom), 'timestamp': time.time_ns()}
        )

    return app
