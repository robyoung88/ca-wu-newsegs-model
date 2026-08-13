from newsegsmodelapp.newsegsbrowser.postprocess.tables import result_tables_sprake

SPRAKE_RESULT_TABLES = {
    'wind': result_tables_sprake.create_wind_results,
    'pv': result_tables_sprake.create_pv_results,
    'combined_generation': result_tables_sprake.create_combined_generation_results,
    'storage': result_tables_sprake.create_stor_results,
    'consumption': result_tables_sprake.create_cons_results,
    'seasonal_consumption': result_tables_sprake.create_seasonal_cons_results,
    'net_energy': result_tables_sprake.create_net_results,
    'seasonal_net_energy': result_tables_sprake.create_seasonal_net_results,
    'so_benefits': result_tables_sprake.create_so_benefits_results,
    'so_costs': result_tables_sprake.create_so_costs_results,
    'so_value': result_tables_sprake.create_so_value_results,
}
