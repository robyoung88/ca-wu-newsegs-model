"""Components needed by the DSA process.
"""
from dash import dcc, html

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
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Download DSA results')),
                dbc.ModalBody([
                    html.H3('Download contents:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Results only', 'value': 'result'},
                            {'label': 'Results and model configuration', 'value': 'result_and_config'}
                        ],
                        'result',
                        id = {'type': 'dsa-result-download-option', 'key': 'contents-option'}
                    ),
                    html.H3('Result format:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Comma separated variables (.csv)', 'value': 'csv'},
                            {'label': 'Microsoft® Excel® Spreadsheet (.xlsx)', 'value': 'xlsx'},
                        ],
                        'csv',
                        id = {'type': 'dsa-result-download-option', 'key': 'format-option'}
                    )
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = 'btn-dsa-download-confirm-ok',
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = 'btn-dsa-download-confirm-abort',
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = 'modal-dsa-download-confirm',
            is_open = False
        ),
        dcc.Download(id = 'download-dsa-result')
    ]