"""Components needed by the DSA process.
"""
from dash import dcc, html

from newsegsmodelapp.components.results_download import create_results_download_components
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc


def dsa_process_components(**kwargs):
    """Create the components needed by the DSA process: the trigger store, and the modal which asks for confirmation before a DSA is started.

    Args:
        **kwargs: Further keyword arguments.

    Returns:
        List of components.
    """
    return [
        dcc.Store(id = {'type': 'trigger', 'page':kwargs.get('page_type', 'None'), 'key': 'dsa_input_change'}, data = []),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Run DSA?')),
                dbc.ModalBody([
                    html.P("""
                        Deterministic Sensitivity Analyses require multiple model runs
                        and can take minutes to hours to complete, dependent on model
                        complexity. Are you ready to continue?
                    """),
                    html.H3('Configurations to analyse:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Selected configuration', 'value': 'metamodel'},
                            {'label': 'All configurations (for comparison)', 'value': 'project'},
                        ],
                        'metamodel',
                        id = 'dsa-run-scope',
                    ),
                    # For all configurations: how many variables have different bounds across them
                    html.P(id = 'dsa-run-bounds-note', className = 'dsa-run-bounds-note'),
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = 'btn-action-dsa-run-metamodel',
                        # id = {
                        #     'type': 'action-button', 'purpose': 'request-process',
                        #     'supersection': 'dsa', 'section': 'run',
                        #     'key': 'dsa_run_metamodel', 'subindex': 0,
                        # },
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = 'btn-dsa-confirm-abort',
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = 'modal-dsa-confirm',
            is_open = False
        ),
    ] + create_results_download_components('dsa')