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
import pandas as pd

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsComponentProvider, FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import stats as results_stats
from newsegsmodelapp.components.stats import tornado_plot
from newsegsmodelapp.registers import RunRequest, TableDrawRequest, register_table_draw, register_table_draw_request, register_table_getter
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import common as sensitivity, dsa, optim, psa

from ..postprocess.methods import post_dsa_results
from newsegsmodelutils.plots import optim as optim_plots

from . import optim_feedback, result_tables_sprake
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

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(mm.table_config.id)

    _draw_dsa_metamodel_grids(raw_table, table_component, stale, request, result_provider)

    return 'ok'

_DSA_VALUE_FORMATTER = {"function":  "params.value ? d3.format(',.2f')(params.value) : '-' "}
_DSA_LABEL_FORMATTER = {"function":  "params.value ? params.value : '-' "}

def _dsa_statistic_grid(otable):
    """AG grid of a table of one statistic of a DSA (from `results_stats.dsa_statistic_table`)"""
    formatters = {
        'variable': _DSA_LABEL_FORMATTER,
    }
    columnDefs = [
        {
            'field': i,
            "valueFormatter": formatters.get(i, _DSA_VALUE_FORMATTER)
        }
        for i in otable.columns
    ]
    return dag.AgGrid(
        rowData = otable.to_dict('records'),
        columnDefs = columnDefs
    )

def _draw_dsa_metamodel_grids(raw_table, table_component, stale, request, result_provider):
    """Store the grid of each statistic of the DSA of a metamodel, as `table_dsa_metamodel_<statistic>`"""
    table_name = 'table_dsa_metamodel'
    # Results from before a statistic was added do not include it
    available_statistics = set(raw_table.index.get_level_values('statistic'))
    for stat in sensitivity.DSA_STATISTIC_LABELS.keys():
        if stat not in available_statistics:
            continue
        res = _dsa_statistic_grid(results_stats.dsa_statistic_table(raw_table, stat))

        result_provider.upsert_result(
            table_name + '_' + stat,
            table_component,
            res,
            mark_stale = stale,
            request = request
        )

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

TABLE_SECTION = 'table_dsa_project'
_request_table_draw_dsa_project = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))

def _dsa_project_labels(lproj) -> dict[str, str]:
    """Labels of the metamodels of a project, by id, for the comparator options"""
    return {
        lmm.id: f'Config {i + 1}: {lmm.name}' if lmm.name else f'Config {i + 1}'
        for i, lmm in enumerate(lproj.metamodels)
    }

@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_dsa_project'])
def _make_dsa_project_tables(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    """Draw the tables of a whole-project DSA.

    Stores the grids of each metamodel (as after a DSA of that metamodel alone) and, on the project, the options of
    the comparator views: the metamodels with results and the variables. The comparator tables and plots depend
    on the options chosen, so are made when they are shown, by `_get_dsa_project_table`.
    """
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', TABLE_SECTION)
    lproj = provider.get_lightweight_project(request.project_id)

    raw_table, rev = result_provider.get_result('postproc_dsa_project_data', lproj.table_config, True)
    if raw_table is None:
        return 'missing'
    stale = lproj.table_config.revision != rev

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    metamodel_ids = list(raw_table.index.get_level_values('metamodel').unique())
    for lmm in lproj.metamodels:
        if lmm.id not in metamodel_ids:
            continue
        table_component = component_provider.get_lightweight_dataholding_component(lmm.table_config.id)
        _draw_dsa_metamodel_grids(
            raw_table.xs(lmm.id, level = 'metamodel'), table_component,
            stale, request, result_provider
        )

    labels = _dsa_project_labels(lproj)
    options = {
        'metamodels': [{'value': x, 'label': labels.get(x, x)} for x in metamodel_ids],
        'variables': list(raw_table.index.get_level_values('variable').unique()),
    }
    result_provider.upsert_result(
        'table_dsa_project_options',
        component_provider.get_lightweight_dataholding_component(lproj.table_config.id),
        options,
        mark_stale = stale,
        request = request
    )

    return 'ok'

def _dsa_comparison_grid(otable):
    """AG grid of a table of one statistic of several comparators (from `results_stats.dsa_comparison_table`)"""
    comparators = list(otable.columns.get_level_values('comparator').unique())
    records = []
    for variable, row in otable.iterrows():
        rec = {'variable': variable}
        for i, comp in enumerate(comparators):
            for bound in results_stats.DSA_BOUND_COLUMNS:
                val = row[(comp, bound)]
                rec[f'c{i}_{bound}'] = None if pd.isna(val) else float(val)
        records.append(rec)
    columnDefs = [{'field': 'variable', 'pinned': 'left', 'valueFormatter': _DSA_LABEL_FORMATTER}] + [
        {
            'headerName': comp,
            'children': [
                {'field': f'c{i}_{bound}', 'headerName': bound, 'valueFormatter': _DSA_VALUE_FORMATTER}
                for bound in results_stats.DSA_BOUND_COLUMNS
            ]
        }
        for i, comp in enumerate(comparators)
    ]
    return dag.AgGrid(rowData = records, columnDefs = columnDefs)

def _as_list(value) -> list:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)

