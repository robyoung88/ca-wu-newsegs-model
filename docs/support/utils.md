# Plotting utilities (`newsegsmodelutils`)

`newsegsmodelutils` holds what both the framework and the app use but belongs to neither: at present, the functions
that draw figures from the data of the framework. It may use `newsegsmodelframework`, Plotly and matplotlib, but not
Dash or `newsegsmodelapp`. The framework does not use it, so the framework has no plotting dependencies; a test
(`test_framework_independent_of_frontend.py`) imports every module of the framework with Dash and the plotting
libraries blocked.

| Module | Contents |
|---|---|
| `plots.psa` | The scatter of costs and benefits, the cumulative distribution and the convergence of a PSA |
| `plots.optim` | The plot of a statistic across the range of a variable, for an optimisation |
| `plots.wind_resource` | Wind roses, energy roses and wind speed profiles (matplotlib) |

## Plots updated in place

The PSA page updates a drawn plot with new results through a Dash `Patch`, rather than drawing it again. So that the
update and the figure place the data in the same way, each such plot has a function returning the values that depend
on the data, as the path of each within the figure and its value (`PlotValues`):

```python
values = psa_scatter_values(psa_data)       # e.g. [(('data', 0, 'x'), ...), (('layout', 'xaxis', 'range'), ...), ...]

fig = psa_scatter(psa_data)                 # styles the figure, then apply_values(fig, values)
patch = apply_values(Patch(), values)       # in the app: newsegsmodelapp.components.psa_plots
```

`apply_values` sets each value by indexing the target, which works on a Plotly figure and on a Dash `Patch` alike, so
the plotting functions do not need Dash. The values clearing a plot are given by `psa_*_cleared_values`.

The patches, the controls of the plots, the arguments read from the controls, and the registry of the plots the PSA
page offers (`psa_plots`) are Dash-specific, so are in the app (`newsegsmodelapp.components.psa_plots`).

## API

::: newsegsmodelutils
    options:
        show_submodules: true
