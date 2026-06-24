from dash import dcc, html

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

def model_run_components():
    return [
        # A queue of model run requests
        # Will generally get added to when a configuration changes
        # but the running of the model is latched off
        dcc.Store(id = 'queue-model-run', data = []),
        # A pre-queue to transfer model run requests to the queue
        # manager
        dcc.Store(id = 'prequeue-model-run', data = []),
        # An Interval element to trigger the queue until it is cleared
        dcc.Interval(id = 'interval-model-run', interval = 1000, disabled = True),
        # A dispatch object holding id of a model permitted to run
        dcc.Store(id = 'dispatchitem-model-run'),
        # Trigger object for the model run
        dcc.Store(id = 'trigger-model-run'),
        # Trigger object for relocalising model after run
        dcc.Store(id = 'trigger-post-model-run'),
        # A store to trigger handling of model run completion
        dcc.Store(id = 'trigger-postprocess-model-run'),
        # A global switch to disable model runs
        dcc.Store(id = 'latch-model-run-global', data = True),
    ]

def finance_run_components():
    return [
        # A queue of finance run requests
        # A pre-queue to transfer finance run requests to the queue
        # manager
        dcc.Store(id = 'prequeue-finance-run', data = []),
        # The queue to hold scheduled finance runs
        dcc.Store(id = 'queue-finance-run', data = []),
        # An Interval to trigger the queue manager until queue is cleared
        dcc.Interval(id = 'interval-finance-run', interval = 1000, disabled = True),
        # A dispatch object holding id of a finance permitted to run
        dcc.Store(id = 'dispatchitem-finance-run'),
        # Trigger object for the finance run
        dcc.Store(id = 'trigger-finance-run'),
        # Trigger object for relocalising finance after run
        dcc.Store(id = 'trigger-post-finance-run'),
        # Trigger handling of finance run completion
        dcc.Store(id = 'trigger-postprocess-finance-run'),
        # A global switch to disable finance runs
        dcc.Store(id = 'latch-finance-run-global', data = True),
    ]