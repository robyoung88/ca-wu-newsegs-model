import json
import logging
from typing import Any, get_args

from dash import Dash, no_update, ctx

from newsegsbrowser.postprocess import post_dsa_results, post_psa_results, postprocess_utils as pp_utils
from newsegsbrowser.postprocess import post_sprake_storage_results
from newsegsbrowser.postprocess import post_sprake_net_results
from newsegssensitivity import dsa, psa

logger = logging.getLogger(__name__)

def postproc_model_stor(
    model_run_json: list | str,
    app: Dash
):
    return pp_utils.generic_model_postprocess(
        model_run_json,
        post_sprake_storage_results.stor_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['storage'],
        app
    )

def postproc_model_net(
    model_run_json: list | str,
    app: Dash
):
    return pp_utils.generic_model_postprocess(
        model_run_json,
        post_sprake_net_results.net_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['net_energy'],
        app
    )

def _postprocess_dsa_single_mm(
    metamodel_id: str,
    app: Dash
) -> bool:
    """
    Checks if a postprocessed data set exists for the dsa for a metamodel.

    If not, creates one.
    Returns False if no change to results, True if results updated, and raises
    a ValueError if there are no dsa results for the metamodel.
    """
    table_id = pp_utils.get_dsa_result_id(
        pp_utils.RESULT_CACHE_PREFIXES['dsa_table'],
        metamodel_id
    )
    label_id = pp_utils.get_dsa_result_id(
        pp_utils.RESULT_CACHE_PREFIXES['dsa_label'],
        metamodel_id
    )

    logger.info('Getting result table %s and %s', table_id, label_id)

    prev_result = app.results.get(table_id)
    prev_labels = app.results.get(label_id)
    mm = app.metamodels.get(metamodel_id)
    if (
        not prev_result is None 
        and getattr(prev_result, '_run_time') == mm.last_dsa_run
        and not prev_labels is None
        and getattr(prev_labels, '_run_time') == mm.last_dsa_run
    ):
        return False
    logger.info('Cache miss - making dsa tables %s and %s', table_id, label_id)

    dsa_results = pp_utils.get_dsa_raw_data(metamodel_id, app)
    if dsa_results is None:
        raise ValueError(f'DSA results for {metamodel_id} not found')
    
    res_table, label_table = post_dsa_results.dsa_results_to_tables(dsa_results)
    setattr(res_table, '_run_time', mm.last_dsa_run)
    setattr(label_table, '_run_time', mm.last_dsa_run)
    app.results[table_id] = res_table
    app.results[label_id] = label_table
    
    return True

def postproc_dsa(
    dsa_triggers,
    selected_configuration,
    configurations,
    app: Dash
):
    NUP = no_update
    logger.info('postproc_dsa triggered by %s', dsa_triggers)
    
    processed_list = []
    trigger_ui_refresh = False

    for trigger in dsa_triggers:
        if isinstance(trigger, list):
            for trig_str in trigger:
                trig = json.loads(trig_str)

                mm_id = trig.get('metamodel_id')
                
                if mm_id in processed_list:
                    continue
                processed_list.append(mm_id)
                try:
                    results_updated = _postprocess_dsa_single_mm(mm_id, app)
                except ValueError as e:
                    logger.error(e)
                    continue

                if results_updated:
                    trigger_ui_refresh = True
        else:
            # A universal trigger has been applied.
             # A universal trigger has been applied.
            for conf_j in configurations:
                mm_id = json.loads(conf_j)['metamodel_id']
                if mm_id in processed_list:
                    continue
                processed_list.append(mm_id)
                try:
                    results_updated = _postprocess_dsa_single_mm(mm_id, app)
                except ValueError as e:
                    logger.error(e)
                    continue
                
                if results_updated:
                    trigger_ui_refresh = True
            break
    
    if trigger_ui_refresh:
        return dsa_triggers[0]
    else:
        # Trigger it anyway
        return dsa_triggers[0]
        #return NUP
    
def _set_dsa_feedback_status(
    status: str,
    message: str,
    rval: list[Any],
    resize_handle_ids,
    result_tooltip_ids
):
    """
    Modifies rval in place to set handle class and tooltip message
    """
    match status:
        case 'ok':
            handle_class = 'resize-handle resize-handle-ok'
        case 'warning':
            handle_class = 'resize-handle resize-handle-warning'
        case 'error':
            handle_class = 'resize-handle resize-handle-error'
        case _:
            handle_class = 'resize-handle'
    for idx, id in enumerate(resize_handle_ids):
        if id.get('page') == 'dsa':
            rval[0][idx] = handle_class
    for idx, id in enumerate(result_tooltip_ids):
        if id.get('page') == 'dsa':
            rval[1][idx] = message
    return

