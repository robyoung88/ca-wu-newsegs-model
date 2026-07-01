import copy
import json
import logging

from dash import no_update

logger = logging.getLogger(__name__)

RESULT_CACHE_PREFIXES = {
    'generation': 'res_gen_',
    'storage': 'res_stor_',
    'consumption': 'res_cons_',
    'net_energy': 'res_net_',
    'finance_benefits_so': 'res_fnc_ben_so_',
    'finance_costs_so': 'res_fnc_cost_so_',
    'finance_value_so': 'res_fnc_val_so_',
    'dsa_results': 'res_dsa_',
    'dsa_table': 'dsa_table_',
    'dsa_label': 'dsa_label_',
}

def get_model_result_id(prefix, model_id):
    return prefix + str(model_id)

def get_finance_result_id(prefix, finance_id, model_id):
    return prefix + "fnc_" + str(finance_id) + "_mdl_" + str(model_id)

def get_dsa_result_id(prefix: str, metamodel_id: str) -> str:
    return prefix + metamodel_id

def get_model_result_list(prefix, configs, app):
    return [app.results.get(get_model_result_id(prefix, json.loads(x)['model_id'])) for x in configs]

def get_finance_result_list(prefix, configs, app):
    return [app.results.get(get_finance_result_id(prefix, json.loads(x)['finance_id'], json.loads(x)['model_id'])) for x in configs]

def generic_model_postprocess(
    model_run,
    postprocess_function,
    result_id_prefix,
    app
):
    """
    Run a postprocess function on a model and store in the results cache.
    """
    NUP = no_update
    if model_run is None:
        return NUP
    
    model_run_0 = copy.copy(model_run)

    if isinstance(model_run, str):
        model_run = json.loads(model_run)
    
    if isinstance(model_run, list):
        return [
            generic_model_postprocess(
                x, 
                postprocess_function, 
                result_id_prefix, 
                app
            ) for x in model_run
        ]

    model_id = model_run['model_id']
    mdl = app.models.get(model_id)
    if mdl is None:
        return NUP
    
    # Avoid recalculation if nothing has actually run
    run_hash = hash(mdl)
    result_id = get_model_result_id(result_id_prefix, model_id)
    logger.info('Getting result %s', result_id)
    prev_result = app.results.get(result_id, None)
    if not prev_result is None and prev_result['run_hash'] == run_hash:
        return NUP
    
    logger.info('Cache miss - making result %s', result_id)
    
    postproc_results = postprocess_function(mdl)
    postproc_results['run_hash'] = run_hash
    app.results[result_id] = postproc_results

    return model_run_0

def generic_finance_postprocess(
    finance_run,
    postprocess_function,
    result_id_prefix,
    app
):
    NUP = no_update
    if finance_run is None:
        return NUP
    
    finance_run_0 = copy.copy(finance_run)

    if isinstance(finance_run, str):
        finance_run = json.loads(finance_run)
    
    if isinstance(finance_run, list):
        return [generic_finance_postprocess(x, postprocess_function, result_id_prefix, app) for x in finance_run]
    
    model_id = finance_run['model_id']
    finance_id = finance_run['finance_id']
    mdl = app.models.get(model_id)
    fnc = app.finances.get(finance_id)

    if mdl is None or fnc is None:
        logger.warning('model (%s) or finance (%s) not found for postprocess %s', type(mdl), type(fnc), finance_run)
        return NUP

    run_hash = hash(mdl) + hash(fnc)
    result_id = get_finance_result_id(result_id_prefix, finance_id, model_id)
    logger.info('Getting result %s', result_id)
    prev_result = app.results.get(result_id, None)
    if not prev_result is None and prev_result['run_hash'] == run_hash:
        return NUP
    
    logger.info('Cache miss - making result %s', result_id)

    try:
        postproc_results = postprocess_function(mdl, fnc)
    except KeyError:
        # Model has not been run yet
        logger.warning('Keyerror in finance postprocess, likely due to model results not available: %s', finance_run)
        return NUP

    postproc_results['run_hash'] = run_hash
    app.results[result_id] = postproc_results

    return finance_run_0
