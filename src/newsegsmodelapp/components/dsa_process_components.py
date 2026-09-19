from dash import dcc, html
from dash_bootstrap_components._components.Modal import Modal as dbc_Modal
from dash_bootstrap_components._components.ModalHeader import ModalHeader as dbc_ModalHeader
from dash_bootstrap_components._components.ModalTitle import ModalTitle as dbc_ModalTitle
from dash_bootstrap_components._components.ModalBody import ModalBody as dbc_ModalBody
from dash_bootstrap_components._components.ModalFooter import ModalFooter as dbc_ModalFooter
from dash_bootstrap_components._components.Button import Button as dbc_Button

def dsa_process_components(**kwargs):
    return [
        dcc.Store(id = {'type': 'trigger', 'page':kwargs.get('page_type', 'None'), 'key': 'dsa_input_change'}, data = []),
        dbc_Modal(
            [
                dbc_ModalHeader(dbc_ModalTitle('Run DSA?')),
                dbc_ModalBody("""
                    Deterministic Sensitivity Analyses require multiple model runs 
                    and can take minutes to hours to complete, dependent on model 
                    complexity. Are you ready to continue?
                """),
                dbc_ModalFooter([
                    dbc_Button(
                        'OK',
                        id = 'btn-action-dsa-run-metamodel',
                        # id = {
                        #     'type': 'action-button', 'purpose': 'request-process',
                        #     'supersection': 'dsa', 'section': 'run',
                        #     'key': 'dsa_run_metamodel', 'subindex': 0,
                        # },
                        n_clicks = 0
                    ),
                    dbc_Button(
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
        dbc_Modal(
            [
                dbc_ModalHeader(dbc_ModalTitle('Download DSA results')),
                dbc_ModalBody([
                    html.H3('Download contents:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Results only', 'value': 'result'},
                            {'label': 'Results and model configuration', 'value': 'result_and_config'}
                        ],
                        'result',
                        id = {'type': 'dsa-result-download-option', 'page': kwargs.get('page_type', 'None'), 'key': 'contents-option'}
                    ),
                    html.H3('Result format:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Comma separated variables (.csv)', 'value': 'csv'},
                            {'label': 'Microsoft® Excel® Spreadsheet (.xlsx)', 'value': 'xlsx'},
                        ],
                        'csv',
                        id = {'type': 'dsa-result-download-option', 'page': kwargs.get('page_type', 'None'), 'key': 'format-option'}
                    )
                ]),
                dbc_ModalFooter([
                    dbc_Button(
                        'OK',
                        id = {'type': 'results-download-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa'},
                        n_clicks = 0
                    ),
                    dbc_Button(
                        'Cancel', 
                        id = {'type': 'modal-close-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-download-confirm'},
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'dsa-download-confirm'},
            is_open = False
        ),
        dcc.Download(id = {'type': 'results-download-component', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa'})
    ]