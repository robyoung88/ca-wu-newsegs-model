"""
Functions and classes for performing probabilistic sensitivity analysis
"""
from collections import namedtuple
from typing import Any, Callable, Literal, NamedTuple, Sequence
from typing import get_args
import warnings

from dash import Patch, dcc, html
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from newsegsmetamodel import NewsegsMetaModel
from newsegsmodel import NewsegsModel
from newsegsfinance import NewsegsFinance
from newsegsvariable import variable

PSA_FLOAT_STATISTIC = Literal[
    'total_present_costs_undiscounted',
    'total_present_costs_discounted',
    'total_present_benefits_undiscounted',
    'total_present_benefits_discounted',
    'net_present_value_undiscounted',
    'net_present_value_discounted'
]

PSA_PLOT_TYPES = [
    'Scatter plot',
]

PSA_STATISTIC_NAMES = {
    'total_present_costs_undiscounted': 'Total cost (undisc.)',
    'total_present_costs_discounted': 'Total cost (disc.)',
    'total_present_benefits_undiscounted': 'Total benefits (undisc.)',
    'total_present_benefits_discounted': 'Total benefits (disc.)',
    'net_present_value_undiscounted': 'NPV (undisc.)',
    'net_present_value_discounted': 'NPV (disc.)'
}

def _psa_float_statistic_mapper(
    stat: PSA_FLOAT_STATISTIC,
    mdl: NewsegsModel,
    fnc: NewsegsFinance
) -> float:
    fnc_attrname = 'get_' + stat
    if hasattr(fnc, fnc_attrname):
        return getattr(fnc, fnc_attrname)()
    #elif hasattr(type(fnc), fnc_attrname):
    #    return getattr(type(fnc), fnc_attrname)(fnc)
    
    # Nothing to look for here yet, but included for future expansion
    if hasattr(mdl, fnc_attrname):
        return getattr(mdl, fnc_attrname)()
    #elif hasattr(type(mdl), fnc_attrname):
    #    return getattr(type(mdl), fnc_attrname)(mdl)
    
    raise ValueError(f'stat {stat} is not known as a PSA statistic')

def _make_psa_result(
    mm: NewsegsMetaModel,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    statistics: Sequence[PSA_FLOAT_STATISTIC],
    return_draws: bool = False,
):
    res: dict[str, Any] = {}
    if return_draws:
        for var in mm.variables.values():
            if var.psa_selected:
                if isinstance(var, variable.ScalarVariable):
                    res[var.name] = var.get_psa_value()
                elif isinstance(var, variable.VectorVariable):
                    nms = [var.name + '_' + str(x) for x in var.value_name]
                    vals = var.get_psa_value()
                    for nm, v in zip(nms, vals):
                        res[nm] = v
                else:
                    raise TypeError(f'var is not a supported variable type - is {type(var)}')
    for stat in statistics:
        res[stat] = _psa_float_statistic_mapper(stat, mdl, fnc)
    return res

def run_psa(
    mm: NewsegsMetaModel,
    statistics: Sequence[PSA_FLOAT_STATISTIC] = get_args(PSA_FLOAT_STATISTIC),
    samples: int = 100,
    seed: int | None = None,
    rng: np.random.Generator | None = None,
    return_draws: bool = False,
    progress: Callable[[int, int], None] | None = None,
    include_deterministic: bool = True,
) -> pd.DataFrame:
    variables = mm.variables.values()
    mdl = mm.model
    fnc = mm.finance

    results = []
    n_calcs = samples if not include_deterministic else samples + 1
    prog_i = 0
    if progress is not None:
        progress(prog_i, n_calcs)

    if include_deterministic:
        for v in variables:
            v.psa_active = False
            v.update_model(mdl)
            v.update_model(fnc)
        mdl.run()
        fnc.run()

        res = _make_psa_result(mm, mdl, fnc, statistics, return_draws)
        res['deterministic'] = True
        res['draw'] = 0
        results.append(res)
        if progress is not None:
                prog_i += 1
                progress(prog_i, n_calcs)
    
    if samples <= 0:
        return pd.DataFrame(results)
    
    if rng is None:
        rng = np.random.default_rng(seed)
    elif seed is not None:
        warnings.warn('Both a seed and a random generator are provided - existing generator will be used without reseeding')
    
    for v in variables:
        v.psa_active = True
    
    try:
        for i in range(samples):
            for v in variables:
                v.draw_psa(rng)
                v.update_model_psa(mdl)
                v.update_model_psa(fnc)
            
            mdl.run()
            fnc.run()

            res = _make_psa_result(mm, mdl, fnc, statistics, return_draws)
            res['deterministic'] = False
            res['draw'] = i+1
            results.append(res)
            if progress is not None:
                prog_i += 1
                progress(prog_i, n_calcs)
    finally:
        for v in variables:
            v.psa_active = False
            v.update_model(mdl)
            v.update_model(fnc)
    
    results = pd.DataFrame(results)
    return results

