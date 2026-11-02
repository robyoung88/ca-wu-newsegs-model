"""The table drawing and table getting procedures of the `sprake` model type.

Each procedure, registered for a table section and started when a postprocess procedure completes, draws the table data of a kind of result - grid, generation, consumption, storage,
net flows, finance, DSA, PSA and optimisation - and stores it.
"""
import logging
logger = logging.getLogger(__name__)

from dataclasses import asdict
import json
from typing import Callable, cast

import dash_ag_grid as dag
from dash import html

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsComponentProvider, FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components.stats import tornado_plot
from newsegsmodelapp.registers import RunRequest, TableDrawRequest, register_table_draw, register_table_draw_request, register_table_getter
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import common as sensitivity, optim

from . import result_tables_sprake
from .get_result_list import get_result_list

def _get_metamodel_from_proj_by_id(mm_id, lproj):
    for mm in lproj.metamodels:
        if mm.id == mm_id:
            break
    else:
        mm = None
    if mm is None:
        raise ValueError(f'Metamodel {mm_id} not found for project {lproj.id}')
    return mm

def _table_draw_request_factory(postproc_request_type: str, **kwargs):
    _update_kwargs = {k:v for k,v in kwargs.items()}
    def make_request(request: RunRequest, config: dict | None = None):
        rdict = asdict(request)
        request_type = rdict.pop('request_type', '')
        _ = rdict.pop('request_class', '')
        rdict['request_type'] = postproc_request_type
        rdict['trigger_request_type'] = request_type
        # The trigger should be carried forward from the inciting event
        rdict['trigger_request_id'] = request.trigger_request_id if request.trigger_request_id != -1 else rdict.pop('request_id', -1)
        _ = rdict.pop('run_id', -1)
        if config:
            payload = rdict.get('payload', '{}')
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError:
                payload = {}
            payload.update(config)
            rdict['payload'] = json.dumps(payload)
        if _update_kwargs:
            rdict.update(_update_kwargs) # Powerful but dangerous
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
    table_name = 'table_generation_wind'

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', table_name)
    lproj = provider.get_lightweight_project(request.project_id)

    res, stale = get_result_list(result_type, lproj, result_provider, True)

    wind_results = [
        result_tables_sprake.create_wind_results(res, True),
        result_tables_sprake.create_wind_results(res, False),
    ]

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)
                    
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        wind_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        wind_results[1],
        mark_stale = stale,
        request = request
    )

    pv_results = [
        result_tables_sprake.create_pv_results(res, True),
        result_tables_sprake.create_pv_results(res, False),
    ]

    table_name = 'table_generation_pv'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        pv_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        pv_results[1],
        mark_stale = stale,
        request = request
    )

    combined_generation_results = [
        result_tables_sprake.create_combined_generation_results(res, True),
        result_tables_sprake.create_combined_generation_results(res, False)
    ]

    table_name = 'table_generation_combined'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        combined_generation_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        combined_generation_results[1],
        mark_stale = stale,
        request = request
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
    table_name = 'table_consumption'

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', table_name)
    lproj = provider.get_lightweight_project(request.project_id)

    res, stale = get_result_list(result_type, lproj, result_provider, True)

    consumption_results = [
        result_tables_sprake.create_cons_results(res, True),
        result_tables_sprake.create_cons_results(res, False)
    ]

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)
    
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        consumption_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        consumption_results[1],
        mark_stale = stale,
        request = request
    )

    seasonal_consumption_results = [
        result_tables_sprake.create_seasonal_cons_results(res, True),
        result_tables_sprake.create_seasonal_cons_results(res, False),
    ]

    table_name = 'table_consumption_seasonal'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        seasonal_consumption_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        seasonal_consumption_results[1],
        mark_stale = stale,
        request = request
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
    table_name = 'table_storage'

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', table_name)
    lproj = provider.get_lightweight_project(request.project_id)

    res,stale = get_result_list(result_type, lproj, result_provider, True)

    storage_results = [
        result_tables_sprake.create_stor_results(res, True),
        result_tables_sprake.create_stor_results(res, False)
    ]

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)

    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        storage_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        storage_results[1],
        mark_stale = stale,
        request = request
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
    table_name = 'table_net'

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', table_name)
    lproj = provider.get_lightweight_project(request.project_id)

    res, stale = get_result_list(result_type, lproj, result_provider, True)

    net_results = [
        result_tables_sprake.create_net_results(res, True),
        result_tables_sprake.create_net_results(res, False)
    ]

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)

    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        net_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        net_results[1],
        mark_stale = stale,
        request = request
    )

    seasonal_net_results = [
        result_tables_sprake.create_seasonal_net_results(res, True),
        result_tables_sprake.create_seasonal_net_results(res, False),
    ]

    table_name = 'table_net_seasonal'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        seasonal_net_results[0],
        mark_stale = stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        seasonal_net_results[1],
        mark_stale = stale,
        request = request
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

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', 'table_finance')
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_id != request.request_id and request.trigger_request_id != -1:
        # Have a downstream request. Only run full logic if
        # 1) All upstream tables have been created
        # 2) Downstream tables have not been made for this run

        # As (2) is the fastest to check, we will do that first
        op_table_names = (
            'table_finance_so_benefits_ann',
            'table_finance_so_costs_ann',
            'table_finance_so_value_ann'
        )
        all_op_exist = True
        for tbl_nm in op_table_names:
            res_id = result_provider.result_exists(
                tbl_nm, request.trigger_request_id,
                lproj.table_config
            )
            if res_id is False:
                all_op_exist = False
                break

        if all_op_exist:
            # Can safely exit
            return 'ok'
        
        # Now check that all upstream tables are created
        
        try:
            request_dict = json.loads(request.payload)
        except:
            request_dict = {}

        mm_ids = request_dict.get('metamodel_id', None)

        if mm_ids is None:
            mm_ids = [x.id for x in lproj.metamodels]
        else:
            mm_ids = [mm_ids]

        # Sublists hold results for the currently run metamodel if on a single metamodel run,
        # or all metamodels if on a full project run (and so are not sublists but full lists)
        benefit_result_sublist = []
        b_stale = False
        
        cost_result_sublist = []
        c_stale = False
        
        value_result_sublist = []
        v_stale = False

        for mm_id in mm_ids:
            lmm = lproj.metamodels[[x.id for x in lproj.metamodels].index(mm_id)]
            
            pp_fnc_ben = result_provider.result_exists(
                'postproc_finance_benefits', 
                request.trigger_request_id,
                lmm.finance.table_config
            )
            if pp_fnc_ben == False:
                return 'missing'
            res, rev = result_provider.get_result_by_id(pp_fnc_ben)
            benefit_result_sublist.append(res)
            b_stale = b_stale or rev != lmm.finance.table_config.revision

            pp_fnc_costs = result_provider.result_exists(
                'postproc_finance_costs', 
                request.trigger_request_id,
                lmm.finance.table_config
            )
            if pp_fnc_costs == False:
                return 'missing'
            res, rev = result_provider.get_result_by_id(pp_fnc_costs)
            cost_result_sublist.append(res)
            c_stale = c_stale or rev != lmm.finance.table_config.revision

            pp_fnc_value = result_provider.result_exists(
                'postproc_finance_value', 
                request.trigger_request_id,
                lmm.finance.table_config
            )
            if pp_fnc_value == False:
                return 'missing'
            res, rev = result_provider.get_result_by_id(pp_fnc_value)
            value_result_sublist.append(res)
            v_stale = v_stale or rev != lmm.finance.table_config.revision

        # As we have made it this far, continue with production of tables
        jdx = 0
        
        if len(mm_ids) != len(lproj.metamodels):
            benefits = []
            costs = []
            value = []
            for lmm in lproj.metamodels:
                if lmm.id in mm_ids:
                    benefits.append(benefit_result_sublist[jdx])
                    costs.append(cost_result_sublist[jdx])
                    value.append(value_result_sublist[jdx])
                    jdx += 1
                else:
                    # Benefits
                    res, rev = result_provider.get_result(
                        'postproc_finance_benefits', lmm.finance.table_config,
                        allow_stale = True
                    )
                    benefits.append(res)
                    b_stale = b_stale or rev is None or rev != lmm.finance.table_config.revision

                    # Costs
                    res, rev = result_provider.get_result(
                        'postproc_finance_costs', lmm.finance.table_config,
                        allow_stale = True
                    )
                    costs.append(res)
                    c_stale = c_stale or rev is None or rev != lmm.finance.table_config.revision

                    # Value
                    res, rev = result_provider.get_result(
                        'postproc_finance_value', lmm.finance.table_config,
                        allow_stale = True
                    )
                    value.append(res)
                    v_stale = v_stale or rev is None or rev != lmm.finance.table_config.revision
        else:
            benefits = benefit_result_sublist
            costs = cost_result_sublist
            value = value_result_sublist

    else:
        # If a request is generated from the front-end, always just try to make a table
        benefits, b_stale = get_result_list(
            'postproc_finance_benefits', lproj,
            result_provider, True
        )

        costs, c_stale = get_result_list(
            'postproc_finance_costs', lproj,
            result_provider, True
        )

        value, v_stale = get_result_list(
            'postproc_finance_value', lproj,
            result_provider, True
        )

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)

    benefits_results = [
        result_tables_sprake.create_so_benefits_results(benefits, True),
        result_tables_sprake.create_so_benefits_results(benefits, False)
    ]

    table_name = 'table_finance_so_benefits'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        benefits_results[0],
        mark_stale = b_stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        benefits_results[1],
        mark_stale = b_stale,
        request = request
    )

    costs_results = [
        result_tables_sprake.create_so_costs_results(costs, True),
        result_tables_sprake.create_so_costs_results(costs, False),
    ]

    table_name = 'table_finance_so_costs'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        costs_results[0],
        mark_stale = c_stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        costs_results[1],
        mark_stale = c_stale,
        request = request
    )

    value_results = [
        result_tables_sprake.create_so_value_results(value, True),
        result_tables_sprake.create_so_value_results(value, False),
    ]
    
    table_name = 'table_finance_so_value'
    result_provider.upsert_result(
        table_name + '_ann',
        table_component,
        value_results[0],
        mark_stale = v_stale,
        request = request
    )
    result_provider.upsert_result(
        table_name + '_hori',
        table_component,
        value_results[1],
        mark_stale = v_stale,
        request = request
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
    
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', 'table_dsa_metamodel')
    lproj = provider.get_lightweight_project(request.project_id)
            
    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')

    mm = _get_metamodel_from_proj_by_id(mm_id, lproj)
     
    raw_table, rev = result_provider.get_result(
        'postproc_dsa_single_metamodel_data', mm.table_config,
        allow_stale = False
    )
    if raw_table is None:
        return 'missing'
    stale = mm.table_config.revision != rev

    # Results from before a statistic was added do not include it
    available_statistics = set(raw_table.index.get_level_values('statistic'))
    dsa_statistics = [s for s in sensitivity.DSA_STATISTIC_LABELS.keys() if s in available_statistics]

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(mm.table_config.id)
    
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
            table_component,
            res,
            mark_stale = stale,
            request = request
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

    lproj = project_provider.get_lightweight_project(active_project_id)
    logger.debug('Getting lightweight project - Table Getter [%s]', 'table_dsa_metamodel')
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    match int(subindex):
        case 1:
            #Tornado!
            dsa_df, rev = result_provider.get_result(
                'postproc_dsa_single_metamodel_data', lmm.table_config
            )
            #dsa_df, rev = result_provider.get_result('dsa_single_metamodel', mm.table_config)
            if dsa_df is None:
                return None, None
            index_vars = ['variable', 'statistic']
            if not set(dsa_df.index.names) == set(index_vars):
                dsa_df = dsa_df.set_index(index_vars)

            label_df, _ = result_provider.get_result(
                'postproc_dsa_single_metamodel_labels', lmm.table_config,
            )

            stat = 'net_present_value_undiscounted' if not stat else stat
            if stat not in dsa_df.index.get_level_values('statistic'):
                return None, None
            plot = tornado_plot(dsa_df, label_df, stat)
            return plot, rev
        case _:
            if stat:
                table_name = 'table_dsa_metamodel_'+stat
            else:
                table_name = 'table_dsa_metamodel'

            return result_provider.get_result(
                table_name, lmm.table_config, True
            )

TABLE_SECTION = 'table_optim_metamodel' # TODO: Improve this key
_request_plot_marginal_optim = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE,)
def _trigger_plot_marginal_optim(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    # NB - use full representation of project, as variables must be syncronised
    # Set partial calling options into the store so that the plotter can get them
    proj = project_provider.get_project(request.project_id)

    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    mm = proj.get_metamodel_by_id(mm_id)

    varid = run_config.get('varid')
    if varid is None or varid not in mm.variables:
        return 'variable missing'

    # TODO: This needs replacing with a dedicated configuration one day.
    if hasattr(proj.dsa_config, 'optim_config'):
        raw_config = proj.dsa_config.optim_config
    else:
        raw_config = {}

    bounds_config = raw_config.get('bounds', {})
    var_bounds = bounds_config.get(varid, {})

    lower = var_bounds.get('lower', 0)
    upper = var_bounds.get('upper', 10000)
    res = var_bounds.get('intervals', 10)

    if lower > upper:
        temp = lower
        lower = upper
        upper = temp

    res = int(res)
    if res <= 0:
        res = 2
    if res > 20:
        res = 20

    stat = run_config.get('statistic', 'net_present_value_discounted')

    # TODO: Add progress
    plot_df = optim.evaluate_statistic_across_margin(
        mm, varid, stat, lower, upper, res
    )

    fig = optim.statistic_across_margin_plot(plot_df, mm)

    result_provider.upsert_result('plot_marginal_optim', proj.table_config, fig, request = request)

    return 'ok'
    
@register_table_getter(TABLE_SECTION, MODEL_TYPE)
def _plot_marginal_optim(
    active_project_id: str,
    table_options: dict,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface
):
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Table Getter [%s]', 'table_optim_metamodel')
    lproj = provider.get_lightweight_project(active_project_id)
    fig, rev = result_provider.get_result(
        'plot_marginal_optim', lproj.table_config,
    )

    return fig, rev

TABLE_SECTION = 'table_postopt_metamodel'
_request_table_draw_postopt_metamodel = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['optim_run_metamodel'])
def _make_postopt_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', 'table_postopt_metamodel')
    lproj = provider.get_lightweight_project(request.project_id)
    
    optdict, _ = result_provider.get_result(
        'optimisation_result', lproj.table_config
    )

    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    
    if optdict is None:
        return 'missing'

    if optdict['success']:
        table_data = [
            html.H4('Success'),
            str(optdict['opt'])
        ]
    else:
        opt = optdict['opt']
        table_data = [
            html.H4('Failure'),
            f'Optimisation was not a success: {opt.message}' + \
            '\n Try again with a different method, variables or bounds.' + \
            str(opt),
        ]

    result_provider.upsert_result(
        'table_postopt_metamodel', lproj.table_config.id, 
        table_data, request=request
    )

    return 'ok'

