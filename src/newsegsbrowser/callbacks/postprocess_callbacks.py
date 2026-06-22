import json
import logging

from dash import Dash, Input, no_update, Output, State

from newsegsbrowser import common as browser
from newsegsbrowser.callbacks import callbacks_map

logger = logging.getLogger(__name__)

def add_postprocess_callbacks(app: Dash):

    @app.callback(
        Output('prequeue-finance-run', 'data', allow_duplicate = True),
        Input('trigger-post-model-run', 'data'),
        State('prequeue-finance-run', 'data'),
        State('store-configurations', 'data'),
        prevent_initial_call = True
    )
    def trigger_finance_after_model_run(
        model_run, 
        prequeue_finance_run, 
        store_configurations
    ):
        """
        Postprocess and trigger updates from a completed model run.

        A completed model run should result in the following actions:
        1. For any configuration where the finance is associated with this 
           model, queue up a finance run.
        2. If the model is the model of the selected configuration, update the
           main results.
        3. Update the model results in the View.

        The latter two processes are handled by separate postprocess callbacks.
        Therefore, this callback only dispatches to the finance run queue.
        """
        NUP = no_update
        if model_run is None or store_configurations is None:
            return NUP
        
        model_run = json.loads(model_run)

        if prequeue_finance_run is None:
            prequeue_finance_run = []
        
        model_id = model_run['model_id']

        do_update = False
        for s_config in store_configurations:
            config = json.loads(s_config)
            if config['model_id'] == model_id:
                prequeue_finance_run.append(
                    json.dumps(
                        browser.finance_run_request(config['metamodel_id'], config['finance_id'], model_id)
                    )
                )
                do_update = True
        
        if not do_update:
            logger.info('completed model run has no downstream finance runs')
            return NUP
        
        logger.info('prequeuing %d finance runs after model run completion', len(prequeue_finance_run))

        return prequeue_finance_run
    
    @app.callback(
        Output('res-gen', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_gen(
        model_run_json,
        selected_model
    ):
        """
        Create the generation results for a completed model run.
        """
        logger.info('postprocessing generation')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_model_gen'](
            model_run_json,
            app
        )
    
    @app.callback(
        Output('res-stor', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_stor(
        model_run_json,
        selected_model
    ):
        """
        Create the storage results for a completed model run.
        """
        logger.info('postprocessing storage')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_model_stor'](
            model_run_json,
            app
        )
    
    @app.callback(
        Output('res-cons', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_cons(
        model_run_json,
        selected_model
    ):
        """
        Create the consumption results for a completed model run.
        """
        logger.info('postprocessing consumption')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_model_cons'](
            model_run_json,
            app
        )
    
    @app.callback(
        Output('res-net', 'data'),
        Input('trigger-postprocess-model-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_model_net(
        model_run_json,
        selected_model
    ):
        """
        Create the net energy results for a completed model run.
        """
        logger.info('postprocessing net energy')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_model_net'](
            model_run_json,
            app
        )
    
    @app.callback(
        Output('res-finance-so-benefits', 'data'),
        Input('trigger-postprocess-finance-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_finance_benefits_so(
        finance_run_json,
        selected_model
    ):
        """
        Create the system owner financial benefits results.
        """
        logger.info('postprocessing financial benefits')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_finance_benefits_so'](
            finance_run_json,
            app
        )
    
    @app.callback(
        Output('res-finance-so-costs', 'data'),
        Input('trigger-postprocess-finance-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_finance_costs_so(
        finance_run_json,
        selected_model
    ):
        """
        Create the system owner financial costs results.
        """
        logger.info('postprocessing financial costs')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_finance_costs_so'](
            finance_run_json,
            app
        )
    
    @app.callback(
        Output('res-finance-so-value', 'data'),
        Input('trigger-postprocess-finance-run', 'data'),
        State('selected-model', 'data'),
        prevent_initial_call = True
    )
    def postproc_finance_value_so(
        finance_run_json,
        selected_model
    ):
        """
        Create the system owner financial value results.
        """
        logger.info('postprocessing financial value')
        return callbacks_map.CALLBACKS_MAP[selected_model]['postproc_finance_value_so'](
            finance_run_json,
            app
        )
    
    return app
