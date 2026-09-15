from dataclasses import asdict
import json
from typing import Callable, cast

import dash_ag_grid as dag

from newsegsmodelapp.newsegsbrowser.postprocess.tables import result_tables_sprake
from newsegsmodelapp.newsegsbrowser.stats import tornado_plot
from newsegsmodelapp.postprocessing.tables.get_result_list import get_result_list
from newsegsmodelapp.registers import RunRequest, TableDrawRequest, register_table_draw, register_table_draw_request, register_table_getter
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import common as sensitivity


def _table_draw_request_factory(postproc_request_type: str):
    def make_request(request: RunRequest):
        rdict = asdict(request)
        request_type = rdict.pop('request_type', '')
        _ = rdict.pop('request_class', '')
        rdict['request_type'] = postproc_request_type
        rdict['trigger_request_type'] = request_type
        return TableDrawRequest(**rdict)    
    return make_request

MODEL_TYPE = 'default'
TABLE_SECTION = 'table_grid'
_request_table_draw_grid = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_grid'])
def _make_grid_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    ann_hori_toggle: bool = False,
) -> str:
    # Do nothing - grid currently has no postproc
    return 'ok'


TABLE_SECTION = 'table_generation'
_request_table_draw_generation = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_generation'])
def _make_generation_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    result_type = 'postproc_generation'
    proj = project_provider.get_project(request.project_id)

    res, stale = get_result_list(result_type, proj, result_provider, True)

    wind_results = [
        result_tables_sprake.create_wind_results(res, True),
        result_tables_sprake.create_wind_results(res, False),
    ]
                    
    table_name = 'table_generation_wind'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        wind_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        wind_results[1],
        mark_stale = stale
    )

    pv_results = [
        result_tables_sprake.create_pv_results(res, True),
        result_tables_sprake.create_pv_results(res, False),
    ]

    table_name = 'table_generation_pv'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        pv_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        pv_results[1],
        mark_stale = stale
    )

    combined_generation_results = [
        result_tables_sprake.create_combined_generation_results(res, True),
        result_tables_sprake.create_combined_generation_results(res, False)
    ]

    table_name = 'table_generation_combined'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        combined_generation_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        combined_generation_results[1],
        mark_stale = stale
    )

    return 'ok'

TABLE_SECTION = 'table_consumption'
_request_table_draw_consumption = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_consumption'])
def _make_consumption_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    result_type = 'postproc_consumption'
    proj = project_provider.get_project(request.project_id)

    res, stale = get_result_list(result_type, proj, result_provider, True)

    consumption_results = [
        result_tables_sprake.create_cons_results(res, True),
        result_tables_sprake.create_cons_results(res, False)
    ]
    table_name = 'table_consumption'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        consumption_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        consumption_results[1],
        mark_stale = stale
    )

    seasonal_consumption_results = [
        result_tables_sprake.create_seasonal_cons_results(res, True),
        result_tables_sprake.create_seasonal_cons_results(res, False),
    ]
    table_name = 'table_consumption_seasonal'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        seasonal_consumption_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        seasonal_consumption_results[1],
        mark_stale = stale
    )
    return 'ok'

TABLE_SECTION = 'table_storage'
_request_table_draw_storage = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_storage'])
def _make_storage_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    result_type = 'postproc_storage'
    proj = project_provider.get_project(request.project_id)

    res,stale = get_result_list(result_type, proj, result_provider, True)

    storage_results = [
        result_tables_sprake.create_stor_results(res, True),
        result_tables_sprake.create_stor_results(res, False)
    ]
    table_name = 'table_storage'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        storage_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        storage_results[1],
        mark_stale = stale
    )

    return 'ok'

TABLE_SECTION = 'table_net'
_request_table_draw_net = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_net'])
def _make_net_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    result_type = 'postproc_net'
    proj = project_provider.get_project(request.project_id)

    res, stale = get_result_list(result_type, proj, result_provider, True)

    net_results = [
        result_tables_sprake.create_net_results(res, True),
        result_tables_sprake.create_net_results(res, False)
    ]
    table_name = 'table_net'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        net_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        net_results[1],
        mark_stale = stale
    )

    seasonal_net_results = [
        result_tables_sprake.create_seasonal_net_results(res, True),
        result_tables_sprake.create_seasonal_net_results(res, False),
    ]
    table_name = 'table_net_seasonal'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        seasonal_net_results[0],
        mark_stale = stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        seasonal_net_results[1],
        mark_stale = stale
    )

    return 'ok'

