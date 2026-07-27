import copy
import json
import logging
import time
from typing import Any, cast

from dash import no_update
import pandas as pd
import scipy.optimize as sci_opt

from newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

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
    'psa_results': 'res_psa_',
    'psa_table': 'psa_table_',
    'psa_prob_positive_npv': 'psa_prob_positive_npv_',
    'optim_results': 'res_optim_',
}

def get_model_result_id(prefix, model_id):
    return prefix + str(model_id)

def get_finance_result_id(prefix, finance_id, model_id):
    return prefix + "fnc_" + str(finance_id) + "_mdl_" + str(model_id)

def get_dsa_result_id(prefix: str, metamodel_id: str) -> str:
    return prefix + metamodel_id

def get_psa_result_id(prefix: str, metamodel_id: str) -> str:
    return prefix + metamodel_id

def get_optim_result_id(prefix: str, metamodel_id: str) -> str:
    return prefix + metamodel_id

def get_model_result_list(prefix, configs, app):
    return [app.results.get(get_model_result_id(prefix, json.loads(x)['model_id'])) for x in configs]

def get_finance_result_list(prefix, configs, app):
    return [app.results.get(get_finance_result_id(prefix, json.loads(x)['finance_id'], json.loads(x)['model_id'])) for x in configs]

def assign_dsa_results(
    mm: NewsegsMetaModel,
    results: pd.DataFrame,
    run_time: float | None = None,
) -> str:
    """
    Add or assign the appropriate attributes to match up dsa results to metamodels

    Returns the result_id for caching
    """
    if run_time is None:
        run_time = time.time()
    result_id = get_dsa_result_id(RESULT_CACHE_PREFIXES['dsa_results'], mm.id)

    mm.last_dsa_run = run_time
    setattr(results, '_run_time', run_time)
    return result_id

def assign_psa_results(
    mm: NewsegsMetaModel,
    results: pd.DataFrame,
    run_time: float | None = None,
) -> str:
    """
    Add or assign the appropriate attributes to match up psa results to metamodels

    Returns the result_id for caching
    """
    if run_time is None:
        run_time = time.time()
    result_id = get_psa_result_id(RESULT_CACHE_PREFIXES['psa_results'], mm.id)

    mm.last_psa_run = run_time
    setattr(results, '_run_time', run_time)
    return result_id

def assign_optim_results(
    mm: NewsegsMetaModel,
    results: sci_opt._optimize.OptimizeResult,
    run_time: float | None = None,
):
    """
    Set the metamodel.last_optim_run (time) and ._run_time attribute on the results object.

    Return the result id.
    """
    if run_time is None:
        run_time = time.time()
    result_id = get_optim_result_id(RESULT_CACHE_PREFIXES['optim_results'], mm.id)

    mm.last_optim_run = run_time
    setattr(results, '_run_time', run_time)
    return result_id

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

def get_det_raw_data(
    metamodel: str | dict[str, str] | NewsegsMetaModel,
    app
) -> pd.DataFrame | None:
    if isinstance(metamodel, str):
        metamodel = cast(NewsegsMetaModel, app.metamodels.get(metamodel))
    elif isinstance(metamodel, dict):
        metamodel = cast(NewsegsMetaModel, app.metamodels.get(metamodel.get('metamodel_id')))

    if metamodel is None:
        raise ValueError(f'metamodel not found')
    
    try:
        gen_res = metamodel.model.get_generation_result()
        grid_res = metamodel.model.get_grid_result()
        cs_res = metamodel.model.get_consumption_storage_result()
    except AttributeError:
        return None
    
    all_frames = [
        gen_res.meters_to_pandas(),
        gen_res.dsm_to_pandas(),
        grid_res.meters_to_pandas(),
        grid_res.dsm_to_pandas(),
        cs_res.meters_to_pandas(),
        cs_res.dsm_to_pandas()
    ]

    all_frames = [x for x in all_frames if not x.empty]
    if not len(all_frames):
        return None
    elif len(all_frames) == 1:
        return all_frames[0]
    else:
        odf = all_frames[0]
        for j in range(1, len(all_frames)):
            odf = odf.join(all_frames[j])

    return odf

def get_dsa_raw_data(
    metamodel: str | dict[str, str] | NewsegsMetaModel,
    app
) -> pd.DataFrame | None:
    if isinstance(metamodel, NewsegsMetaModel):
        mm_id = metamodel.id
    elif isinstance(metamodel, dict):
        mm_id = metamodel['metamodel_id']
    else:
        mm_id = metamodel
    df_id = get_dsa_result_id(
        RESULT_CACHE_PREFIXES['dsa_results'],
        mm_id
    )
    logger.info('finding result %s', df_id)
    return app.results.get(df_id)    

def get_psa_raw_data(
        metamodel: str | dict[str, str] | NewsegsMetaModel,
        app
    ) -> pd.DataFrame | None:
    if isinstance(metamodel, NewsegsMetaModel):
        mm_id = metamodel.id
    elif isinstance(metamodel, dict):
        mm_id = metamodel['metamodel_id']
    else:
        mm_id = metamodel
    df_id = get_psa_result_id(
        RESULT_CACHE_PREFIXES['psa_results'],
        mm_id
    )
    logger.info('finding result %s', df_id)
    return app.results.get(df_id)
