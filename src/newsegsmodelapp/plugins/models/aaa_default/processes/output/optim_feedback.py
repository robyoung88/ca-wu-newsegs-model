"""The feedback shown after an optimisation: what it achieved, from the `optimisation_result` saved by
`optim_single_mm`.

On success, the statistic before and after with the improvement, the change in each variable, and
the configuration created; on failure, why, what to try, and the best value found; and, when no
variables were selected, that nothing was run. The optimiser's own result is kept in a closed
Details, for diagnosis.
"""
import math

from dash import html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelframework.newsegssensitivity import optim

_SUGGESTIONS = [
    'Try another optimisation method.',
    'Vary different variables, or fewer of them.',
    'Widen the bounds of the variables.',
]

def _relative_tolerance(value: float) -> float:
    return 1e-9 * max(1., abs(value))

def is_improvement(start: float, final: float, maximised: bool) -> bool:
    """Whether a final value of a statistic is better than its start, beyond rounding error.

    Args:
        start: The value before optimisation.
        final: The value after.
        maximised: Whether the statistic is maximised.

    Returns:
        True if the final value is better.
    """
    change = final - start if maximised else start - final
    return change > _relative_tolerance(start)

def format_money(value: float) -> str:
    """A value in pounds, to the nearest pound, e.g. '£12,345' or '−£12,345'."""
    sign = '−' if value < 0 and round(value) != 0 else ''
    return f'{sign}£{abs(value):,.0f}'

def format_value(value: float) -> str:
    """A value of a variable, to 6 significant figures (or the nearest whole number, if larger), with
    thousands separators and without trailing zeros, e.g. '1,234,567' or '135.5'."""
    if not math.isfinite(value):
        return 'none'
    if value == 0:
        return '0'
    decimals = max(0, 6 - (math.floor(math.log10(abs(value))) + 1))
    text = f'{value:,.{decimals}f}'
    return text.rstrip('0').rstrip('.') if decimals else text

def improvement_summary(result: dict) -> str:
    """One sentence saying how the statistic changed in an optimisation.

    The relative change is given only when the start is positive, as it is undefined or misleading
    otherwise.

    Args:
        result: The `optimisation_result` of a successful optimisation.

    Returns:
        The sentence, e.g. 'NPV (discounted) improved by £12,345 (+8.2%), from £150,000 to £162,345.'
    """
    label = optim.OPTIM_TARGET_STATISTIC_LABELS.get(result['statistic'], result['statistic'])
    start, final = result['start_value'], result['final_value']
    if not is_improvement(start, final, result['maximised']):
        return (
            f'{label} did not improve: the configuration is already at or near its best within the bounds '
            f'({format_money(start)}).'
        )
    change = abs(final - start)
    verb = 'improved' if result['maximised'] else 'reduced'
    relative = f' ({(final - start) / start:+.1%})' if start > 0 else ''
    return f'{label} {verb} by {format_money(change)}{relative}, from {format_money(start)} to {format_money(final)}.'

def variables_table(result: dict):
    """Table of the variables varied, with their values before and after, and their bounds."""
    header = html.Thead(html.Tr([html.Th(x) for x in ('Variable', 'Before', 'After', 'Lower bound', 'Upper bound')]))
    rows = [
        html.Tr([
            html.Td(v['label']),
            html.Td(format_value(v['before'])),
            html.Td(format_value(v['after'])),
            html.Td(format_value(v['lower'])),
            html.Td(format_value(v['upper'])),
        ])
        for v in result['variables']
    ]
    return dbc.Table([header, html.Tbody(rows)], striped = True, bordered = False, hover = True, size = 'sm')

def _diagnostics(result: dict):
    return html.Details(
        [
            html.Summary('Optimiser details', style = {'cursor': 'pointer'}),
            html.Pre(str(result.get('opt')), className = 'small'),
        ],
        className = 'mt-2',
    )

def create_optimisation_feedback(result: dict) -> list:
    """The feedback shown after an optimisation.

    Args:
        result: The `optimisation_result` saved by the optimisation.

    Returns:
        The components.
    """
    status = result.get('status')
    if status is None:
        # Saved before the feedback recorded the statistic
        return _legacy_feedback(result)

    if status == 'not_run':
        return [
            html.H4('Optimisation not run'),
            html.P('No variables are selected for optimisation. Select the variables to vary, and set their bounds, then run it again.'),
        ]

    label = optim.OPTIM_TARGET_STATISTIC_LABELS.get(result['statistic'], result['statistic'])
    if status == 'success':
        children = [
            html.H4('Optimisation complete'),
            html.P(improvement_summary(result), className = 'lead'),
            variables_table(result),
        ]
        if is_improvement(result['start_value'], result['final_value'], result['maximised']):
            children.append(html.P([
                'The optimised values are in the new configuration ',
                html.B(result['new_metamodel_name']),
                ', added to the project.',
            ]))
        children.append(_diagnostics(result))
        return children

    children = [
        html.H4('Optimisation did not succeed'),
        html.P(f'The optimiser stopped without finding a best value of {label}: {result["message"]}'),
    ]
    if is_improvement(result['start_value'], result['final_value'], result['maximised']):
        children.append(html.P(
            f'The best value it found, {format_money(result["final_value"])}, is better than the configuration\'s '
            f'{format_money(result["start_value"])}, but has not been saved.'
        ))
    children += [
        html.P('To try again:', className = 'mb-1'),
        html.Ul([html.Li(x) for x in _SUGGESTIONS]),
        _diagnostics(result),
    ]
    return children

def _legacy_feedback(result: dict) -> list:
    opt = result.get('opt')
    if result.get('success'):
        return [html.H4('Optimisation complete'), _diagnostics(result)]
    return [
        html.H4('Optimisation did not succeed'),
        html.P(f'{getattr(opt, "message", "")}'),
        html.Ul([html.Li(x) for x in _SUGGESTIONS]),
        _diagnostics(result),
    ]