TABLE_SECTION = 'table_finance'
_request_table_draw_finance = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_finance_benefits', 'postproc_finance_costs', 'postproc_finance_value'])
def _make_finance_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    proj = project_provider.get_project(request.project_id)

    # TODO: Check which of these actually needs reprocessing, as we have multiple
    # triggers.

    benefits, b_stale = get_result_list(
        'postproc_finance_benefits', proj,
        result_provider, True
    )
    benefits_results = [
        result_tables_sprake.create_so_benefits_results(benefits, True),
        result_tables_sprake.create_so_benefits_results(benefits, False)
    ]
    table_name = 'table_finance_so_benefits'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        benefits_results[0],
        mark_stale = b_stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        benefits_results[1],
        mark_stale = b_stale
    )
    
    costs, c_stale = get_result_list(
        'postproc_finance_costs', proj,
        result_provider, True
    )
    costs_results = [
        result_tables_sprake.create_so_costs_results(costs, True),
        result_tables_sprake.create_so_costs_results(costs, False),
    ]
    table_name = 'table_finance_so_costs'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        costs_results[0],
        mark_stale = c_stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        costs_results[1],
        mark_stale = c_stale
    )

    value, v_stale = get_result_list(
        'postproc_finance_value', proj,
        result_provider, True
    )
    value_results = [
        result_tables_sprake.create_so_value_results(value, True),
        result_tables_sprake.create_so_value_results(value, False),
    ]
    table_name = 'table_finance_so_value'
    result_provider.upsert_result(
        table_name + '_ann',
        proj.table_config,
        value_results[0],
        mark_stale = v_stale
    )
    result_provider.upsert_result(
        table_name + '_hori',
        proj.table_config,
        value_results[1],
        mark_stale = v_stale
    )

    return 'ok'

TABLE_SECTION = 'table_dsa_metamodel'
_request_table_draw_dsa_metamodel = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_dsa_metamodel'])
def _make_dsa_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    proj = project_provider.get_project(request.project_id)
            
    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    mm = proj.get_metamodel_by_id(mm_id)

    raw_table, rev = result_provider.get_result('postproc_dsa_single_metamodel_data', mm.table_config, allow_stale = False)
    if raw_table is None:
        return 'missing'
    stale = mm.table_config.revision != rev

    dsa_statistics = list(sensitivity.DSA_STATISTIC_LABELS.keys())

    table_name = 'table_dsa_metamodel'
    for stat in dsa_statistics:
        otable = (
            raw_table
            .xs(stat, level=1, axis=0)
            .xs('absolute', level = 0, axis = 1)
            .loc[:,['central', 'interval', 'lower', 'upper']]
            .reset_index()
        )
        formatters = {
            'variable': {"function":  "params.value ? params.value : '-' "},
        }
        columnDefs = [
            {
                'field': i,
                "valueFormatter": formatters.get(i, {"function":  "params.value ? d3.format(',.2f')(params.value) : '-' "})
            }
            for i in otable.columns
        ]
        res = dag.AgGrid(
            rowData = otable.to_dict('records'),
            columnDefs = columnDefs
        )
        result_provider.upsert_result(
            table_name + '_' + stat,
            mm.table_config,
            res,
            mark_stale = stale
        )
    
    return 'ok'

@register_table_getter(TABLE_SECTION, MODEL_TYPE)
def _get_dsa_metamodel_table(
    active_project_id: str,
    table_options: dict,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface
):
    stat = table_options.get('statistic')
    subindex = table_options['subindex']

    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()

    match int(subindex):
        case 1:
            #Tornado!
            dsa_df, rev = result_provider.get_result('postproc_dsa_single_metamodel_data', mm.table_config)
            #dsa_df, rev = result_provider.get_result('dsa_single_metamodel', mm.table_config)
            if dsa_df is None:
                return None, None
            index_vars = ['variable', 'statistic']
            if not set(dsa_df.index.names) == set(index_vars):
                dsa_df = dsa_df.set_index(index_vars)

            label_df, _ = result_provider.get_result('postproc_dsa_single_metamodel_labels', mm.table_config)


            stat = 'net_present_value_undiscounted' if not stat else stat
            plot = tornado_plot(dsa_df, label_df, stat)
            return plot, rev
        case _:
            if stat:
                table_name = 'table_dsa_metamodel_'+stat
            else:
                table_name = 'table_dsa_metamodel'

            proj = project_provider.get_project(active_project_id)
            mm = proj.get_focussed_metamodel()
            return result_provider.get_result(table_name, mm.table_config, True)

