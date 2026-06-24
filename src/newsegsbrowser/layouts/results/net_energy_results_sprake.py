from collections.abc import Mapping, Callable

from dash import html
import dash_bootstrap_components as dbc

from newsegsbrowser import icons
from newsegsbrowser.layouts.results import results_details


def create_net_results_card(results_table_functions: Mapping[str, Callable]):
    """
    A bootstrap card holding net energy flow results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('import-export'), 'Net Energy Results'],
            className='card-title'),

            html.H4([
                'Annual export = ',
                html.Span('0.0'),
                ' kWh; Annual import = ',
                html.Span('0.0'),
                ' kWh; Storage losses = ',
                html.Span('0.0'),
                ' kWh'
            ],
            id = {'type': 'result-header', 'section': 'deterministic-results', 'key': 'net-ressmry'},
            #id='net-ressmry-container',
            className='card-subtitle'),

            results_details.create_results_details(
                results_table_functions,
                'net_energy',
                'Overall net energy',
                'net'
            ),
            results_details.create_results_details(
                results_table_functions,
                'seasonal_net_energy',
                'Seasonal net energy',
                'net'
            ),
        ])
    ])