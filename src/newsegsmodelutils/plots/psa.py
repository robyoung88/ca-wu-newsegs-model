"""Plots of the results of a probabilistic sensitivity analysis (PSA): the scatter of costs and benefits, the
cumulative distribution of a statistic, and the convergence of a statistic over the draws.

The data of each plot come from `newsegsmodelframework.newsegssensitivity.psa`. Each plot has a function returning the
values that depend on the data (`psa_*_values`), which its figure function (`psa_scatter`, `psa_cdf`,
`psa_convergence`) applies, and which the app applies to a Dash `Patch` to update a drawn figure; and the values that
clear a drawn figure (`psa_*_cleared_values`).
"""
from typing import NamedTuple

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from newsegsmodelframework.newsegssensitivity.psa import (
    PSA_STATISTIC_LABELS, PSACDFData, PSAConvergenceData, _CONVERGENCE_STATISTICS,
    get_null_psa_data, psa_cdf_data, psa_convergence_data, psa_scatter_data,
)
from newsegsmodelutils.plots import PlotValues, apply_values

class BoundingBox(NamedTuple):
    """Bounding box of a set of points.
    """
    xmin: float
    ymin: float
    xmax: float
    ymax: float

##### Scatter ######

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

def psa_scatter_values(
    psa_data: pd.DataFrame,
    cost_statistic: str = 'total_present_costs_discounted',
    benefit_statistic: str = 'total_present_benefits_discounted',
    show_proportion_ce: bool = True,
) -> PlotValues:
    """The values of the scatter plot of costs and benefits which depend on the results of the PSA.

    The cost effective and other samples (traces 0 and 1), the deterministic point (trace 2), the line of equal costs
    and benefits, the axes, and the proportion cost effective.

    Args:
        psa_data: The results of the PSA.
        cost_statistic: The statistic used as costs.
        benefit_statistic: The statistic used as benefits.
        show_proportion_ce: Whether the plot annotates the proportion of samples that are cost effective.

    Returns:
        The values.
    """
    plot_data = psa_scatter_data(psa_data, cost_statistic, benefit_statistic)
    bb = psa_scatter_bounds(plot_data.scatter_data)
    scatterdata = plot_data.scatter_data.set_index('cost_effective')

    values: PlotValues = []
    for trace, category in enumerate(('CE', 'Not CE')):
        if category in scatterdata.index:
            values += [
                (('data', trace, 'x'), pd.Series(scatterdata.loc[category, cost_statistic])),
                (('data', trace, 'y'), pd.Series(scatterdata.loc[category, benefit_statistic])),
            ]
        else:
            values += [(('data', trace, 'x'), []), (('data', trace, 'y'), [])]

    values += [
        # Deterministic
        (('data', 2, 'x'), [plot_data.det_point[cost_statistic]]),
        (('data', 2, 'y'), [plot_data.det_point[benefit_statistic]]),
        # Reference line; xmin should equal ymin of the bounding box, but just in case
        (('layout', 'shapes', 0, 'x0'), bb.xmin),
        (('layout', 'shapes', 0, 'y0'), bb.xmin),
        (('layout', 'shapes', 0, 'x1'), bb.xmax),
        (('layout', 'shapes', 0, 'y1'), bb.xmax),
        # Axes
        (('layout', 'xaxis', 'range'), [bb.xmin, bb.xmax]),
        (('layout', 'xaxis', 'title', 'text'), PSA_STATISTIC_LABELS.get(cost_statistic, cost_statistic)),
        (('layout', 'yaxis', 'range'), [bb.ymin, bb.ymax]),
        (('layout', 'yaxis', 'title', 'text'), PSA_STATISTIC_LABELS.get(benefit_statistic, benefit_statistic)),
    ]
    if show_proportion_ce:
        values.append((('layout', 'annotations', 0, 'text'), f'Proportion CE: {plot_data.ce_proportion:.1%}'))
    return values

