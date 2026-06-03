from collections.abc import Mapping, Callable

from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser import icons
from src.newsegsbrowser.layouts.results import results_details

def create_economic_results_so_card(results_table_functions: Mapping[str, Callable]):
    """
    A bootstrap card holding economic results from the system owner perspective
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('cost'), 'Financial Results - System Owner'],
            className='card-title'),

            html.H4([
                'Total benefits (',
                html.Span('0%'),
                ') = ',
                html.Span('£0.00'),
                '; Total costs (',
                html.Span('0%'),
                ') = ',
                html.Span('£0.00'),
                '; NPV = ',
                html.Span('£0.00'),
            ],
            id='finance-ressmry-container',
            className='card-subtitle'),

            results_details.create_results_details(
                results_table_functions,
                'so_benefits',
                'Benefits',
                'finance_so'
            ),

            results_details.create_results_details(
                results_table_functions,
                'so_costs',
                'Costs',
                'finance_so'
            ),

            results_details.create_results_details(
                results_table_functions,
                'so_value',
                'Value',
                'finance_so'
            ),
        ])
    ])
