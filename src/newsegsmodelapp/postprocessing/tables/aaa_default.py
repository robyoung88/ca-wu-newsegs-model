from typing import Callable, cast

from newsegsmodelapp.newsegsbrowser.postprocess.tables import result_tables_sprake
from newsegsmodelapp.postprocessing.tables.get_result_list import get_result_list
from newsegsmodelapp.registers import RunRequest, register_table_draw
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface


MODEL_TYPE = 'default'
TABLE_SECTION = 'grid'

@register_table_draw((TABLE_SECTION, MODEL_TYPE))
def _make_grid_tables_sprake(
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False,
) -> str:
    # Do nothing - grid currently has no postproc
    return 'ok'


TABLE_SECTION = 'generation'
@register_table_draw((TABLE_SECTION, MODEL_TYPE))
def _make_generation_tables_sprake(
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False
) -> str:
    result_type = 'postproc_model_generation'
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    res = get_result_list(result_type, proj, result_provider, True)

    wind_results = result_tables_sprake.create_wind_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_generation_wind',
        proj.table_config,
        wind_results
    )

    pv_results = result_tables_sprake.create_pv_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_generation_pv',
        proj.table_config,
        pv_results
    )

    combined_generation_results = result_tables_sprake.create_combined_generation_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_generation_combined',
        proj.table_config,
        combined_generation_results
    )

    return 'ok'

TABLE_SECTION = 'consumption'
@register_table_draw((TABLE_SECTION, MODEL_TYPE))
def _make_consumption_tables_sprake(
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False
) -> str:
    result_type = 'postproc_model_consumption'
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    res = get_result_list(result_type, proj, result_provider, True)

    consumption_results = result_tables_sprake.create_cons_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_consumption',
        proj.table_config,
        consumption_results
    )

    seasonal_consumption_results = result_tables_sprake.create_seasonal_cons_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_consumption_seasonal',
        proj.table_config,
        seasonal_consumption_results
    )

    return 'ok'

TABLE_SECTION = 'storage'
@register_table_draw((TABLE_SECTION, MODEL_TYPE))
def _make_storage_tables_sprake(
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False
) -> str:
    result_type = 'postproc_model_storage'
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    res = get_result_list(result_type, proj, result_provider, True)

    storage_results = result_tables_sprake.create_stor_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_storage',
        proj.table_config,
        storage_results
    )

    return 'ok'

TABLE_SECTION = 'net'
@register_table_draw((TABLE_SECTION, MODEL_TYPE))
def _make_net_tables_sprake(
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False
) -> str:
    result_type = 'postproc_model_net'
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    res = get_result_list(result_type, proj, result_provider, True)

    net_results = result_tables_sprake.create_net_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_net_energy',
        proj.table_config,
        net_results
    )

    seasonal_net_results = result_tables_sprake.create_seasonal_net_results(res, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_model_net_energy_seasonal',
        proj.table_config,
        seasonal_net_results
    )

    return 'ok'

TABLE_SECTION = 'finance'
@register_table_draw((TABLE_SECTION, MODEL_TYPE))
def _make_finance_tables_sprake(
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False
) -> str:
    result_type = 'postproc_model_net'
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    benefits = get_result_list(
        'postproc_finance_benefits', proj,
        result_provider, True
    )

    costs = get_result_list(
        'postproc_finance_costs', proj,
        result_provider, True
    )

    value = get_result_list(
        'postproc_finance_value', proj,
        result_provider, True
    )

    benefits_results = result_tables_sprake.create_so_benefits_results(benefits, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_finance_so_benefits',
        proj.table_config,
        benefits_results
    )

    costs_results = result_tables_sprake.create_so_costs_results(costs, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_finance_so_costs',
        proj.table_config,
        costs_results
    )
    
    value_results = result_tables_sprake.create_so_value_results(value, not(ann_hori_toggle))
    result_provider.upsert_result(
        'table_finance_so_value',
        proj.table_config,
        value_results
    )

    return 'ok'
