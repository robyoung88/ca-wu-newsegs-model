"""The plots of the PSA page: their figures (from `newsegsmodelutils.plots.psa`), the patches that update drawn figures
with new results, their controls, and the arguments read from the values of the controls.

`psa_plots` registers each plot by the name the page offers, with its `draw`, `update`, `controls` and `arguments`
functions. A patch applies the same values as its figure function (`psa_*_values`), so a drawn figure is updated in
the same way as it is drawn.
"""
from dash import Patch, dcc, html

from newsegsmodelframework.newsegssensitivity.psa import CONVERGENCE_STATISTICS, PSA_STATISTIC_LABELS, _CONVERGENCE_STATISTICS
from newsegsmodelutils.plots import apply_values
from newsegsmodelutils.plots import psa as psa_plotting
from newsegsmodelutils.plots.psa import psa_cdf, psa_convergence, psa_scatter

##### Scatter ######

def psa_scatter_update(
    psa_data,
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
    if psa_data is None:
        values = psa_plotting.psa_scatter_cleared_values(show_proportion_ce)
    else:
        values = psa_plotting.psa_scatter_values(psa_data, cost_statistic, benefit_statistic, show_proportion_ce)
    return apply_values(Patch(), values)

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

def psa_cdf_update(
    psa_data,
    statistic: str = 'net_present_value_discounted',
):
    """Patch to update an existing cumulative distribution plot with new results, without redrawing it.

    Args:
        psa_data: The results of the PSA; None to clear the plot.
        statistic: The statistic.

    Returns:
        The patch (a Dash `Patch`) of the figure.
    """
    if psa_data is None:
        values = psa_plotting.psa_cdf_cleared_values()
    else:
        values = psa_plotting.psa_cdf_values(psa_data, statistic)
    return apply_values(Patch(), values)

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

def psa_convergence_update(
    psa_data,
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
    if psa_data is None:
        values = psa_plotting.psa_convergence_cleared_values()
    else:
        values = psa_plotting.psa_convergence_values(psa_data, statistic, convergence_statistic)
    return apply_values(Patch(), values)

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
"""The plots of the PSA page, by the name the page offers, with their `draw`, `update`, `controls` and `arguments`
functions."""
