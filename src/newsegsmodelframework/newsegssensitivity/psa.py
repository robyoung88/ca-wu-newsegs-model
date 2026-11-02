"""
Functions and classes for performing probabilistic sensitivity analysis
"""
from dataclasses import field
from typing import Any, Callable, Literal, NamedTuple, Sequence, override
from typing import get_args
import warnings

from dash import Patch, dcc, html
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmodel import NewsegsModel
from newsegsmodelframework.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegssensitivity.common import COST_FRAME_STATISTICS, total_of_cost_frame
from newsegsmodelframework.newsegsvariable import variable

PSA_FLOAT_STATISTIC = Literal[
    'total_present_costs_undiscounted',
    'total_present_costs_discounted',
    'total_present_benefits_undiscounted',
    'total_present_benefits_discounted',
    'net_present_value_undiscounted',
    'net_present_value_discounted',
    'all_capex_costs_undiscounted',
    'all_capex_costs_discounted',
    'all_recurrent_costs_undiscounted',
    'all_recurrent_costs_discounted',
]
"""The statistics of a run of the NewSEGS Energy Model and finance model that a PSA can calculate."""

PSA_PLOT_TYPES = [
    'Scatter plot',
    'Cumulative probability',
    'Convergence'
]
"""The types of plot of the results of a PSA."""

PSA_STATISTIC_LABELS = {
    'total_present_costs_undiscounted': 'Total cost (undisc.)',
    'total_present_costs_discounted': 'Total cost (disc.)',
    'total_present_benefits_undiscounted': 'Total benefits (undisc.)',
    'total_present_benefits_discounted': 'Total benefits (disc.)',
    'net_present_value_undiscounted': 'NPV (undisc.)',
    'net_present_value_discounted': 'NPV (disc.)',
    'all_capex_costs_undiscounted': 'Total capex (undisc.)',
    'all_capex_costs_discounted': 'Total capex (disc.)',
    'all_recurrent_costs_undiscounted': 'Total opex (undisc.)',
    'all_recurrent_costs_discounted': 'Total opex (disc.)',
}
"""Short labels of the statistics of a PSA, for plots."""

_CONVERGENCE_STATISTICS = Literal[
    'Mean',
    'Variance',
    'Median',
    'First Decile',
    'First Quartile',
    'Third Quartile',
    'Ninth Decile'
]

CONVERGENCE_STATISTICS = get_args(_CONVERGENCE_STATISTICS)
"""The statistics whose convergence, over the draws of a PSA, can be plotted."""

def quantile_stderr_cum(
    x,
    p: float = 0.5,
    bw: float | None = None
):
    """Standard error of the quantile of the first n values, for each n.

    The standard error of a sample quantile is `sqrt(p (1 - p) / n) / f`, where `f` is the density at the quantile,
    estimated by a Gaussian kernel density estimate. See
    [quantileSE](https://github.com/kbroman/broman/blob/main/R/quantileSE.R).

    Args:
        x: The sample, in order of draw.
        p: The probability of the quantile; 0.5 is the median.
        bw: Bandwidth of the kernel density estimate; by default chosen by scipy.

    Returns:
        Array of the standard error after each draw.
    """
    # https://github.com/kbroman/broman/blob/main/R/quantileSE.R
    from scipy.stats import gaussian_kde
    quant = np.quantile(x, p)
    R = np.sqrt(p * (1. - p) / (np.arange(len(x))+1))
    if bw is None:
        pdf_ = gaussian_kde(x)
        f = pdf_.pdf(quant)
    else:
        pdf_ = gaussian_kde(x, bw_method = bw)
        f = pdf_.pdf(quant)
    return R / f

def _psa_float_statistic_mapper(
    stat: PSA_FLOAT_STATISTIC,
    mdl: NewsegsModel,
    fnc: NewsegsFinance
) -> float:
    if stat in COST_FRAME_STATISTICS:
        return total_of_cost_frame(getattr(fnc, stat))

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