@register_table_getter(TABLE_SECTION, MODEL_TYPE)
def _get_dsa_project_table(
    active_project_id: str,
    table_options: dict,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface
):
    """Get the table (subindex 0) or tornado plot (subindex 1) of a comparator view of a whole-project DSA.

    The options are the view (`multiple` or `pairwise`), the statistic, the comparators of the multiple view, the
    comparator and reference of the pairwise view, and the variables to show (all if none are chosen).
    """
    view = table_options.get('view')
    if view not in ('multiple', 'pairwise'):
        return None, None
    subindex = int(table_options.get('subindex', 0))
    variables = _as_list(table_options.get('variables')) or None
    stat = table_options.get('statistic')

    lproj = project_provider.get_lightweight_project(active_project_id)
    logger.debug('Getting lightweight project - Table Getter [%s]', TABLE_SECTION)
    labels = _dsa_project_labels(lproj)

    if view == 'multiple':
        if stat not in sensitivity.DSA_STATISTIC_LABELS:
            stat = 'net_present_value_undiscounted'
        dsa_df, rev = result_provider.get_result('postproc_dsa_project_data', lproj.table_config, True)
        if dsa_df is None:
            return None, None
        available = list(dsa_df.index.get_level_values('metamodel').unique())
        comparators = [x for x in _as_list(table_options.get('comparators')) if x in available] or available
        dsa_dfs = {labels.get(x, x): dsa_df.xs(x, level = 'metamodel') for x in comparators}
        if subindex == 1:
            label_df, _ = result_provider.get_result('postproc_dsa_project_labels', lproj.table_config, True)
            label_dfs = {}
            if label_df is not None:
                label_dfs = {
                    labels.get(x, x): label_df.xs(x, level = 'metamodel')
                    for x in comparators if x in label_df.index.get_level_values('metamodel')
                }
            color_indexes = {labels.get(x, x): available.index(x) for x in comparators}
            return results_stats.multi_tornado_plot(
                dsa_dfs, stat, variables, label_dfs = label_dfs, color_indexes = color_indexes
            ), rev
        otable = results_stats.dsa_comparison_table(dsa_dfs, stat, variables)
        if otable.empty:
            return html.Div('No results for the chosen configurations and variables'), rev
        return _dsa_comparison_grid(otable), rev

    # Pairwise
    if stat not in sensitivity.DSA_PAIRWISE_STATISTIC_LABELS:
        stat = next(iter(sensitivity.DSA_PAIRWISE_STATISTIC_LABELS))
    comparator = table_options.get('comparator')
    reference = table_options.get('reference')
    if not comparator or not reference:
        return html.Div('Choose a comparator and a reference configuration'), None
    raw, rev = result_provider.get_result('dsa_project', lproj.table_config, True)
    if raw is None:
        return None, None
    try:
        pairwise = dsa.dsa_pairwise(raw, comparator, reference)
    except KeyError:
        return html.Div('No DSA results for the chosen configurations'), rev
    if len(pairwise) < 2:
        return html.Div('No variables were varied in the DSA'), rev
    pw_table, pw_labels = post_dsa_results.dsa_results_to_tables(pairwise.set_index(['variable', 'bound']))
    if subindex == 1:
        title = f'Incremental DSA variation: {labels.get(comparator, comparator)} vs {labels.get(reference, reference)}'
        return results_stats.tornado_plot(pw_table, pw_labels, stat, variables, title = title), rev
    return _dsa_statistic_grid(results_stats.dsa_statistic_table(pw_table, stat, variables)), rev

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
    # The plot is saved at the revision of the table config as stored, which the app looks it up by. Running the
    # model across the margin increments the revisions of the project in memory, without saving them.
    table_revision = project_provider.get_lightweight_project(request.project_id).table_config.revision

    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    mm = proj.get_metamodel_by_id(mm_id)

    varid = run_config.get('varid')
    if varid is None or varid not in mm.variables:
        return 'variable missing'

    var = mm.variables[varid]
    optim.check_optim_bounds([var])
    lower, upper = var.get_optim_bounds()

    res = int(var.optim_plot_intervals)
    if res <= 0:
        res = 2
    if res > 20:
        res = 20

    stat = mm.optim_config.statistic

    # TODO: Add progress
    try:
        plot_df = optim.evaluate_statistic_across_margin(
            mm, varid, stat, lower, upper, res
        )
    finally:
        # The project in memory no longer matches the store (its revisions were incremented), so must not be reused
        # from this process's cache
        project_provider.invalidate_cache_for_component(proj.id)

    fig = optim_plots.statistic_across_margin_plot(plot_df, mm.variables[varid].name)

    result_provider.upsert_result(
        'plot_marginal_optim', proj.table_config, fig, request = request, revision = table_revision
    )

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

    # A component, not a list: a list is saved as JSON, which would turn the components into text
    table_data = html.Div(optim_feedback.create_optimisation_feedback(optdict))

    # Saved against the table configuration, from which the results container reads it; the result
    # provider needs its data-holding description, as do the other tables
    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)
    result_provider.upsert_result(
        'table_postopt_metamodel', table_component,
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

    npv_data, rev_ppv = result_provider.get_result(
        'postproc_psa_single_metamodel_prob_positive_npv',
        mm.table_config, allow_stale = False
    )
    if npv_data is None:
        return 'missing'

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    table_component = component_provider.get_lightweight_dataholding_component(mm.table_config.id)
    _draw_psa_metamodel_table(raw_table, npv_data, table_component, any_stale, request, result_provider)

    return 'ok'

_PSA_VALUE_FORMATTER = {"function":  "params.value ? d3.format(',.2f')(params.value) : '-' "}
_PSA_LABEL_FORMATTER = {"function":  "params.value ? params.value : '-' "}
_PSA_PROBABILITY_FORMATTER = {"function":  "params.value != null ? d3.format('.1%')(params.value) : '-' "}

def _psa_grid(otable, label_columns = ('Statistic', 'Configuration'), probability_columns = ()):
    """AG grid of a table of PSA statistics, labelled by its first column"""
    columnDefs = [
        {
            'field': i,
            "valueFormatter": (
                _PSA_LABEL_FORMATTER if i in label_columns
                else _PSA_PROBABILITY_FORMATTER if i in probability_columns
                else _PSA_VALUE_FORMATTER
            )
        }
        for i in otable.columns
    ]
    return dag.AgGrid(
        rowData = otable.to_dict('records'),
        columnDefs = columnDefs
    )

def _draw_psa_metamodel_table(raw_table, npv_data, table_component, stale, request, result_provider):
    """Store the summary table of the PSA of a metamodel, with its probabilities of a positive NPV, as `table_psa_metamodel`"""
    otable = (
        raw_table
        .rename(sensitivity.PSA_STATISTIC_LABELS)
        .reset_index(drop=False)
        .rename(columns={'index':'Statistic'})
    )

    rval = [_psa_grid(otable)]

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

    result_provider.upsert_result('table_psa_metamodel', table_component, html.Div(rval), mark_stale = stale, request=request)

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

TABLE_SECTION = 'table_psa_project'
_request_table_draw_psa_project = register_table_draw_request(TABLE_SECTION)(_table_draw_request_factory(TABLE_SECTION))

@register_table_draw(TABLE_SECTION, MODEL_TYPE, ['postproc_psa_project'])
def _make_psa_project_tables(
    request: TableDrawRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    """Draw the tables of a whole-project PSA.

    Draws the summary table of each metamodel for its individual view, and stores the options of the comparator
    views (the metamodels and the variables drawn) as `table_psa_project_options`. The comparisons are drawn by
    the table getter, as they depend on the options chosen.
    """
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Creating Table [%s]', TABLE_SECTION)
    lproj = provider.get_lightweight_project(request.project_id)

    raw_table, rev = result_provider.get_result('postproc_psa_project_data', lproj.table_config, True)
    if raw_table is None:
        return 'missing'
    npv_data, _ = result_provider.get_result('postproc_psa_project_prob_positive_npv', lproj.table_config, True)
    if npv_data is None:
        return 'missing'
    stale = lproj.table_config.revision != rev

    component_provider = cast(FromDatabaseNewsegsComponentProvider, provider._component_provider)
    metamodel_ids = list(raw_table.index.get_level_values('metamodel').unique())
    for lmm in lproj.metamodels:
        if lmm.id not in metamodel_ids:
            continue
        table_component = component_provider.get_lightweight_dataholding_component(lmm.table_config.id)
        _draw_psa_metamodel_table(
            raw_table.xs(lmm.id, level = 'metamodel'), npv_data.xs(lmm.id, level = 'metamodel'),
            table_component, stale, request, result_provider
        )

    variables = []
    psa_results, _ = result_provider.get_result('psa_project', lproj.table_config, True)
    if psa_results is not None:
        variables = psa.psa_variable_columns(psa_results)

    labels = _dsa_project_labels(lproj)
    options = {
        'metamodels': [{'value': x, 'label': labels.get(x, x)} for x in metamodel_ids],
        'variables': variables,
    }
    result_provider.upsert_result(
        'table_psa_project_options',
        component_provider.get_lightweight_dataholding_component(lproj.table_config.id),
        options,
        mark_stale = stale,
        request = request
    )

    return 'ok'

def _psa_discount(statistic: str) -> str:
    return 'undiscounted' if statistic.endswith('undiscounted') else 'discounted'

def _psa_ceaf(psa_results, metamodel_ids, labels, available, statistic):
    """The cost-effectiveness acceptability frontier plot of the metamodels, discounted as the statistic"""
    discount = _psa_discount(statistic)
    ceac = psa.psa_ceac(
        psa_results, metamodel_ids, results_stats.DEFAULT_BENEFIT_VALUES,
        cost_statistic = f'total_present_costs_{discount}',
        benefit_statistic = f'total_present_benefits_{discount}',
    )
    return results_stats.psa_ceaf_plot(
        ceac,
        labels = {x: labels.get(x, x) for x in metamodel_ids},
        color_indexes = {x: available.index(x) for x in metamodel_ids},
        title = f'Cost-effectiveness acceptability curves and frontier ({discount})',
    )

@register_table_getter(TABLE_SECTION, MODEL_TYPE)
def _get_psa_project_table(
    active_project_id: str,
    table_options: dict,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface
):
    """Get the table (subindex 0) or plot (subindex 1) of a comparator view of a whole-project PSA.

    The options are the view (`multiple` or `pairwise`), the statistic, the plot (see `results_stats.PSA_PROJECT_PLOTS`), the
    comparators of the multiple view, the comparator and reference of the pairwise view, and the variable of the
    marginal sensitivity plot.
    """
    view = table_options.get('view')
    if view not in results_stats.PSA_PROJECT_PLOTS:
        return None, None
    subindex = int(table_options.get('subindex', 0))
    stat = table_options.get('statistic')
    plot = table_options.get('plot')
    if plot not in results_stats.PSA_PROJECT_PLOTS[view]:
        plot = next(iter(results_stats.PSA_PROJECT_PLOTS[view]))
    variable = table_options.get('variable')

    lproj = project_provider.get_lightweight_project(active_project_id)
    logger.debug('Getting lightweight project - Table Getter [%s]', TABLE_SECTION)
    labels = _dsa_project_labels(lproj)

    psa_results, rev = result_provider.get_result('psa_project', lproj.table_config, True)
    if psa_results is None:
        return None, None
    available = list(psa_results['metamodel'].unique())

    if view == 'multiple':
        if stat not in sensitivity.PSA_STATISTIC_LABELS:
            stat = next(iter(sensitivity.PSA_STATISTIC_LABELS))
        comparators = [x for x in _as_list(table_options.get('comparators')) if x in available] or available
        color_indexes = {labels.get(x, x): available.index(x) for x in comparators}

        if subindex == 0:
            summaries, _ = result_provider.get_result('postproc_psa_project_data', lproj.table_config, True)
            if summaries is None:
                return None, None
            otable = results_stats.psa_summary_comparison_table(
                {labels.get(x, x): summaries.xs(x, level = 'metamodel') for x in comparators
                 if x in summaries.index.get_level_values('metamodel')},
                stat,
            )
            if otable.empty:
                return html.Div('No results for the chosen configurations and statistic'), rev
            return _psa_grid(otable.rename(columns = results_stats.PSA_SUMMARY_COLUMN_LABELS)), rev

        if stat not in psa_results.columns:
            return results_stats._empty_psa_figure('The statistic is not in these PSA results - re-run the PSA'), rev
        match plot:
            case 'ceaf':
                if len(comparators) < 2:
                    return results_stats._empty_psa_figure('Choose at least two configurations to compare'), rev
                return _psa_ceaf(psa_results, comparators, labels, available, stat), rev
            case 'marginal':
                if variable not in psa_results.columns:
                    return results_stats._empty_psa_figure('Choose a variable drawn in the PSA'), rev
                # A configuration which does not vary the variable has no draws of it, and is left out of the plot
                marginals = {
                    labels.get(x, x): psa.psa_marginal(psa_results.loc[psa_results['metamodel'] == x, :], variable, stat)
                    for x in comparators
                }
                return results_stats.psa_marginal_plot(marginals, variable, stat, color_indexes = color_indexes), rev
            case _:
                frames = {x: psa_results.loc[psa_results['metamodel'] == x, :] for x in comparators}
                return results_stats.psa_distribution_plot(
                    {labels.get(x, x): df.loc[~df['deterministic'].astype(bool), stat] for x, df in frames.items()},
                    stat,
                    deterministic = {
                        labels.get(x, x): df.loc[df['deterministic'].astype(bool), stat].iloc[0]
                        for x, df in frames.items() if df['deterministic'].any()
                    },
                    color_indexes = color_indexes,
                ), rev

    # Pairwise
    if stat not in sensitivity.PSA_PAIRWISE_STATISTIC_LABELS:
        stat = next(iter(sensitivity.PSA_PAIRWISE_STATISTIC_LABELS))
    comparator = table_options.get('comparator')
    reference = table_options.get('reference')
    if not comparator or not reference:
        return html.Div('Choose a comparator and a reference configuration'), None
    try:
        pairwise = psa.psa_pairwise(psa_results, comparator, reference)
    except KeyError:
        return html.Div('No PSA results for the chosen configurations'), rev
    comparator_label = labels.get(comparator, comparator)
    reference_label = labels.get(reference, reference)
    versus = f'{comparator_label} vs {reference_label}'

    if subindex == 0:
        statistics = list(sensitivity.PSA_PAIRWISE_STATISTIC_LABELS)
        summary, _ = psa.basic_psa_stats(pairwise, statistics, npv_statistics = [])
        # The probability that the comparator increases each statistic
        sampled = pairwise.loc[~pairwise['deterministic'].astype(bool), statistics]
        summary['P(increase)'] = sampled.gt(0).mean(axis = 0).where(sampled.notna().any(axis = 0))
        otable = (
            summary.loc[:, [x for x in results_stats.PSA_SUMMARY_COLUMNS if x in summary.columns] + ['P(increase)']]
            .dropna(how = 'all', subset = ['Mean'])
            .rename(columns = results_stats.PSA_SUMMARY_COLUMN_LABELS)
            .rename(sensitivity.PSA_PAIRWISE_STATISTIC_LABELS)
            .rename_axis('Statistic')
            .reset_index()
        )
        return html.Div([html.H3(versus), _psa_grid(otable, probability_columns = ('P(increase)',))]), rev

    color_index = available.index(comparator)
    match plot:
        case 'plane':
            return results_stats.psa_ce_plane_plot(
                pairwise, _psa_discount(stat), comparator_label, reference_label, color_index
            ), rev
        case 'ceaf':
            return _psa_ceaf(psa_results, [reference, comparator], labels, available, stat), rev
        case 'marginal':
            if variable not in pairwise.columns:
                return results_stats._empty_psa_figure('Choose a variable drawn in the PSA'), rev
            return results_stats.psa_marginal_plot(
                {versus: psa.psa_marginal(pairwise, variable, stat)}, variable, stat,
                color_indexes = {versus: color_index},
            ), rev
        case _:
            det = pairwise.loc[pairwise['deterministic'].astype(bool), stat]
            return results_stats.psa_distribution_plot(
                {versus: pairwise.loc[~pairwise['deterministic'].astype(bool), stat]},
                stat,
                deterministic = {versus: det.iloc[0]} if len(det) else None,
                color_indexes = {versus: color_index},
                title = f'Distribution of the increment: {versus}',
            ), rev
