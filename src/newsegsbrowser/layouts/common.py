from dash import dcc, html
import dash_bootstrap_components as dbc

def NULL_LAYOUT(*args, **kwargs):
    return html.Span()

def post_page_load_components(model_type, page_type):
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

def user_action_components():
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
    ]

def model_run_components(**kwargs):
    return [
        # A queue of model run requests
        # Will generally get added to when a configuration changes
        # but the running of the model is latched off
        # The queue is now held statefully by the app due to issues with
        # state captures in near callbacks - i.e. if two callbacks triggered
        # close to each other, the latter would capture state before the queue
        # was updated following the first.
        # dcc.Store(id = 'queue-model-run', data = []),
        # A pre-queue to transfer model run requests to the queue
        # manager
        dcc.Store(id = 'prequeue-model-run', data = []),
        # An Interval element to trigger the queue until it is cleared
        dcc.Interval(id = 'interval-model-run', interval = 1000, disabled = True),
        # A dispatch object holding id of a model permitted to run
        dcc.Store(id = 'dispatchitem-model-run', data = None),
        # Trigger object for the model run
        dcc.Store(id = {'type': 'background-callback-call', 'target': 'model-run'}),
        # Trigger object for relocalising model after run
        dcc.Store(id = {'type': 'background-callback-return', 'target': 'model-run'}),
        # A store to trigger handling of model run completion
        dcc.Store(id = 'trigger-postprocess-model-run'),

        # Locks to control model running
        dcc.Store(id = {'type': 'lock', 'target': 'model-run', 'stage': 'prequeue', 'key': 'user-toggle'}, data = True),
        dcc.Store(id = {'type': 'lock', 'target': 'model-run', 'stage': 'prequeue', 'key': 'page-control'}, data = kwargs.get('autorun_model', True)),
        dcc.Store(id = {'type': 'lock', 'target': 'model-run', 'stage': 'dispatch', 'key': 'process-in-use'}, data = True),
    ]

def finance_run_components(**kwargs):
    return [
        # A queue of finance run requests
        # A pre-queue to transfer finance run requests to the queue
        # manager
        dcc.Store(id = 'prequeue-finance-run', data = []),
        # The queue to hold scheduled finance runs
        # The queue is now held statefully by the app due to issues with
        # state captures in near callbacks - i.e. if two callbacks triggered
        # close to each other, the latter would capture state before the queue
        # was updated following the first.
        # dcc.Store(id = 'queue-finance-run', data = []),
        # An Interval to trigger the queue manager until queue is cleared
        dcc.Interval(id = 'interval-finance-run', interval = 1000, disabled = True),
        # A dispatch object holding id of a finance permitted to run
        dcc.Store(id = 'dispatchitem-finance-run'),
        # Trigger object for the finance run
        dcc.Store(id = {'type': 'background-callback-call', 'target': 'finance-run'}),
        # Trigger object for relocalising finance after run
        dcc.Store(id = {'type': 'background-callback-return', 'target': 'finance-run'}),
        # Trigger handling of finance run completion
        dcc.Store(id = 'trigger-postprocess-finance-run'),

        # Locks to control finance running
        dcc.Store(id = {'type': 'lock', 'target': 'finance-run', 'stage': 'prequeue', 'key': 'user-toggle'}, data = True),
        dcc.Store(
            id = {'type': 'lock', 'target': 'finance-run', 'stage': 'prequeue', 'key': 'page-control'}, 
            data = kwargs.get('autorun_finance', kwargs.get('autorun_model', True))
        ),
        dcc.Store(id = {'type': 'lock', 'target': 'finance-run', 'stage': 'dispatch', 'key': 'process-in-use'}, data = True),
    ]

