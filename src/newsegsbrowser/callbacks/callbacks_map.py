from newsegsbrowser.callbacks import model_configuration_callbacks_generic
from newsegsbrowser.callbacks import model_configuration_callbacks_sprake
from newsegsbrowser.callbacks import postprocess_callbacks_generic
from newsegsbrowser.callbacks import postprocess_callbacks_sprake
from newsegsbrowser.callbacks import results_callbacks_sprake
SPRAKE_CALLBACKS = {
    'sync_config': model_configuration_callbacks_sprake.sync_config,
    'sync_loc_inputs_to_store': model_configuration_callbacks_generic.sync_loc_inputs_to_store,

    'update_dsa_boundsinputs':model_configuration_callbacks_generic.update_dsa_boundsinputs,
    'update_psa_inputs_status':model_configuration_callbacks_generic.update_psa_inputs_status,

    'update_headers_model_config': model_configuration_callbacks_sprake.update_headers_model_config,
    'update_headers_finance_config': model_configuration_callbacks_sprake.update_headers_finance_config,
    'update_headers_dsa_inputs': model_configuration_callbacks_generic.update_headers_dsa_inputs,
    'update_headers_psa_inputs': model_configuration_callbacks_generic.update_headers_psa_inputs,
    'update_feedback_graphs': model_configuration_callbacks_sprake.update_feedback_graphs,
    'dispatcher_action_user': model_configuration_callbacks_sprake.dispatcher_action_user,

    'postproc_model_gen': postprocess_callbacks_sprake.postproc_model_gen,
    'postproc_model_stor': postprocess_callbacks_generic.postproc_model_stor,
    'postproc_model_cons': postprocess_callbacks_sprake.postproc_model_cons,
    'postproc_model_net': postprocess_callbacks_generic.postproc_model_net,
    'postproc_finance_benefits_so': postprocess_callbacks_sprake.postproc_finance_benefits_so,
    'postproc_finance_costs_so': postprocess_callbacks_sprake.postproc_finance_costs_so,
    'postproc_finance_value_so': postprocess_callbacks_sprake.postproc_finance_value_so,
    'postproc_dsa': postprocess_callbacks_generic.postproc_dsa,

    'update_model_result_headers': results_callbacks_sprake.update_model_result_headers,
    'update_finance_result_headers': results_callbacks_sprake.update_finance_result_headers,

    'sync_gen_results_table_to_store': results_callbacks_sprake.sync_gen_results_table_to_store,
    'sync_stor_results_table_to_store': results_callbacks_sprake.sync_stor_results_table_to_store,
    'sync_cons_results_table_to_store': results_callbacks_sprake.sync_cons_results_table_to_store,
    'sync_net_results_table_to_store': results_callbacks_sprake.sync_net_results_table_to_store,
    'sync_fnc_so_table_to_store': results_callbacks_sprake.sync_fnc_so_table_to_store,

    'sync_dsa_results_table_to_store': results_callbacks_sprake.sync_dsa_results_table_to_store,
    'sync_dsa_tornado_to_store': results_callbacks_sprake.sync_dsa_tornado_to_store,

}

CALLBACKS_MAP = {
    'sprake': SPRAKE_CALLBACKS
}
