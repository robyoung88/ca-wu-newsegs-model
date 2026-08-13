from collections.abc import Mapping, Callable

from dash import html
import dash_bootstrap_components as dbc

from newsegsmodelapp.newsegsbrowser import icons
from newsegsmodelapp.newsegsbrowser.layouts.results import results_details

def create_generation_results_card(results_table_functions: Mapping[str, Callable]):
    """
    A bootstrap card holding generation results
    """
    return dbc.Card([
        dbc.CardBody([
            html.H2([icons.get_icon('generation'), 'Generation Results'],
            className='card-title'),

            html.H4([
                'Annual generation: ',
                icons.get_icon('generation'),
                " = ",
                html.Span("0.0"),
                " kWh; ",
                icons.get_icon('gen-wind'),
                " = ",
                html.Span("0.0"),
                " kWh; ",
                icons.get_icon('gen-pv'),
                " = ",
                html.Span("0.0"),
                " kWh"
            ],
            id = {'type': 'result-header', 'section': 'deterministic-results', 'key': 'gen-ressmry'},
            #id='gen-ressmry-container',
            className='card-subtitle'),

            results_details.create_results_details(
                results_table_functions,
                'wind',
                'Wind Generation',
                'generation'
            ),

            results_details.create_results_details(
                results_table_functions,
                'pv',
                'Solar PV Generation',
                'generation'
            ),
            
            results_details.create_results_details(
                results_table_functions,
                'combined_generation',
                'Total Generation',
                'generation'
            ),
        ])
    ])
