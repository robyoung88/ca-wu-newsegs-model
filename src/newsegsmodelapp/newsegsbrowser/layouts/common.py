from dash import dcc, html
import dash_bootstrap_components as dbc

def NULL_LAYOUT(*args, **kwargs):
    return html.Span()

def post_page_load_components(model_type, page_type):
    """App control components which should be the last things loaded onto a page.
    
    Used to trigger callbacks on page load completion.
    """
    return [
        dcc.Store(id = {
            'type': 'firstload-config-watcher',
            'selected_model': model_type, 
            'page_type': page_type
        }),
        html.Div(id = {
            'type': 'onload-div',
            'selected_model': model_type, 
            'page_type': page_type
        })
    ]

def user_action_components(**kwargs):
    return [
        # A queue of actions performed by the user
        # Generally will hold changes to model and finance configurations
        # to enact.
        dcc.Store(id = 'queue-action-user', data = []),
        # A pre-queue holds individual actions on the way to the queue
        # manager
        dcc.Store(id = 'prequeue-action-user', data = []),
        # A dispatch object holds actions that may be handled by the
        # dispatcher.
        dcc.Store(id = 'dispatchitem-action-user'),
        # An Interval element is necessary to trigger the queue until
        # it is cleared
        dcc.Interval(id = 'interval-action-user', interval = 1000, disabled = True),

        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Download deterministic results')),
                dbc.ModalBody([
                    html.H3('Download contents:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Results only', 'value': 'result'},
                            {'label': 'Results and model configuration', 'value': 'result_and_config'}
                        ],
                        'result',
                        id = {'type': 'det-result-download-option', 'page': kwargs.get('page_type', 'None'), 'key': 'contents-option'}
                    ),
                    html.H3('Result format:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Comma separated variables (.csv)', 'value': 'csv'},
                            {'label': 'Microsoft® Excel® Spreadsheet (.xlsx)', 'value': 'xlsx'},
                        ],
                        'csv',
                        id = {'type': 'det-result-download-option', 'page': kwargs.get('page_type', 'None'), 'key': 'format-option'}
                    )
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = {'type': 'results-download-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'det'},
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = {'type': 'modal-close-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'det-download-confirm'},
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'det-download-confirm'},
            is_open = False
        ),
        dbc.Toast(
            ['No results available for selected model'],
            id = {'type': 'result-download-feedback-toast', 'page': kwargs.get('page_type', 'None'), 'key': 'det'},
            header = 'Result download error',
            icon = 'warning',
            dismissable = True,
            is_open = False,
            duration = 5000,
            style={"position": "fixed", "top": 66, "right": 10, "width": 350},
        ),
        dcc.Store(id = {'type': 'result-download-information', 'page': kwargs.get('page_type', 'None'), 'key': 'det'}),
        dcc.Download(id = {'type': 'results-download-component', 'page': kwargs.get('page_type', 'None'), 'key': 'det'})
    ]
