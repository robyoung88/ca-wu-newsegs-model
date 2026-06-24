from collections.abc import Mapping, Callable

from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser.layouts.results import results_details

def create_storage_results_card(results_table_functions: Mapping[str, Callable]):
    """
    A bootstrap card holding storage results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('storage'), 'Storage Results'],
            className='card-title'),

            html.H4([
                'Hours full = ',
                html.Span("0"),
                "; Hours empty = ",
                html.Span("0"),
                "; Charge cycles = ",
                html.Span("0")
            ],
            id = {'type': 'result-header', 'section': 'deterministic-results', 'key': 'stor-ressmry'},
            #id='stor-ressmry-container',
            className='card-subtitle'),

            results_details.create_results_details(
                results_table_functions,
                'storage',
                'Storage',
                'storage'
            ),
        ])
    ])
