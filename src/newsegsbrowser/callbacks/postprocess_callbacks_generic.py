from dash import Dash

from src.newsegsbrowser.postprocess import postprocess_utils as pp_utils
from src.newsegsbrowser.postprocess import post_sprake_storage_results
from src.newsegsbrowser.postprocess import post_sprake_net_results

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