def feedback_dsa_status(
    dsa_triggers,
    resize_handle_ids,
    result_tooltip_ids,
    selected_configuration,
    configurations,
    app,
):
    rval = [
        [no_update] * len(resize_handle_ids),
        [no_update] * len(result_tooltip_ids)
    ]
    selected_configuration = json.loads(selected_configuration)
    mm = app.metamodels.get(selected_configuration.get('metamodel_id'))

    try:
        dsa_results = pp_utils.get_dsa_raw_data(mm, app)
    except Exception as e:
        _set_dsa_feedback_status(
            'error',
            'Unable to verify DSA results - no DSA data available',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)

    if dsa_results is None:
        _set_dsa_feedback_status(
            'error',
            'Unable to verify DSA results - no DSA data available',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)
    
    try:
        det_res = dsa.make_dsa_result('deterministic', 'central', '-', mm.model, mm.finance, get_args(dsa.DSA_FLOAT_STATISTIC))
    except:
        _set_dsa_feedback_status(
            'warning',
            'Unable to verify DSA results - model has not been run deterministically',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)

    det_dsa = dsa_results.loc[[('deterministic', 'central')], :]
    if len(det_dsa) != 1:
        _set_dsa_feedback_status(
            'warning',
            'Unable to verify DSA results - no deterministic DSA data available',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)
    
    for stat in get_args(dsa.DSA_FLOAT_STATISTIC):
        if stat in det_dsa.columns:
            err = abs(det_dsa.loc[:, stat].iloc[0] - det_res[stat])
            if abs(det_res[stat]) > 10:
                err = err / abs(det_res[stat])
            if not err < 1e-10:
                logger.info('stat %s does not match: %s (DSA) vs %s (DET)', stat, det_dsa.loc[:, stat].iloc[0], det_res[stat])
                _set_dsa_feedback_status(
                    'error',
                    'DSA verification failed - deterministic results do not correspond to current model',
                    rval, resize_handle_ids, result_tooltip_ids
                )
                return tuple(rval)
            
    # TODO: Check that variables are as per current settings
    
    _set_dsa_feedback_status(
        'ok',
        'DSA verification OK',
        rval, resize_handle_ids, result_tooltip_ids
    )
    return tuple(rval)

def _postprocess_psa_single_mm(
    metamodel_id: str,
    app: Dash
) -> bool:
    """
    Checks if a postprocessed data set exists for the psa for a metamodel.

    If not, creates one.
    Returns False if no change to results, True if results updated, and raises
    a ValueError if there are no psa results for the metamodel.
    """
    table_id = pp_utils.get_psa_result_id(
        pp_utils.RESULT_CACHE_PREFIXES['psa_table'],
        metamodel_id
    )
    pos_npv_id = pp_utils.get_psa_result_id(
        pp_utils.RESULT_CACHE_PREFIXES['psa_prob_positive_npv'],
        metamodel_id
    )

    logger.info('Getting result table %s and %s', table_id, pos_npv_id)

    prev_result = app.results.get(table_id, None)
    prev_npv = app.results.get(pos_npv_id, None)
    mm = app.metamodels.get(metamodel_id)
    if (
        not prev_result is None 
        and getattr(prev_result, '_run_time') == mm.last_psa_run
        and not prev_npv is None
        and getattr(prev_npv, '_run_time') == mm.last_psa_run
    ):
        return False
    logger.info('Cache miss - making psa tables %s and %s', table_id, pos_npv_id)
    
    psa_results = pp_utils.get_psa_raw_data(metamodel_id, app)
    if psa_results is None:
        raise ValueError(f'PSA results for {metamodel_id} not found')
    
    res_table, prob_pos_npv = post_psa_results.psa_results_to_tables(psa_results)
    setattr(res_table, '_run_time', mm.last_psa_run)
    setattr(prob_pos_npv, '_run_time', mm.last_psa_run)
    app.results[table_id] = res_table
    app.results[pos_npv_id] = prob_pos_npv
    
    return True