def make_psa_result(
    mm: NewsegsMetaModel,
    mdl: NewsegsModel,
    fnc: NewsegsFinance,
    statistics: Sequence[PSA_FLOAT_STATISTIC],
    return_draws: bool = False,
):
    """One row of the results of a PSA: a run of the NewSEGS Energy Model and finance model.

    Args:
        mm: The metamodel.
        mdl: The NewSEGS Energy Model, after the run.
        fnc: The finance model, after the run.
        statistics: The statistics to take from the models.
        return_draws: Whether to include the values drawn for each variable selected for PSA.

    Returns:
        Dictionary of the statistics and, if requested, the values of the variables (a vector variable gives one entry for each value).

    Raises:
        TypeError: if a variable selected for PSA is neither a scalar nor a vector variable.
    """
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
    cancel_status: Callable[[], bool] | None = None,
    include_deterministic: bool = True,
    precomputed_deterministic: bool = False,
) -> pd.DataFrame:
    """Run a probabilistic sensitivity analysis of a metamodel.

    Each sample draws a value for every variable that is selected for PSA from its distribution, then runs the NewSEGS Energy Model
    and finance model. Optionally the deterministic run is included first. Afterwards the variables are returned to their deterministic values.

    Args:
        mm: The metamodel.
        statistics: The statistics to calculate for each run.
        samples: The number of samples to draw.
        seed: Seed of the random number generator, if none is provided.
        rng: Random number generator; used in preference to the seed.
        return_draws: Whether to return the values drawn for each variable.
        progress: Function reporting progress, called with the number of runs completed and the total.
        cancel_status: Function returning whether cancellation has been requested; checked before each sample.
        include_deterministic: Whether to include the deterministic run (marked `deterministic`).
        precomputed_deterministic: Whether the metamodel already holds valid results of the deterministic run, so that
            it need not be repeated.

    Returns:
        Dataframe with a row for each run, and columns of the statistics, `deterministic` and `draw` (0 for the deterministic run).

    Raises:
        InterruptedError: if cancellation is requested.
    """
    variables = mm.variables.values()
    mdl = mm.model
    fnc = mm.finance

    results = []
    n_calcs = samples if not include_deterministic else samples + 1
    prog_i = 0
    if progress is not None:
        progress(prog_i, n_calcs)

    if cancel_status is None:
        cancel_status = lambda: False

    if cancel_status():
        raise InterruptedError('PSA job cancelled')
    
    if include_deterministic:
        if not precomputed_deterministic:
            for v in variables:
                v.psa_active = False
                v.update_model(mdl)
                v.update_model(fnc)
            mdl.run()
            fnc.run()

        res = make_psa_result(mm, mdl, fnc, statistics, return_draws)
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

    variables = [v for v in variables if v.psa_selected]
    
    for v in variables:
        v.psa_active = True
    
    try:
        for i in range(samples):
            if cancel_status():
                raise InterruptedError('PSA job cancelled')
            
            for v in variables:
                v.draw_psa(rng)
                v.update_model_psa(mdl)
                v.update_model_psa(fnc)
            
            mdl.run()
            fnc.run()

            res = make_psa_result(mm, mdl, fnc, statistics, return_draws)
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
            mdl.run()
            fnc.run()
    
    results = pd.DataFrame(results)
    return results


@revision_dataclass
class PSAConfig(DataWithRevision):
    """Configuration of a probabilistic sensitivity analysis.

    Attributes:
        samples: Number of samples to draw.
        seed: Seed of the random number generator; random if None.
        return_draws: Whether to return the values drawn.
        include_deterministic: Whether to include the deterministic run.
        statistics: The statistics calculated from the samples.
    """
    samples: int = 1000
    seed: int | None = None
    return_draws: bool = False
    include_deterministic: bool = False
    statistics: list[PSA_FLOAT_STATISTIC] = field(default_factory = lambda: get_args(PSA_FLOAT_STATISTIC))


class PSAComponent(NewsegsComponent):
    """A container for PSA settings"""

    component_type = 'psa'

    @override
    def _generate_config(self, *args, **kwargs) -> PSAConfig:
        return PSAConfig(*args, **kwargs)
    _config: PSAConfig
    
    def __init__(
        self,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)            

