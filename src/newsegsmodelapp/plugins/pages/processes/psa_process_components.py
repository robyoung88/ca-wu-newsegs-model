"""Psa process components module.

TODO: Describe the purpose of the module.
"""
from dash import dcc, html

import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def psa_process_components(**kwargs):
    """Psa process components.

    TODO: Add a description.

    Args:
        **kwargs: TODO.

    Returns:
        TODO.
    """
    return [
        dcc.Store(id = {'type': 'trigger', 'page':kwargs.get('page_type', 'None'), 'key': 'psa_input_change'}, data = []),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Run PSA?')),
                dbc.ModalBody('Probabilistic Sensitivity Analyses require a large number of model runs (often > 1000) and can take minutes to hours to complete, dependent on model complexity. Are you ready to continue?'),
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
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Download PSA results')),
                dbc.ModalBody([
                    html.H3('Download contents:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Results only', 'value': 'result'},
                            {'label': 'Results and model configuration', 'value': 'result_and_config'}
                        ],
                        'result',
                        id = {'type': 'psa-result-download-option', 'key': 'contents-option'}
                    ),
                    html.H3('Result format:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Comma separated variables (.csv)', 'value': 'csv'},
                            {'label': 'Microsoft® Excel® Spreadsheet (.xlsx)', 'value': 'xlsx'},
                        ],
                        'csv',
                        id = {'type': 'psa-result-download-option', 'key': 'format-option'}
                    )
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        #id = {'type': 'results-download-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
                        id = 'btn-psa-download-confirm-ok',
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        #id = {'type': 'modal-close-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-download-confirm'},
                        id = 'btn-psa-download-confirm-abort',
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            #id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'psa-download-confirm'},
            id = 'modal-psa-download-confirm',
            is_open = False
        ),
        dcc.Download(id = 'download-psa-result')
    ]
