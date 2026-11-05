"""The plot of a statistic across the range of a variable, which shows the landscape an optimisation searches."""
import pandas as pd
import plotly.express as px

from newsegsmodelframework.newsegssensitivity.optim import OPTIM_TARGET_STATISTIC_LABELS

def statistic_across_margin_plot(plot_data: pd.DataFrame, variable_label: str):
    """Plot a statistic across a range of values of a variable.

    Args:
        plot_data: The result of `optim.evaluate_statistic_across_margin`: the values of the variable and the
            statistic, as its first and second columns.
        variable_label: Label of the variable, for its axis.

    Returns:
        The line plot (a plotly figure).
    """
    fig = px.line(
        plot_data,
        x = plot_data.columns[0],
        y = plot_data.columns[1]
    )

    fig.update_xaxes(
        title = variable_label
    )
    fig.update_yaxes(
        title = OPTIM_TARGET_STATISTIC_LABELS[plot_data.columns[1]]
    )

    return fig
