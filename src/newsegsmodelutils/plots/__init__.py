"""Functions drawing figures from the data of the framework.

Modules:
    psa: Plots of the results of a probabilistic sensitivity analysis (PSA).
    optim: The plot of a statistic across the range of a variable, for optimisation.
    wind_resource: Wind roses and wind speed profiles (matplotlib).

A plot which is redrawn in place, such as by a Dash `Patch`, has a function returning the values that depend on its
data (`PlotValues`), which its figure function applies to the figure it styles, and which can be applied in the same
way to a patch of that figure with `apply_values`, so that the figure and its updates share the code that places the
data.
"""
from typing import Any, Hashable, Sequence

PlotValues = list[tuple[tuple[Hashable, ...], Any]]
"""Values of a plot, as the path of each within the figure (e.g. `('data', 0, 'x')` or `('layout', 'xaxis', 'range')`)
and the value."""

def apply_values(target: Any, values: PlotValues) -> Any:
    """Set values within a figure, or within anything indexed as a figure is, such as a Dash `Patch` of it.

    Args:
        target: The figure (e.g. a `plotly.graph_objects.Figure`) or patch.
        values: The values and their paths.

    Returns:
        The target.
    """
    for path, value in values:
        _set(target, path, value)
    return target

def _set(target: Any, path: Sequence[Hashable], value: Any) -> None:
    node = target
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