def basic_psa_stats(
    psa_results: pd.DataFrame,
    statistics: Sequence[PSA_FLOAT_STATISTIC] = get_args(PSA_FLOAT_STATISTIC),
    quantiles: Sequence[float] = [0.025, 0.975],
    npv_statistics = [
        'net_present_value_undiscounted',
        'net_present_value_discounted'
    ]
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Summarise the results of a PSA.

    Args:
        psa_results: The results of the PSA, from `run_psa`.
        statistics: The statistics to summarise.
        quantiles: Quantiles to report.
        npv_statistics: The net present value statistics for which to find the probability of being positive.

    Returns:
        A dataframe with a row for each statistic and columns of the deterministic value, the count, mean, median and standard deviation
        of the samples, and the quantiles; and a dataframe of the probability that each net present value is positive.
        Statistics missing from the results (e.g. results from before the statistic was added) are left out.
    """
    statistics = [s for s in statistics if s in psa_results.columns]
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

##### Generic Graph functions #####

class BoundingBox(NamedTuple):
    """Bounding box of a set of points.
    """
    """"""
    xmin: float
    ymin: float
    xmax: float
    ymax: float


def get_null_psa_data(statistics: Sequence[str]) -> pd.DataFrame:
    """Placeholder PSA results, to draw plots before there are results.

    Args:
        statistics: The statistics for which to make data.

    Returns:
        A dataframe of two rows - one deterministic and one not (draws 0 and 1) - with every statistic equal to 1.
    """
    stat_dict = {
        x: [1, 1] for x in statistics
    }
    stat_dict['deterministic'] = [True, False]
    stat_dict['draw'] = [0, 1]
    return pd.DataFrame.from_dict(
            stat_dict
        )

##### Scatter ######

class PSAScatterData(NamedTuple):
    """NamedTuple of data for a PSA scatter plot
    """
    scatter_data: pd.DataFrame
    det_point: pd.Series
    ce_proportion: float


def psa_scatter_data(
    psa_data: pd.DataFrame,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted'
) -> PSAScatterData:
    """Data for the scatter plot of the costs and benefits of the samples of a PSA.

    Each sample is categorised as cost effective (`CE`) if its benefits exceed its costs.

    Args:
        psa_data: The results of the PSA.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.

    Returns:
        The samples with their category, the deterministic point and the proportion of samples that are cost effective.
    """
    scatter_data = (
        psa_data
        .query('deterministic == False')
        .loc[:, [cost_statistic, benefit_statistic]]
        .assign(
            cost_effective = lambda df: (df[benefit_statistic] > df[cost_statistic]).map({True: 'CE', False: 'Not CE'})
        )
        .assign(
            cost_effective = lambda df: pd.Categorical(df['cost_effective'], categories=['CE', 'Not CE'], ordered = True)
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

def psa_scatter_bounds(scatter_data: pd.DataFrame) -> BoundingBox:
    """Bounds of the scatter plot of costs and benefits.

    The plot is square, with padding around the extremes of the costs and benefits; a plot which is wholly positive or wholly negative
    extends to just beyond zero.

    Args:
        scatter_data: The samples, with the costs and benefits in the first two columns.

    Returns:
        The bounding box.
    """
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
    """Scatter plot of the costs and benefits of the samples of a PSA.

    Samples are plotted against a line of equal costs and benefits, so that cost effective samples are those above it, and
    the deterministic result is marked.

    Args:
        psa_data: The results of the PSA; None for an empty plot.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.
        point_alpha: Opacity of the points.
        show_proportion_ce: Whether to annotate the proportion of samples that are cost effective.

    Returns:
        The plot (a plotly figure).
    """
    if psa_data is None:
        psa_data = get_null_psa_data([cost_statistic, benefit_statistic])

    plot_data = psa_scatter_data(psa_data, cost_statistic, benefit_statistic)

    bb = psa_scatter_bounds(plot_data.scatter_data)

    # First draw - the scatter
    firstdraw_data = pd.DataFrame.from_dict(
        {
            cost_statistic: [1., 1.],
            benefit_statistic: [0.5, 1.],
            'cost_effective' : pd.Categorical(
                ['Not CE', 'CE'],
                categories=['CE', 'Not CE'],
                ordered = True
            )
        }
    )
    
    fig = px.scatter(
        firstdraw_data,
        x=cost_statistic,
        y=benefit_statistic,
        color='cost_effective',
        color_discrete_map={'CE': 'green', 'Not CE': 'red'},
        category_orders = {'cost_effective': ['CE', 'Not CE']},
        labels={'cost_effective': 'Cost effective?'} ,
        opacity=point_alpha
    )

    scatterdata = plot_data.scatter_data.set_index('cost_effective')
    # Scatter not CE
    draw_index = 0
    if 'CE' in scatterdata.index:
        fig.data[draw_index]['x'] = pd.Series(scatterdata.loc['CE', cost_statistic])
        fig.data[draw_index]['y'] = pd.Series(scatterdata.loc['CE', benefit_statistic])
    else:
        fig.data[draw_index]['x'] = []
        fig.data[draw_index]['y'] = []

    # Scatter CE
    draw_index += 1
    if 'Not CE' in scatterdata.index:
        fig.data[draw_index]['x'] = pd.Series(scatterdata.loc['Not CE', cost_statistic])
        fig.data[draw_index]['y'] = pd.Series(scatterdata.loc['Not CE', benefit_statistic])
    else:
        fig.data[draw_index]['x'] = []
        fig.data[draw_index]['y'] = []

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

    # Third draw - the Deterministic point
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
        title=PSA_STATISTIC_LABELS.get(cost_statistic, cost_statistic),
        range=[bb.xmin, bb.xmax],
        scaleanchor='y',
        scaleratio=1,
    )
    fig.update_yaxes(
        title=PSA_STATISTIC_LABELS.get(benefit_statistic, benefit_statistic),
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
    """Patch to update an existing scatter plot of a PSA with new results, without redrawing it.

    Args:
        psa_data: The results of the PSA; None to clear the plot.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.
        show_proportion_ce: Whether the plot annotates the proportion of samples that are cost effective.

    Returns:
        The patch (a Dash `Patch`) of the figure.
    """
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
    # Scatter CE
    draw_index = 0
    if 'CE' in scatterdata.index:
        fig_patch['data'][draw_index]['x'] = pd.Series(scatterdata.loc['CE', cost_statistic])
        fig_patch['data'][draw_index]['y'] = pd.Series(scatterdata.loc['CE', benefit_statistic])
    else:
        fig_patch['data'][draw_index]['x'] = []
        fig_patch['data'][draw_index]['y'] = []

    # Scatter noot CE
    draw_index += 1
    if 'Not CE' in scatterdata.index:
        fig_patch['data'][draw_index]['x'] = pd.Series(scatterdata.loc['Not CE', cost_statistic])
        fig_patch['data'][draw_index]['y'] = pd.Series(scatterdata.loc['Not CE', benefit_statistic])
    else:
        fig_patch['data'][draw_index]['x'] = []
        fig_patch['data'][draw_index]['y'] = []

    # Deterministic
    draw_index += 1
    fig_patch['data'][draw_index]['x'] = pd.Series(plot_data.det_point[cost_statistic])
    fig_patch['data'][draw_index]['y'] = pd.Series(plot_data.det_point[benefit_statistic])

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
    fig_patch['layout']['xaxis']['title']['text'] = PSA_STATISTIC_LABELS.get(cost_statistic, cost_statistic)
    fig_patch['layout']['yaxis']['range'] = [bb.ymin, bb.ymax]
    fig_patch['layout']['yaxis']['title']['text'] = PSA_STATISTIC_LABELS.get(benefit_statistic, benefit_statistic)

    # Annotation
    if show_proportion_ce:
        fig_patch['layout']['annotations'][0]['text'] = f'Proportion CE: {plot_data.ce_proportion:.1%}'

    return fig_patch

def psa_scatter_controls(page: str):
    """Controls of the scatter plot: whether the costs and benefits are discounted.

    Args:
        page: The page that the controls are on, which is part of their ids.

    Returns:
        List of components.
    """
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
    """Arguments of the scatter plot from the values of its controls.

    Args:
        plot_controls: The ids and values of the controls, as given to a Dash callback.

    Returns:
        Dictionary of `cost_statistic` and `benefit_statistic`, discounted by default.

    Raises:
        ValueError: if the discounting is not recognised.
    """
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

###### CDF #####

class PSACDFData(NamedTuple):
    """Data for the cumulative distribution plot of a statistic of a PSA.

    Attributes:
        cdf_data: The samples in ascending order, with their cumulative probability.
        det_value: The value of the statistic of the deterministic run.
        min: Lowest sample.
        max: Highest sample.
    """
    cdf_data: pd.DataFrame
    det_value: float
    min: float
    max: float


def psa_cdf_data(
    psa_data: pd.DataFrame,
    statistic: str
) -> PSACDFData:
    """Data for the cumulative distribution plot of a statistic of a PSA.

    Args:
        psa_data: The results of the PSA.
        statistic: The statistic.

    Returns:
        The samples, the deterministic value and the range.
    """
    cdf_data = (
        psa_data
        .query('deterministic == False')
        .loc[:, [statistic,]]
        .sort_values(statistic)
        .reset_index(drop = True)
        .assign(
            cdf = lambda df: df[statistic].index / max(1, df[statistic].count())
        )
    )

    det_value = (
        psa_data
        .query('deterministic == True')
        .loc[:, statistic]
        .iloc[0]
    )

    return PSACDFData(
        cdf_data,
        det_value,
        cdf_data[statistic].iloc[0],
        cdf_data[statistic].iloc[-1]
    )

def psa_cdf_bounds(cdf_data: PSACDFData) -> BoundingBox:
    """Bounds of the cumulative distribution plot.

    Args:
        cdf_data: The data of the plot.

    Returns:
        The bounding box: the range of the samples, padded, and cumulative probabilities from 0 to 1.
    """
    min_x = cdf_data.min
    max_x = cdf_data.max
    
    if min_x == max_x:
        padding = abs(min_x) * 0.1 if min_x != 0 else 1.
        min_x -= padding
        max_x += padding
    
    span = max_x - min_x
    padding = max(span * 0.1, abs(max_x) * 0.05, abs(min_x) * 0.05, 1e-8)
    lower = min_x - padding
    upper = max_x + padding
    
    return BoundingBox(xmin=lower, ymin=0., xmax=upper, ymax=1.)

def psa_cdf(
    psa_data: pd.DataFrame | None,
    statistic: str = 'net_present_value_discounted'
):
    """Plot of the cumulative distribution of a statistic of a PSA.

    The deterministic value is marked.

    Args:
        psa_data: The results of the PSA; None for an empty plot.
        statistic: The statistic.

    Returns:
        The plot (a plotly figure).
    """
    if psa_data is None:
        psa_data = get_null_psa_data([statistic,])
    
    cdf_data = psa_cdf_data(psa_data, statistic)
    bb = psa_cdf_bounds(cdf_data)

    fig = px.line(
        cdf_data.cdf_data,
        x = statistic,
        y = 'cdf'
    )

    fig.add_shape(
        type = 'line',
        x0 = cdf_data.det_value,
        y0 = -0.1,
        x1 = cdf_data.det_value,
        y1 = 1.1,
        line = dict(color='gray', dash='dash'),
        xref = 'x',
        yref = 'y',
    )

    fig.add_annotation(
        text = f'{cdf_data.min:,.2f}',
        xref = 'x',
        yref = 'y',
        axref = 'x',
        x = cdf_data.min,
        ax = cdf_data.min + 0.05 * (bb.xmax-bb.xmin),
        y = 0.0,
        showarrow = True,
        bgcolor='rgba(255, 255, 255, 0.8)',
        bordercolor='black',
        borderwidth=1
    )

    fig.add_annotation(
        text = f'{cdf_data.max:,.2f}',
        xref = 'x',
        yref = 'y',
        axref = 'x',
        ayref = 'y',
        x = cdf_data.max,
        ax = cdf_data.max - 0.05 * (bb.xmax-bb.xmin),
        y = 1.,
        ay = 0.9,
        showarrow = True,
        bgcolor='rgba(255, 255, 255, 0.8)',
        bordercolor='black',
        borderwidth=1
    )

    # Formatting - axes
    fig.update_xaxes(
        title=PSA_STATISTIC_LABELS.get(statistic, statistic),
        range=[bb.xmin, bb.xmax],
    )
    fig.update_yaxes(
        title = 'Cumulative probability',
        range = [bb.ymin, bb.ymax],
    )

    return fig

def psa_cdf_update(
    psa_data: pd.DataFrame | None,
    statistic: str = 'net_present_value_discounted',
):
    """Patch to update an existing cumulative distribution plot with new results, without redrawing it.

    Args:
        psa_data: The results of the PSA; None to clear the plot.
        statistic: The statistic.

    Returns:
        The patch (a Dash `Patch`) of the figure.
    """
    fig_patch = Patch()

    if psa_data is None:
        # Clear cdf
        fig_patch['data'][0]['x'] = []
        fig_patch['data'][0]['y'] = []

        # Don't touch deterministic reference line
        
        # Clear annotations
        fig_patch['layout']['annotations'][0]['text'] = ''
        fig_patch['layout']['annotations'][1]['text'] = ''

        return fig_patch
    
    cdf_data = psa_cdf_data(psa_data, statistic)
    bb = psa_cdf_bounds(cdf_data)

    # CDF data
    fig_patch['data'][0]['x'] = cdf_data.cdf_data.loc[:, statistic]
    fig_patch['data'][0]['y'] = cdf_data.cdf_data.loc[:, 'cdf']

    # Deterministic reference
    fig_patch['layout']['shapes'][0].update({
        'x0': cdf_data.det_value,
        'x1': cdf_data.det_value
    })

    # Annotations
    fig_patch['layout']['annotations'][0].update({
        'text': f'{cdf_data.min:,.2f}',
        'x': cdf_data.min,
        'ax': cdf_data.min + 0.05 * (bb.xmax-bb.xmin), 
    })

    fig_patch['layout']['annotations'][1].update({
        'text': f'{cdf_data.max:,.2f}',
        'x': cdf_data.max,
        'ax': cdf_data.max - 0.05 * (bb.xmax-bb.xmin), 
    })

    # Axes
    fig_patch['layout']['xaxis']['range'] = [bb.xmin, bb.xmax]
    fig_patch['layout']['xaxis']['title']['text'] = PSA_STATISTIC_LABELS.get(statistic, statistic)

    return fig_patch

def psa_cdf_controls(page: str):
    """Controls of the cumulative distribution plot: which statistic is plotted.

    Args:
        page: The page that the controls are on, which is part of their ids.

    Returns:
        List of components.
    """
    return [
        html.Div(
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-Cumulative probability-ii'},
            style = {'display': 'none'}
        ),
        dcc.Dropdown(
            options = [
                {'label': v, 'value': k} for k, v in PSA_STATISTIC_LABELS.items()
            ],
            value = list(PSA_STATISTIC_LABELS.keys())[0],
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-statistic-dropdown'},
            searchable = False,
            clearable = False
        ),
    ]

def psa_cdf_arguments(plot_controls):
    """Arguments of the cumulative distribution plot from the values of its controls.

    Args:
        plot_controls: The ids and values of the controls, as given to a Dash callback.

    Returns:
        Dictionary of the `statistic`.
    """
    statistic = 'net_present_value_discounted'
    for idx, id in enumerate(plot_controls['ids']):
        if id.get('key') == 'psa-primary-plot-statistic-dropdown':
            statistic = plot_controls['values'][idx]
    rval = dict(statistic = statistic)
    return rval

##### Convergence #####

class PSAConvergenceData(NamedTuple):
    """NamedTuple of data for PSA convergence summaries
    """
    stat_data: pd.DataFrame
    final_stat: float

def psa_convergence_data(
    psa_data: pd.DataFrame,
    statistic: str,
    convergence_statistic: _CONVERGENCE_STATISTICS
):
    """Data for the plot of the convergence of a statistic of a PSA over its draws.

    For each draw, the value of the convergence statistic (e.g. the mean) of the samples so far, with its standard error.

    Args:
        psa_data: The results of the PSA.
        statistic: The statistic of the model whose convergence is plotted.
        convergence_statistic: The statistic of the samples: mean, variance, median or a decile or quartile.

    Returns:
        The convergence of the statistic with its standard error at each draw, and its final value.

    Raises:
        ValueError: if the convergence statistic is not recognised.
    """
    raw_frame = (
        psa_data
        .query('deterministic == False')
        .loc[:, ['draw', statistic]]
    )

    match convergence_statistic:
        case 'Mean':
            final_stat = raw_frame[statistic].mean()
            sample_std = raw_frame[statistic].std()
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().mean(),
                    stderr = lambda df: sample_std / np.sqrt(df['draw'])
                )
            )
        case 'Variance':
            final_stat = raw_frame[statistic].var()
            # Assume that we have convergence and Normally distributed so SE can
            # be estimated using s^2 as sigma^2
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().var(),
                    stderr = lambda df: np.sqrt((2. * final_stat**2) / df['draw'])
                )
            )
        case 'Median':
            final_stat = raw_frame[statistic].median()
            # https://search.r-project.org/CRAN/refmans/wrappedtools/html/se_median.html
            # https://github.com/abusjahn/wrappedtools/blob/main/R/descriptives.R
            from scipy.stats import median_abs_deviation
            mad = median_abs_deviation(raw_frame[statistic])
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().median(),
                    stderr = lambda df: mad / np.sqrt(df['draw'])
                )
            )
        case 'First Decile':
            q = 0.1
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case 'First Quartile':
            q = 0.25
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case 'Third Quartile':
            q = 0.75
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case 'Ninth Decile':
            q = 0.9
            final_stat = float(raw_frame[statistic].quantile(q))
            stat_data = (
                raw_frame
                .assign(
                    cumstat = lambda df: df[statistic].expanding().quantile(q),
                    stderr = lambda df: quantile_stderr_cum(df[statistic], q)
                )
            )
        case _:
            raise ValueError(f'convergence_statistic not recognised: {convergence_statistic}')
    
    stat_data = (
        stat_data
        .assign(
            lower_bound = lambda df: final_stat - 2.0 * df['stderr'],
            upper_bound = lambda df: final_stat + 2.0 * df['stderr']
        )
    )

    return PSAConvergenceData(
        stat_data,
        final_stat
    )

def psa_convergence_bounds(con_data: PSAConvergenceData):
    """Bounds of the convergence plot.

    The range of the draws, and of the cumulative statistic with its standard error, ignoring infinite values, padded.

    Args:
        con_data: The data of the plot.

    Returns:
        The bounding box.
    """
    min_x = con_data.stat_data['draw'].iloc[0]
    max_x = con_data.stat_data['draw'].iloc[-1]

    if min_x == max_x:
        min_x -= 0.25
        max_x += 0.25
    
    span = max_x - min_x
    padding_x = max(span * 0.1, abs(max_x) * 0.05, abs(min_x) * 0.05, 1e-8)
    lower_x = min_x - padding_x
    upper_x = max_x + padding_x

    # drop infinite values when computing y-bounds
    cum = con_data.stat_data['cumstat']
    finite_mask = np.isfinite(cum)
    if finite_mask.any():
        min_y = cum[finite_mask].min(skipna=True)
        max_y = cum[finite_mask].max(skipna=True)
    else:
        # fallback to original behaviour (will produce nan if all missing)
        min_y = cum.min(skipna=True)
        max_y = cum.max(skipna=True)

    if not np.isfinite(min_y):
        min_y = 0.
    if not np.isfinite(max_y):
        max_y = max(min_y, 1.)
    
    if min_y == max_y:
        padding = abs(min_y) * 0.1 if min_y != 0 else 0.25
        min_y -= padding
        max_y += padding
    
    span = max_y - min_y
    padding_y = max(span * 0.1, abs(max_y) * 0.05, abs(min_y) * 0.05, 1e-8)
    lower_y = min_y - padding_y
    upper_y = max_y + padding_y
    return BoundingBox(lower_x, lower_y, upper_x, upper_y)

def psa_convergence(
    psa_data: pd.DataFrame | None,
    statistic: str = 'total_present_costs_discounted',
    convergence_statistic: _CONVERGENCE_STATISTICS = 'Mean'
):
    """Plot of the convergence of a statistic of a PSA over its draws.

    Shows the statistic of the samples so far, its final value, and a band of its standard error.

    Args:
        psa_data: The results of the PSA; None for an empty plot.
        statistic: The statistic of the model whose convergence is plotted.
        convergence_statistic: The statistic of the samples: mean, variance, median or a decile or quartile.

    Returns:
        The plot (a plotly figure).
    """
    if psa_data is None:
        psa_data = get_null_psa_data([statistic])

    con_data = psa_convergence_data(psa_data, statistic, convergence_statistic)
    bb = psa_convergence_bounds(con_data)

    fig = px.line(
        con_data.stat_data,
        x = 'draw',
        y = 'cumstat'
    )
    
    fig.add_trace(
        go.Scatter(
            x = [0, con_data.stat_data['draw'].iloc[-1]*1.1],
            y = [con_data.final_stat, con_data.final_stat],
            mode = 'lines',
            line = dict(color='orange', dash='dash'),
            name = 'Final statistic'
        )
    )

    fig.add_trace(
        go.Scatter(
            x = con_data.stat_data['draw'],
            y = con_data.stat_data['lower_bound'],
            mode = 'lines',
            line = dict(color='gray', dash='dash'),
            name = '2 * estimated SE'
        )
    )

    fig.add_trace(
        go.Scatter(
            x = con_data.stat_data['draw'],
            y = con_data.stat_data['upper_bound'],
            mode = 'lines',
            line = dict(color='gray', dash='dash'),
            name = '2 * estimated SE',
            showlegend = False
        )
    )

    if (con_data.final_stat - bb.ymin) > 0.5 * (bb.ymax - bb.ymin):
        fig.update_layout(
            legend=dict(
                x=0.99,
                y=0.15,
                xanchor='right',
                yanchor='top'
            )
        )
    else:
        fig.update_layout(
            legend=dict(
                x=0.99,
                y=0.95,
                xanchor='right',
                yanchor='top'
            )
        )

    # Formatting - axes
    fig.update_xaxes(
        title = 'Draw',
        range=[bb.xmin, bb.xmax],
    )
    fig.update_yaxes(
        title= f'{PSA_STATISTIC_LABELS.get(statistic, statistic)} - {convergence_statistic}',
        range = [bb.ymin, bb.ymax],
    )

    return fig

def psa_convergence_update(
    psa_data: pd.DataFrame | None,
    statistic: str = 'total_present_costs_discounted',
    convergence_statistic: _CONVERGENCE_STATISTICS = 'Mean'
):
    """Patch to update an existing convergence plot with new results, without redrawing it.

    Args:
        psa_data: The results of the PSA; None to clear the plot.
        statistic: The statistic of the model whose convergence is plotted.
        convergence_statistic: The statistic of the samples.

    Returns:
        The patch (a Dash `Patch`) of the figure.
    """
    fig_patch = Patch()

    if psa_data is None:
        # Clear convergence trace, final value, and bounds
        for data_idx in range(4):
            fig_patch['data'][data_idx]['x'] = []
            fig_patch['data'][data_idx]['y'] = []
        
        return fig_patch
    
    con_data = psa_convergence_data(psa_data, statistic, convergence_statistic)
    bb = psa_convergence_bounds(con_data)

    # Convergence
    data_idx = 0
    fig_patch['data'][data_idx]['x'] = con_data.stat_data['draw']
    fig_patch['data'][data_idx]['y'] = con_data.stat_data['cumstat']

    # Final value
    data_idx += 1
    fig_patch['data'][data_idx]['x'] = [0, con_data.stat_data['draw'].iloc[-1]*1.1]
    fig_patch['data'][data_idx]['y'] = [con_data.final_stat, con_data.final_stat]

    # Lower bound
    data_idx += 1
    fig_patch['data'][data_idx]['x'] = con_data.stat_data['draw']
    fig_patch['data'][data_idx]['y'] = con_data.stat_data['lower_bound']

    # Upper bound
    data_idx += 1
    fig_patch['data'][data_idx]['x'] = con_data.stat_data['draw']
    fig_patch['data'][data_idx]['y'] = con_data.stat_data['upper_bound']

    # Axes
    fig_patch['layout']['xaxis']['range'] = [bb.xmin, bb.xmax]
    fig_patch['layout']['yaxis']['range'] = [bb.ymin, bb.ymax]
    fig_patch['layout']['yaxis']['title']['text'] = f'{PSA_STATISTIC_LABELS.get(statistic, statistic)} - {convergence_statistic}'

    # Legend
    if (con_data.final_stat - bb.ymin) > 0.5 * (bb.ymax - bb.ymin):
        fig_patch['layout']['legend']['y'] = 0.15
    else:
        fig_patch['layout']['legend']['y'] = 0.95

    return fig_patch

def psa_convergence_controls(page: str):
    """Controls of the convergence plot: which statistic is plotted, and which statistic of its samples.

    Args:
        page: The page that the controls are on, which is part of their ids.

    Returns:
        List of components.
    """
    return [
        html.Div(
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-Convergence-ii'},
            style = {'display': 'none'}
        ),
        dcc.Dropdown(
            options = [
                {'label': v, 'value': k} for k, v in PSA_STATISTIC_LABELS.items()
            ],
            value = list(PSA_STATISTIC_LABELS.keys())[0],
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-statistic-dropdown'},
            searchable = False,
            clearable = False
        ),
        dcc.Dropdown(
            options = CONVERGENCE_STATISTICS,
            value = CONVERGENCE_STATISTICS[0],
            id = {'type': 'psa-graph-plot-control', 'page': page, 'key': 'psa-primary-plot-convergence-statistic-dropdown'},
            searchable = False,
            clearable = False
        ),
    ]

def psa_convergence_arguments(plot_controls):
    """Arguments of the convergence plot from the values of its controls.

    Args:
        plot_controls: The ids and values of the controls, as given to a Dash callback.

    Returns:
        Dictionary of the `statistic` and the `convergence_statistic`.
    """
    statistic = 'net_present_value_discounted'
    convergence_statistic = 'Mean'
    for idx, id in enumerate(plot_controls['ids']):
        if id.get('key') == 'psa-primary-plot-statistic-dropdown':
            statistic = plot_controls['values'][idx]
        elif id.get('key') == 'psa-primary-plot-convergence-statistic-dropdown':
            convergence_statistic = plot_controls['values'][idx]
    rval = dict(statistic = statistic, convergence_statistic = convergence_statistic)
    return rval

psa_plots = {
    'Scatter plot': {
        'draw': psa_scatter,
        'update': psa_scatter_update,
        'controls': psa_scatter_controls,
        'arguments': psa_scatter_arguments,
    },
    'Cumulative probability': {
        'draw': psa_cdf,
        'update': psa_cdf_update,
        'controls': psa_cdf_controls,
        'arguments': psa_cdf_arguments,
    },
    'Convergence': {
        'draw': psa_convergence,
        'update': psa_convergence_update,
        'controls': psa_convergence_controls,
        'arguments': psa_convergence_arguments,
    }
}