def postproc_psa(
    psa_triggers,
    selected_configuration,
    configurations,
    app: Dash
):
    
    NUP = no_update
    logger.info('postproc_psa triggered by %s', psa_triggers)

    processed_list = []
    trigger_ui_refresh = False

    for trigger in psa_triggers:
        if isinstance(trigger, list):
            for trig_str in trigger:
                trig = json.loads(trig_str)

                mm_id = trig.get('metamodel_id')
                if mm_id in processed_list:
                    continue
                processed_list.append(mm_id)
                try:
                    results_updated = _postprocess_psa_single_mm(mm_id, app)
                except ValueError as e:
                    logger.error(e)
                    continue
                
                if results_updated:
                    trigger_ui_refresh = True
                
        else:
            # A universal trigger has been applied.
            for conf_j in configurations:
                mm_id = json.loads(conf_j)['metamodel_id']
                if mm_id in processed_list:
                    continue
                processed_list.append(mm_id)
                try:
                    results_updated = _postprocess_psa_single_mm(mm_id, app)
                except ValueError as e:
                    logger.error(e)
                    continue
                
                if results_updated:
                    trigger_ui_refresh = True
            break
    
    if trigger_ui_refresh:
        return psa_triggers[0]
    else:
        # Trigger it anyway
        return psa_triggers[0]
        #return NUP

def _set_psa_feedback_status(
    status: str,
    message: str,
    rval: list[Any],
    resize_handle_ids,
    result_tooltip_ids
):
    """
    Modifies rval in place to set handle class and tooltip message
    """
    match status:
        case 'ok':
            handle_class = 'resize-handle resize-handle-ok'
        case 'warning':
            handle_class = 'resize-handle resize-handle-warning'
        case 'error':
            handle_class = 'resize-handle resize-handle-error'
        case _:
            handle_class = 'resize-handle'
    for idx, id in enumerate(resize_handle_ids):
        if id.get('page') == 'psa':
            rval[0][idx] = handle_class
    for idx, id in enumerate(result_tooltip_ids):
        if id.get('page') == 'psa':
            rval[1][idx] = message
    return

def feedback_psa_status(
    psa_triggers,
    resize_handle_ids,
    result_tooltip_ids,
    selected_configuration,
    configurations,
    app,
):
    rval = [
        [no_update] * len(resize_handle_ids),
        [no_update] * len(result_tooltip_ids)
    ]

    selected_configuration = json.loads(selected_configuration)
    mm = app.metamodels.get(selected_configuration.get('metamodel_id'))
    try:
        det_res = psa.make_psa_result(mm, mm.model, mm.finance, statistics = get_args(psa.PSA_FLOAT_STATISTIC), return_draws = False)
    except:
        _set_psa_feedback_status(
            'warning',
            'Unable to verify PSA results - model has not been run deterministically',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)
    try:
        psa_results = pp_utils.get_psa_raw_data(mm, app)
    except:
        _set_psa_feedback_status(
            'error',
            'Unable to verify PSA results - no PSA data available',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)
    if psa_results is None:
        _set_psa_feedback_status(
            'error',
            'Unable to verify PSA results - no PSA data available',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)
    
    det_psa = psa_results.query('deterministic == True')
    if len(det_psa) != 1:
        _set_psa_feedback_status(
            'warning',
            'Unable to verify PSA results - no deterministic PSA data available',
            rval, resize_handle_ids, result_tooltip_ids
        )
        return tuple(rval)
    
    for stat in get_args(psa.PSA_FLOAT_STATISTIC):
        if stat in det_psa.columns:
            err = abs(det_psa.loc[:, stat].iloc[0] - det_res[stat])
            if abs(det_res[stat]) > 10:
                err = err / abs(det_res[stat])
            if not err < 1e-10:
                logger.info('stat %s does not match: %s (PSA) vs %s (DET)', stat, det_psa.loc[:, stat].iloc[0], det_res[stat])
                _set_psa_feedback_status(
                    'error',
                    'PSA verification failed - deterministic results do not correspond to current model',
                    rval, resize_handle_ids, result_tooltip_ids
                )
                return tuple(rval)
            
    # TODO: Check that variables are as per current settings
    
    _set_psa_feedback_status(
        'ok',
        'PSA verification OK',
        rval, resize_handle_ids, result_tooltip_ids
    )
    return tuple(rval)