def psa_scatter_cleared_values(show_proportion_ce: bool = True) -> PlotValues:
    """The values which clear the samples, the deterministic point and the annotation of a scatter plot, leaving its
    reference line and axes.

    Args:
        show_proportion_ce: Whether the plot annotates the proportion of samples that are cost effective.

    Returns:
        The values.
    """
    values: PlotValues = [(('data', trace, axis), []) for trace in range(3) for axis in ('x', 'y')]
    if show_proportion_ce:
        values.append((('layout', 'annotations', 0, 'text'), ''))
    return values

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

    # The traces of the samples, styled by plotly express from placeholder points of each category
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

    # The reference line
    fig.add_shape(
        type='line',
        line=dict(color='gray', dash='dash'),
        xref='x',
        yref='y'
    )

    # The deterministic point
    fig.add_trace(
        go.Scatter(
            mode='markers',
            marker=dict(size=12, symbol='diamond', color='gold', line=dict(color='black', width=1)),
            name='Deterministic',
            showlegend=True
        )
    )

    # Formatting - axes
    fig.update_xaxes(
        scaleanchor='y',
        scaleratio=1,
    )

    if show_proportion_ce:
        # The proportion cost effective
        fig.add_annotation(
            xref='paper',
            yref='paper',
            x=0.05,
            y=0.95,
            showarrow=False,
            bgcolor='rgba(255, 255, 255, 0.8)',
            bordercolor='black',
            borderwidth=1
        )

    return apply_values(fig, psa_scatter_values(psa_data, cost_statistic, benefit_statistic, show_proportion_ce))

###### CDF #####

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

def psa_cdf_values(
    psa_data: pd.DataFrame,
    statistic: str = 'net_present_value_discounted',
) -> PlotValues:
    """The values of the cumulative distribution plot which depend on the results of the PSA.

    The distribution (trace 0), the deterministic value (the line), the minimum and maximum (the annotations), and the
    horizontal axis.

    Args:
        psa_data: The results of the PSA.
        statistic: The statistic.

    Returns:
        The values.
    """
    cdf_data = psa_cdf_data(psa_data, statistic)
    bb = psa_cdf_bounds(cdf_data)
    return [
        (('data', 0, 'x'), cdf_data.cdf_data.loc[:, statistic]),
        (('data', 0, 'y'), cdf_data.cdf_data.loc[:, 'cdf']),
        # Deterministic reference
        (('layout', 'shapes', 0, 'x0'), cdf_data.det_value),
        (('layout', 'shapes', 0, 'x1'), cdf_data.det_value),
        # Minimum and maximum
        (('layout', 'annotations', 0, 'text'), f'{cdf_data.min:,.2f}'),
        (('layout', 'annotations', 0, 'x'), cdf_data.min),
        (('layout', 'annotations', 0, 'ax'), cdf_data.min + 0.05 * (bb.xmax-bb.xmin)),
        (('layout', 'annotations', 1, 'text'), f'{cdf_data.max:,.2f}'),
        (('layout', 'annotations', 1, 'x'), cdf_data.max),
        (('layout', 'annotations', 1, 'ax'), cdf_data.max - 0.05 * (bb.xmax-bb.xmin)),
        # Axes
        (('layout', 'xaxis', 'range'), [bb.xmin, bb.xmax]),
        (('layout', 'xaxis', 'title', 'text'), PSA_STATISTIC_LABELS.get(statistic, statistic)),
    ]

def psa_cdf_cleared_values() -> PlotValues:
    """The values which clear the distribution and the annotations of a cumulative distribution plot, leaving its
    deterministic line and axes.

    Returns:
        The values.
    """
    return [
        (('data', 0, 'x'), []),
        (('data', 0, 'y'), []),
        (('layout', 'annotations', 0, 'text'), ''),
        (('layout', 'annotations', 1, 'text'), ''),
    ]

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

    fig = px.line(
        cdf_data.cdf_data,
        x = statistic,
        y = 'cdf'
    )

    # The deterministic value
    fig.add_shape(
        type = 'line',
        y0 = -0.1,
        y1 = 1.1,
        line = dict(color='gray', dash='dash'),
        xref = 'x',
        yref = 'y',
    )

    # The minimum
    fig.add_annotation(
        xref = 'x',
        yref = 'y',
        axref = 'x',
        y = 0.0,
        showarrow = True,
        bgcolor='rgba(255, 255, 255, 0.8)',
        bordercolor='black',
        borderwidth=1
    )

    # The maximum
    fig.add_annotation(
        xref = 'x',
        yref = 'y',
        axref = 'x',
        ayref = 'y',
        y = 1.,
        ay = 0.9,
        showarrow = True,
        bgcolor='rgba(255, 255, 255, 0.8)',
        bordercolor='black',
        borderwidth=1
    )

    # Formatting - axes
    fig.update_yaxes(
        title = 'Cumulative probability',
        range = [0., 1.],
    )

    return apply_values(fig, psa_cdf_values(psa_data, statistic))