def metamodel_process_components():
    return [
        # A queue of model run requests
        # Will generally get added to when a configuration changes
        # but the running of the model is latched off
        # The queue is now held statefully by the app due to issues with
        # state captures in near callbacks - i.e. if two callbacks triggered
        # close to each other, the latter would capture state before the queue
        # was updated following the first.
        # dcc.Store(id = 'queue-metamodel-process', data = []),
        # A pre-queue to transfer model run requests to the queue
        # manager
        dcc.Store(id = 'prequeue-metamodel-process', data = []),
        # An Interval element to trigger the queue until it is cleared
        dcc.Interval(id = 'interval-metamodel-process', interval = 500, disabled = True),
        # A dispatch object holding id of a model permitted to run
        dcc.Store(id = 'dispatchitem-metamodel-process'),
        # Trigger object for the model run
        dcc.Store(id = {'type': 'background-callback-call', 'target': 'metamodel-process'}),
        # Trigger object for relocalising model after run
        dcc.Store(id = {'type': 'background-callback-return', 'target': 'metamodel-process'}),
        # A store to trigger handling of model run completion
        dcc.Store(id = 'trigger-postprocess-metamodel-process'),
        
        # Locks to control metamodel processing
        dcc.Store(id = {'type': 'lock', 'target': 'metamodel-process', 'stage': 'dispatch', 'key': 'process-in-use'}, data = True),

        dcc.Store(id = 'background_cancel_trigger'),
        dcc.Store(id = 'background_progress_tracker', data = '{"value":"0","max":"1"}'),
    ]

def dsa_process_components(**kwargs):
    return [
        dcc.Store(id = {'type': 'trigger', 'page':kwargs.get('page_type', 'None'), 'key': 'dsa_input_change'}, data = []),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Run DSA?')),
                dbc.ModalBody('Deterministic Sensitivity Analyses require multiple model runs and can take minutes to hours to complete, dependent on model complexity. Are you ready to continue?'),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = {'type': 'dsa-run-button', 'page': kwargs.get('page_type', 'None')},
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = {'type': 'modal-close-button', 'page': kwargs.get('page_type', 'None'), 'key': 'dsa-run-confirm'},
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'dsa-run-confirm'},
            is_open = False
        )
    ]

def psa_process_components(**kwargs):
    return [
        dcc.Store(id = {'type': 'trigger', 'page':kwargs.get('page_type', 'None'), 'key': 'psa_input_change'}, data = []),
        dbc.Modal(
            [
                dbc.ModalHeader(dbc.ModalTitle('Run PSA?')),
                dbc.ModalBody('Probabilistic Sensitivity Analyses require a large number of model runs (often > 1000) and can take minutes to hours to complete, dependent on model complexity. Are you ready to continue?'),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = {'type': 'psa-run-button', 'page': kwargs.get('page_type', 'None')},
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = {'type': 'modal-close-button', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-run-confirm'},
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'psa-run-confirm'},
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
                        id = {'type': 'psa-result-download-option', 'page': kwargs.get('page_type', 'None'), 'key': 'contents-option'}
                    ),
                    html.H3('Result format:'),
                    dcc.RadioItems(
                        [
                            {'label': 'Comma separated variables (.csv)', 'value': 'csv'},
                            {'label': 'Microsoft® Excel® Spreadsheet (.xlsx)', 'value': 'xlsx'},
                        ],
                        'csv',
                        id = {'type': 'psa-result-download-option', 'page': kwargs.get('page_type', 'None'), 'key': 'format-option'}
                    )
                ]),
                dbc.ModalFooter([
                    dbc.Button(
                        'OK',
                        id = {'type': 'results-download-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'},
                        n_clicks = 0
                    ),
                    dbc.Button(
                        'Cancel', 
                        id = {'type': 'modal-close-btn', 'page': kwargs.get('page_type', 'None'), 'key': 'psa-download-confirm'},
                        className = 'ms-auto',
                        n_clicks = 0
                    )
                ]),
            ],
            id = {'type': 'modal-confirm', 'page': kwargs.get('page_type', 'None'), 'key':'psa-download-confirm'},
            is_open = False
        ),
        dcc.Download(id = {'type': 'results-download-component', 'page': kwargs.get('page_type', 'None'), 'key': 'psa'})
    ]
