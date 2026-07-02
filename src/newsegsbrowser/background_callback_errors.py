"""
A handler for errors in background callbacks.
"""
from collections import defaultdict
import json
import logging
from typing import Any

from dash import ALL, dcc, Dash, Input, Output, State, no_update, set_props

logger = logging.getLogger(__name__)

MAX_BACKGROUND_REPEATS = defaultdict(lambda: 5)

def add_background_callback_error_dispatch(app: Dash) -> Dash:
    @app.callback(
        Output({'type': 'background-callback-call', 'target': ALL}, 'data', allow_duplicate = True),
        Output({'type': 'background-callback-return', 'target': ALL}, 'data', allow_duplicate = True),

        Input('background_callback_error_reporter', 'data'),

        State({'type': 'background-callback-call', 'target': ALL}, 'id'),
        State({'type': 'background-callback-call', 'target': ALL}, 'data'),
        State({'type': 'background-callback-return', 'target': ALL}, 'id'),
        prevent_initial_call = True
    )
    def bc_error_dispatch(
        error_target,
        call_ids,
        call_data,
        return_ids,
    ):
        rval: list[Any] = [
            [no_update] * len(call_ids),
            [no_update]* len(return_ids)
        ]

        if error_target is None:
            return tuple(rval)
        
        err_call = None
        err_idx = None
        for idx, id in enumerate(call_ids):
            if id.get('target') == error_target:
                err_idx = idx
                err_call = call_data[idx]
                break
        
        if err_call is None:
            raise ValueError(f'Cannot find call which resulted in background callback exception for {error_target}')
                        
        store_call_id = 'last_bcerr_'+str(error_target)
        store_count_id = 'n_bcerr_'+str(error_target)

        last_err = app.sts.get(store_call_id)
        n_repeats = 0
        if last_err is not None:
            if err_call == last_err:
                n_repeats = app.sts.get(store_count_id, 0)
        
        n_repeats += 1
        if n_repeats > MAX_BACKGROUND_REPEATS[str(error_target)]:
            # Attach a failure indicator to the call object and pass onwards to the appropriate return
            call_ = json.loads(err_call)
            call_['success'] = False
            err_call = json.dumps(call_)
            for idx, id in enumerate(return_ids):
                if id.get('target') == error_target:
                    rval[1][idx] = err_call
        else:
            app.sts[store_call_id] = err_call
            app.sts[store_count_id] = n_repeats
            rval[0][err_idx] = err_call
        
        return tuple(rval)
    
    return app

def background_callback_error_handler_factory(target):
    def error_handler(err: Exception):
        logger.error(str(err))
        last_call_ = err.args[0].split('\n')[-1]
        if 'NoSuchProcess' in last_call_:
            set_props('background_callback_error_reporter', {'data': target})
        else:
            raise(err)
    return error_handler

def background_callback_error_handler_components():
    return [
        dcc.Store(id = 'background_callback_error_reporter', data = None)
    ]