def basic_psa_stats(
    psa_results: pd.DataFrame,
    statistics: Sequence[PSA_FLOAT_STATISTIC] = get_args(PSA_FLOAT_STATISTIC),
    quantiles: Sequence[float] = [0.025, 0.975],
    npv_statistics = [
        'net_present_value_undiscounted',
        'net_present_value_discounted'
    ]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    res_det = (
        psa_results
        .query('deterministic == True')
        .loc[:, statistics]
        .sum()
        .to_frame()
        .rename(columns={0:'Deterministic'})
        )
    
    res_psa_raw = (
        psa_results
        .query('deterministic == False')
        .loc[:, statistics]
    )
    res_psa = (
        res_psa_raw
        .agg(
            ['count', 'mean', 'median', 'std']
        )
        .transpose()
        .rename(columns=lambda x: x.title())
    )
    res_psa_quants = (
        res_psa_raw
        .quantile(quantiles)
        .transpose()
        .rename(columns = lambda x: f'{100.*float(x):.1f} pctile'.replace('.','_'))
    )

    all_res = (
        res_det
        .join(res_psa)
        .join(res_psa_quants)
    )
    
    prob_positive_npv = (
        res_psa_raw
        .loc[:, npv_statistics]
        .gt(0)
        .mean(axis=0)
        .to_frame() # pyright: ignore[reportAttributeAccessIssue]
        .rename(columns={0:'prob_pos_npv'})
    )

    return all_res, prob_positive_npv

class PSAScatterData(NamedTuple):
    scatter_data: pd.DataFrame
    det_point: pd.Series
    ce_proportion: float

def psa_scatter_data(
    psa_data: pd.DataFrame,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted'
) -> PSAScatterData:
    scatter_data = (
        psa_data
        .query('deterministic == False')
        .loc[:, [cost_statistic, benefit_statistic]]
        .assign(
            cost_effective=lambda df: (df[benefit_statistic] > df[cost_statistic]).map({True: 'CE', False: 'Not CE'})
        )
    )

    det_point = (
        psa_data
        .query('deterministic == True')
        .loc[:, [cost_statistic, benefit_statistic]]
        .iloc[0]
    )

    ce_proportion = scatter_data['cost_effective'].eq('CE').mean()

    return PSAScatterData(scatter_data, det_point, ce_proportion)

BoundingBox = namedtuple('BoundingBox', ['xmin', 'ymin', 'xmax', 'ymax'])

def psa_scatter_bounds(scatter_data: pd.DataFrame) -> BoundingBox:
    all_max = float(scatter_data.iloc[:,0:2].max(axis=None)) # pyright: ignore[reportArgumentType]
    all_min = float(scatter_data.iloc[:,0:2].min(axis=None)) # pyright: ignore[reportArgumentType]

    if all_max == all_min:
        padding = abs(all_min) * 0.1 if all_min != 0 else 1. 
        all_min -= padding
        all_max += padding
    
    span = all_max - all_min
    padding = max(span * 0.1, abs(all_max) * 0.05, abs(all_min) * 0.05, 1e-8)
    if all_min >= 0:
        lower = -padding
        upper = all_max + padding
    elif all_max <= 0:
        lower = all_min - padding
        upper = padding
    else:
        lower = all_min - padding
        upper = all_max + padding
    
    return BoundingBox(lower, lower, upper, upper)

def psa_scatter(
    psa_data: pd.DataFrame | None,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted',
    point_alpha: float = 0.2,
    show_proportion_ce: bool = True,
):
    if psa_data is None:
        psa_data = pd.DataFrame.from_dict(
            {
                cost_statistic: [1, 1],
                benefit_statistic: [1, 1],
                'deterministic': [True, False],
            }
        )
    plot_data = psa_scatter_data(psa_data, cost_statistic, benefit_statistic)

    bb = psa_scatter_bounds(plot_data.scatter_data)

    # First draw - the scatter
    fig = px.scatter(
        plot_data.scatter_data,
        x=cost_statistic,
        y=benefit_statistic,
        color='cost_effective',
        color_discrete_map={'CE': 'green', 'Not CE': 'red'},
        labels={'cost_effective': 'Cost effective?'} ,
        opacity=point_alpha
    )

    # Second draw - the reference line
    # NB - xmin should equal ymin of bb, but just in case:
    fig.add_shape(
        type='line',
        x0=bb.xmin,
        y0=bb.xmin,
        x1=bb.xmax,
        y1=bb.xmax,
        line=dict(color='gray', dash='dash'),
        xref='x',
        yref='y'
    )

    # Third draw - the DSA point
    fig.add_trace(
        go.Scatter(
            x=[plot_data.det_point[cost_statistic]],
            y=[plot_data.det_point[benefit_statistic]],
            mode='markers',
            marker=dict(size=12, symbol='diamond', color='gold', line=dict(color='black', width=1)),
            name='Deterministic',
            showlegend=True
        )
    )

    # Formatting - axes
    fig.update_xaxes(
        title=PSA_STATISTIC_NAMES.get(cost_statistic, cost_statistic),
        range=[bb.xmin, bb.xmax],
        scaleanchor='y',
        scaleratio=1,
    )
    fig.update_yaxes(
        title=PSA_STATISTIC_NAMES.get(benefit_statistic, benefit_statistic),
        range=[bb.ymin, bb.ymax],
    )

    if show_proportion_ce:
        # Fourth draw - proportion ce
        fig.add_annotation(
            text=f'Proportion CE: {plot_data.ce_proportion:.1%}',
            xref='paper',
            yref='paper',
            x=0.05,
            y=0.95,
            showarrow=False,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='black',
            borderwidth=1
        )

    return fig
    
def psa_scatter_update(
    psa_data: pd.DataFrame | None,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted',
    show_proportion_ce: bool = True
):
    fig_patch = Patch()

    if psa_data is None:
        # Clear scatter
        # Not CE
        fig_patch['data'][0]['x'] = []
        fig_patch['data'][0]['y'] = []
        # CE
        fig_patch['data'][1]['x'] = []
        fig_patch['data'][1]['y'] = []
        
        # Clear deterministic
        fig_patch['data'][2]['x'] = []
        fig_patch['data'][2]['y'] = []

        # Don't update reference line
        # Don't update axes

        # Clear annotation
        if show_proportion_ce:
            fig_patch['layout']['annotations'][0]['text'] = ''
        
        return fig_patch
    
    
    plot_data = psa_scatter_data(psa_data, cost_statistic, benefit_statistic)
    bb = psa_scatter_bounds(plot_data.scatter_data)

    scatterdata = plot_data.scatter_data.set_index('cost_effective')
    # Scatter not CE
    draw_index = 0
    fig_patch['data'][draw_index]['x'] = scatterdata.loc['Not CE', cost_statistic]
    fig_patch['data'][draw_index]['y'] = scatterdata.loc['Not CE', benefit_statistic]

    # Scatter CE
    draw_index += 1
    fig_patch['data'][draw_index]['x'] = scatterdata.loc['CE', cost_statistic]
    fig_patch['data'][draw_index]['y'] = scatterdata.loc['CE', benefit_statistic]

    # Deterministic
    draw_index += 1
    fig_patch['data'][draw_index]['x'] = plot_data.det_point[cost_statistic]
    fig_patch['data'][draw_index]['y'] = plot_data.det_point[benefit_statistic]

    # Reference line
    fig_patch['layout']['shapes'][0].update(
        {
            'x0': bb.xmin,
            'y0': bb.xmin,
            'x1': bb.xmax,
            'y1': bb.xmax,
        }
    )

    # Axes
    fig_patch['layout']['xaxis']['range'] = [bb.xmin, bb.xmax]
    fig_patch['layout']['xaxis']['title']['text'] = PSA_STATISTIC_NAMES.get(cost_statistic, cost_statistic)
    fig_patch['layout']['yaxis']['range'] = [bb.ymin, bb.ymax]
    fig_patch['layout']['yaxis']['title']['text'] = PSA_STATISTIC_NAMES.get(benefit_statistic, benefit_statistic)

    # Annotation
    if show_proportion_ce:
        fig_patch['layout']['annotations'][0]['text'] = f'Proportion CE: {plot_data.ce_proportion:.1%}'

    return fig_patch

def psa_scatter_controls(page: str):
    return [
        html.Div(
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-Scatter plot-ii'},
            style = {'display': 'none'}
        ),
        dcc.Dropdown(
            options = [
                {'label': 'Discounted', 'value': 'discounted'},
                {'label': 'Undiscounted', 'value': 'undiscounted'}
            ],
            value = 'discounted',
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-discount-dropdown'},
            searchable = False,
            clearable = False
        ),
    ]

def psa_scatter_arguments(plot_controls):
    discounting = 'discounted'
    for idx, id in enumerate(plot_controls['ids']):
        if id.get('key') == 'psa-primary-plot-discount-dropdown':
            discounting = plot_controls['values'][idx]
            break
    
    rval = {}
    match discounting:
        case 'discounted':
            rval['cost_statistic'] = 'total_present_costs_discounted'
            rval['benefit_statistic'] = 'total_present_benefits_discounted'
        case 'undiscounted':
            rval['cost_statistic'] = 'total_present_costs_undiscounted'
            rval['benefit_statistic'] = 'total_present_benefits_undiscounted'
        case _:
            raise ValueError(f'Discounting type not recognised: {discounting}')
    return rval

psa_plots = {
    'Scatter plot': {
        'draw': psa_scatter,
        'update': psa_scatter_update,
        'controls': psa_scatter_controls,
        'arguments': psa_scatter_arguments,
    }
}
