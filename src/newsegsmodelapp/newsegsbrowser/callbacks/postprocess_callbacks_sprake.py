from dash import Dash

from newsegsmodelapp.newsegsbrowser.app_cache_manager import NewsegsBrowserCacheManager
from newsegsmodelapp.newsegsbrowser.postprocess import postprocess_utils as pp_utils
from newsegsmodelapp.newsegsbrowser.postprocess import post_sprake_gen_results
from newsegsmodelapp.newsegsbrowser.postprocess import post_sprake_consumption_results
from newsegsmodelapp.newsegsbrowser.postprocess import post_sprake_finance_benefits_results
from newsegsmodelapp.newsegsbrowser.postprocess import post_sprake_finance_costs_results
from newsegsmodelapp.newsegsbrowser.postprocess import post_sprake_finance_value_results

def postproc_model_gen(
    model_run_json: list | str,
    acm: NewsegsBrowserCacheManager
):
    return pp_utils.generic_model_postprocess(
        model_run_json,
        post_sprake_gen_results.gen_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['generation'],
        acm
    )

def postproc_model_cons(
    model_run_json: list | str,
    acm: NewsegsBrowserCacheManager
):
    return pp_utils.generic_model_postprocess(
        model_run_json,
        post_sprake_consumption_results.consumption_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['consumption'],
        acm
    )

def postproc_finance_benefits_so(
    finance_run_json: list | str,
    acm: NewsegsBrowserCacheManager
):
    return pp_utils.generic_finance_postprocess(
        finance_run_json,
        post_sprake_finance_benefits_results.finance_benefits_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['finance_benefits_so'],
        acm
    )

def postproc_finance_costs_so(
    finance_run_json: list | str,
    acm: NewsegsBrowserCacheManager
):
    return pp_utils.generic_finance_postprocess(
        finance_run_json,
        post_sprake_finance_costs_results.finance_costs_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['finance_costs_so'],
        acm
    )

def postproc_finance_value_so(
    finance_run_json: list | str,
    acm: NewsegsBrowserCacheManager
):
    return pp_utils.generic_finance_postprocess(
        finance_run_json,
        post_sprake_finance_value_results.finance_value_results_to_interface_sprake,
        pp_utils.RESULT_CACHE_PREFIXES['finance_value_so'],
        acm
    )
