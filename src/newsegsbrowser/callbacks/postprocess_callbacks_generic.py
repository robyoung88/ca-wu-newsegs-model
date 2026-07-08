import json
import logging

from dash import Dash, no_update

from newsegsbrowser.postprocess import post_dsa_results, post_psa_results, postprocess_utils as pp_utils
from newsegsbrowser.postprocess import post_sprake_storage_results
from newsegsbrowser.postprocess import post_sprake_net_results

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

def postproc_dsa(
    dsa_triggers,
    app: Dash
):
    NUP = no_update
    
    for trigger in dsa_triggers:
        if isinstance(trigger, list):
            for trig_str in trigger:
                trig = json.loads(trig_str)

                mm_id = trig.get('metamodel_id')

                mm = app.metamodels.get(mm_id)
                table_id = pp_utils.get_dsa_result_id(
                    pp_utils.RESULT_CACHE_PREFIXES['dsa_table'],
                    mm_id
                )
                label_id = pp_utils.get_dsa_result_id(
                    pp_utils.RESULT_CACHE_PREFIXES['dsa_label'],
                    mm_id
                )
                logger.info('Getting result table %s', table_id)
                logger.info('Getting result labels %s', label_id)

                prev_result = app.results.get(table_id, None)
                prev_labels = app.results.get(label_id, None)
                if (
                    not prev_result is None 
                    and getattr(prev_result, '_run_time') == mm.last_dsa_run
                    and not prev_labels is None
                    and getattr(prev_labels, '_run_time') == mm.last_dsa_run
                ):
                    return NUP
                
                logger.info('Cache miss - making dsa table %s', table_id)

                data_id = pp_utils.get_dsa_result_id(
                    pp_utils.RESULT_CACHE_PREFIXES['dsa_results'],
                    mm_id
                )
                dsa_results = app.results.get(data_id, None)
                if dsa_results is None:
                    raise ValueError(f'DSA results {data_id} not found')

                res_table, label_table = post_dsa_results.dsa_results_to_tables(dsa_results)
                setattr(res_table, '_run_time', mm.last_dsa_run)
                setattr(label_table, '_run_time', mm.last_dsa_run)
                app.results[table_id] = res_table
                app.results[label_id] = label_table
                
                return dsa_triggers
        else:
            # A universal trigger has been applied.
            return NUP

def postproc_psa(
    psa_triggers,
    app: Dash
):
    NUP = no_update

    for trigger in psa_triggers:
        if isinstance(trigger, list):
            for trig_str in trigger:
                trig = json.loads(trig_str)

                mm_id = trig.get('metamodel_id')
                table_id = pp_utils.get_psa_result_id(
                    pp_utils.RESULT_CACHE_PREFIXES['psa_table'],
                    mm_id
                )
                pos_npv_id = pp_utils.get_psa_result_id(
                    pp_utils.RESULT_CACHE_PREFIXES['psa_prob_positive_npv'],
                    mm_id
                )

                logger.info('Getting result table %s', table_id)

                prev_result = app.results.get(table_id, None)
                prev_npv = app.results.get(pos_npv_id, None)
                
                mm = app.metamodels.get(mm_id)

                if (
                    not prev_result is None 
                    and getattr(prev_result, '_run_time') == mm.last_psa_run
                    and not prev_npv is None
                    and getattr(prev_npv, '_run_time') == mm.last_psa_run
                ):
                    return NUP

                logger.info('Cache miss - making psa table %s', table_id)

                data_id = pp_utils.get_psa_result_id(
                    pp_utils.RESULT_CACHE_PREFIXES['psa_results'],
                    mm_id
                )
                psa_results = app.results.get(data_id, None)
                if psa_results is None:
                    raise ValueError(f'PSA results {data_id} not found')

                res_table, prob_pos_npv = post_psa_results.psa_results_to_tables(psa_results)
                setattr(res_table, '_run_time', mm.last_psa_run)
                setattr(prob_pos_npv, '_run_time', mm.last_psa_run)
                app.results[table_id] = res_table
                app.results[pos_npv_id] = prob_pos_npv

                return psa_triggers
        else:
            # A universal trigger has been applied.
            return NUP