##### Convergence #####

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

def psa_convergence_values(
    psa_data: pd.DataFrame,
    statistic: str = 'total_present_costs_discounted',
    convergence_statistic: _CONVERGENCE_STATISTICS = 'Mean',
) -> PlotValues:
    """The values of the convergence plot which depend on the results of the PSA.

    The convergence (trace 0), the final value (trace 1), the band of the standard error (traces 2 and 3), the axes,
    and the position of the legend, which is kept clear of the final value.

    Args:
        psa_data: The results of the PSA.
        statistic: The statistic of the model whose convergence is plotted.
        convergence_statistic: The statistic of the samples.

    Returns:
        The values.
    """
    con_data = psa_convergence_data(psa_data, statistic, convergence_statistic)
    bb = psa_convergence_bounds(con_data)
    return [
        # Convergence
        (('data', 0, 'x'), con_data.stat_data['draw']),
        (('data', 0, 'y'), con_data.stat_data['cumstat']),
        # Final value
        (('data', 1, 'x'), [0, con_data.stat_data['draw'].iloc[-1]*1.1]),
        (('data', 1, 'y'), [con_data.final_stat, con_data.final_stat]),
        # Lower and upper bounds
        (('data', 2, 'x'), con_data.stat_data['draw']),
        (('data', 2, 'y'), con_data.stat_data['lower_bound']),
        (('data', 3, 'x'), con_data.stat_data['draw']),
        (('data', 3, 'y'), con_data.stat_data['upper_bound']),
        # Axes
        (('layout', 'xaxis', 'range'), [bb.xmin, bb.xmax]),
        (('layout', 'yaxis', 'range'), [bb.ymin, bb.ymax]),
        (('layout', 'yaxis', 'title', 'text'), f'{PSA_STATISTIC_LABELS.get(statistic, statistic)} - {convergence_statistic}'),
        # Legend, below the final value if it is in the upper half
        (('layout', 'legend', 'y'), 0.15 if (con_data.final_stat - bb.ymin) > 0.5 * (bb.ymax - bb.ymin) else 0.95),
    ]

def psa_convergence_cleared_values() -> PlotValues:
    """The values which clear the convergence, final value and bounds of a convergence plot.

    Returns:
        The values.
    """
    return [(('data', trace, axis), []) for trace in range(4) for axis in ('x', 'y')]

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

    fig = px.line(
        con_data.stat_data,
        x = 'draw',
        y = 'cumstat'
    )

    fig.add_trace(
        go.Scatter(
            mode = 'lines',
            line = dict(color='orange', dash='dash'),
            name = 'Final statistic'
        )
    )

    fig.add_trace(
        go.Scatter(
            mode = 'lines',
            line = dict(color='gray', dash='dash'),
            name = '2 * estimated SE'
        )
    )

    fig.add_trace(
        go.Scatter(
            mode = 'lines',
            line = dict(color='gray', dash='dash'),
            name = '2 * estimated SE',
            showlegend = False
        )
    )

    fig.update_layout(
        legend=dict(
            x=0.99,
            xanchor='right',
            yanchor='top'
        )
    )

    # Formatting - axes
    fig.update_xaxes(
        title = 'Draw',
    )

    return apply_values(fig, psa_convergence_values(psa_data, statistic, convergence_statistic))
