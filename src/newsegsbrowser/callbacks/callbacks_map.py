from newsegsbrowser.callbacks import model_configuration_callbacks_generic
from newsegsbrowser.callbacks import model_configuration_callbacks_sprake
from newsegsbrowser.callbacks import postprocess_callbacks_generic
from newsegsbrowser.callbacks import postprocess_callbacks_sprake
from newsegsbrowser.callbacks import results_callbacks_sprake
SPRAKE_CALLBACKS = {
    'sync_config': model_configuration_callbacks_sprake.sync_config,
    'sync_loc_inputs_to_store': model_configuration_callbacks_generic.sync_loc_inputs_to_store,
    'sync_gen_inputs_to_store': model_configuration_callbacks_generic.sync_gen_inputs_to_store,
    'sync_stor_inputs_to_store': model_configuration_callbacks_generic.sync_stor_inputs_to_store,
    'sync_bc_inputs_to_store': model_configuration_callbacks_generic.sync_bc_inputs_to_store,
    'sync_dc_inputs_to_store': model_configuration_callbacks_sprake.sync_dc_inputs_to_store,
    'sync_mc_inputs_to_store': model_configuration_callbacks_sprake.sync_mc_inputs_to_store,
    'sync_unit_cost_inputs_to_store': model_configuration_callbacks_sprake.sync_unit_cost_inputs_to_store,
    'sync_fnc_inputs_to_store': model_configuration_callbacks_generic.sync_fnc_inputs_to_store,

    'update_headers_model_config': model_configuration_callbacks_sprake.update_headers_model_config,
    'update_headers_finance_config': model_configuration_callbacks_sprake.update_headers_finance_config,
    'update_feedback_graphs': model_configuration_callbacks_sprake.update_feedback_graphs,
    'dispatcher_action_user': model_configuration_callbacks_sprake.dispatcher_action_user,

    'postproc_model_gen': postprocess_callbacks_sprake.postproc_model_gen,
    'postproc_model_stor': postprocess_callbacks_generic.postproc_model_stor,
    'postproc_model_cons': postprocess_callbacks_sprake.postproc_model_cons,
    'postproc_model_net': postprocess_callbacks_generic.postproc_model_net,
    'postproc_finance_benefits_so': postprocess_callbacks_sprake.postproc_finance_benefits_so,
    'postproc_finance_costs_so': postprocess_callbacks_sprake.postproc_finance_costs_so,
    'postproc_finance_value_so': postprocess_callbacks_sprake.postproc_finance_value_so,

    'update_generation_results_header': results_callbacks_sprake.update_generation_results_header,
    'update_storage_results_header': results_callbacks_sprake.update_storage_results_header,
    'update_consumption_results_header': results_callbacks_sprake.update_consumption_results_header,
    'update_net_results_header': results_callbacks_sprake.update_net_results_header,
    'update_finance_results_header': results_callbacks_sprake.update_finance_results_header,

    'sync_gen_results_table_to_store': results_callbacks_sprake.sync_gen_results_table_to_store,
    'sync_stor_results_table_to_store': results_callbacks_sprake.sync_stor_results_table_to_store,
    'sync_cons_results_table_to_store': results_callbacks_sprake.sync_cons_results_table_to_store,
    'sync_net_results_table_to_store': results_callbacks_sprake.sync_net_results_table_to_store,
    'sync_fnc_so_table_to_store': results_callbacks_sprake.sync_fnc_so_table_to_store,


}

CALLBACKS_MAP = {
    'sprake': SPRAKE_CALLBACKS
}
