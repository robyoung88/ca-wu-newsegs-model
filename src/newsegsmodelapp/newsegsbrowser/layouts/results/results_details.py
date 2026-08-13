from collections.abc import Mapping, Callable

from dash import html

def create_results_details(
    results_table_functions: Mapping[str, Callable],
    function_key: str,
    title: str,
    results_section: str,
) -> html.Details:
    """
    A html.Details holding the (blank) results table defined by the function.

    Use this to ensure that the created container is given an id that matches
    the function key.
    """
    return html.Details([
        html.Summary(title),
        html.Div([
            results_table_functions[function_key]()
            ],
            id = {'type': 'results-table', 'section': results_section, 'key': function_key})
    ])
