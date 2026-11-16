"""Components needed by the PSA process.
"""
from dash import dcc, html

from newsegsmodelapp.components.results_download import create_results_download_components
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def psa_process_components(**kwargs):
    """Create the components needed by the PSA process, such as the modal which asks for confirmation before a PSA is started.

    Args:
        **kwargs: Further keyword arguments.

    Returns:
        List of components.
    """
    return [
        dcc.Store(id = {'type': 'trigger', 'page':kwargs.get('page_type', 'None'), 'key': 'psa_input_change'}, data = []),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Run PSA?')),
                dbc.ModalBody([
                    html.P('Probabilistic Sensitivity Analyses require a large number of model runs (often > 1000) and can take minutes to hours to complete, dependent on model complexity. Are you ready to continue?'),
                    html.H3('Configurations to analyse:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Selected configuration', 'value': 'metamodel'},
                            {'label': 'All configurations (for comparison, sharing each draw)', 'value': 'project'},
                        ],
                        'metamodel',
                        id = 'psa-run-scope',
                    ),
                    # For all configurations: how many variables have different distributions or SDs across them
                    html.P(id = 'psa-run-differences-note', className = 'psa-run-differences-note'),
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = 'btn-action-psa-run-metamodel',
                        # id = {
                        #     'type': 'action-button', 'purpose': 'request-process',
                        #     'supersection': 'psa', 'section': 'run',
                        #     'key': 'psa_run_metamodel', 'subindex': 0,
                        # },
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = 'btn-psa-confirm-abort',
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = 'modal-psa-confirm',
            is_open = False
        ),
    ] + create_results_download_components('psa')