TABLE_SECTION = 'table_psa_metamodel'
_request_table_draw_psa_metamodel = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))
@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_psa_metamodel'])
def _make_psa_tables_sprake(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', 'table_psa_metamodel')
    lproj = provider.get_lightweight_project(request.project_id)
            
    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    mm = _get_metamodel_from_proj_by_id(mm_id, lproj)

    raw_table, rev = result_provider.get_result(
        'postproc_psa_single_metamodel_data', mm.table_config,
        allow_stale = False
    )
    if raw_table is None:
        return 'missing'
    any_stale = mm.table_config.revision != rev

    psa_statistics = list(sensitivity.PSA_STATISTIC_LABELS.keys())

    table_name = 'table_psa_metamodel'
    otable = (
        raw_table
        .rename(sensitivity.PSA_STATISTIC_LABELS)
        .reset_index(drop=False)
        .rename(columns={'index':'Statistic'})
    )

    rval = []
        
    formatters = {
        'Statistic': {"function":  "params.value ? params.value : '-' "},
    }
    columnDefs = [
        {
            'field': i,
            "valueFormatter": formatters.get(i, {"function":  "params.value ? d3.format(',.2f')(params.value) : '-' "})
        }
        for i in otable.columns
    ]

    tbl1 = dag.AgGrid(
        rowData = otable.to_dict('records'),
        columnDefs = columnDefs
    )

    rval.append(
        tbl1   
    )

    npv_data, rev_ppv = result_provider.get_result(
        'postproc_psa_single_metamodel_prob_positive_npv',
        mm.table_config, allow_stale = False
    )
    if npv_data is None:
        return 'missing'

    pnpv = [
        html.H2('Probability of positive NPV:'),
        html.H3(
            f'Undiscounted: {npv_data.loc['net_present_value_undiscounted','prob_pos_npv']:.1%}'
        ),
        html.H3(
            f'Discounted: {npv_data.loc['net_present_value_discounted','prob_pos_npv']:.1%}'
        ),
    ]
    rval.extend(pnpv)

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(mm.table_config.id)

    result_provider.upsert_result('table_psa_metamodel', table_component, html.Div(rval), mark_stale = any_stale, request=request)
    
    return 'ok'

@register_table_getter(TABLE_SECTION, MODEL_TYPE)
def _get_psa_metamodel_table(
    active_project_id: str,
    table_options: dict,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface
):
    subindex = table_options['subindex']

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Table Getter [%s]', 'table_psa_metamodel')
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]
    match int(subindex):
        case 1:
            return None, None
        case _:
            
            table_name = 'table_psa_metamodel'

            return result_provider.get_result(
                table_name, lmm.table_config, True
            )
        