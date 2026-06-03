from collections.abc import Mapping, Callable

from dash import html
import dash_bootstrap_components as dbc

from src.newsegsbrowser import icons
from src.newsegsbrowser.layouts.results import results_details

def create_consumption_results_card(results_table_functions: Mapping[str, Callable]):
    """
    A bootstrap card holding consumption results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('consumption-direct'), 'Consumption Results'],
            className='card-title'),

            html.H4([
                'Annual consumption: ',
                icons.get_icon('consumption-building'),
                ' = ',
                html.Span('0.0'),
                ' kWh; ',
                icons.get_icon('consumption-direct-ev'),
                ' = ',
                html.Span('0.0'),
                ' kWh'                
            ],
            id='cons-ressmry-container',
            className='card-subtitle'),

            results_details.create_results_details(
                results_table_functions,
                'consumption',
                'Consumption',
                'consumption'
            ),

            results_details.create_results_details(
                results_table_functions,
                'seasonal_consumption',
                'Seasonal Consumption',
                'consumption'
            ),
        ])
    ])