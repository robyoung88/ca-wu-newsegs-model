"""The postprocess procedures of the `sprake` model type.

Each procedure, registered for a name and started when a run completes, converts the results of the run of a NewSEGS Energy Model or finance model - or
the DSA or PSA - into the form shown in the interface (summary statistics, in tables), with the functions of `postprocess.methods`.
"""
from dataclasses import asdict
import json
from typing import Callable, cast

import pandas as pd

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsMetamodelProvider, FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.registers import PostprocessRequest, RunRequest, register_postprocess_procedure, register_postprocess_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import dsa

from .methods import post_dsa_results
from .methods import post_psa_results
from .methods.post_sprake_consumption_results import consumption_results_to_interface_sprake
from .methods.post_sprake_finance_benefits_results import finance_benefits_results_to_interface_sprake
from .methods.post_sprake_finance_costs_results import finance_costs_results_to_interface_sprake
from .methods.post_sprake_finance_value_results import finance_value_results_to_interface_sprake
from .methods.post_sprake_gen_results import gen_results_to_interface_sprake
from .methods.post_sprake_net_results import net_results_to_interface_sprake
from .methods.post_sprake_storage_results import stor_results_to_interface_sprake

def _postprocess_request_factory(postproc_request_type: str, **kwargs):
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
        return PostprocessRequest(**rdict)    
    return make_request

MODEL_TYPE = 'default'
POSTPROCESS_TYPE = 'postproc_grid'
_request_postprocess_model_grid = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _grid_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    # Do nothing - grid currently has no postproc
    return 'ok'


POSTPROCESS_TYPE = 'postproc_generation'
_request_postprocess_model_generation = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _generation_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)
   
    if request.trigger_request_type == 'deterministic_run_project':
        lmetamodels = lproj.metamodels
    
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'

    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing generation - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            mdl.table_config.id, revision = mdl.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)

        any_stale = full_model.reattach_results(result_provider, True, request_id = request.trigger_request_id)

        res = gen_results_to_interface_sprake(full_model)
        result_provider.upsert_result(
            result_type, full_model.table_config, res, mark_stale = any_stale, request = request
        )

    return 'ok'

POSTPROCESS_TYPE = 'postproc_consumption'
_request_postprocess_model_consumption = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _consumption_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_type == 'deterministic_run_project':
            lmetamodels = lproj.metamodels
        
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'
    
    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing consumption - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            mdl.table_config.id, revision = mdl.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)

        any_stale = full_model.reattach_results(
            result_provider, True, request_id = request.trigger_request_id
        )

        res = consumption_results_to_interface_sprake(full_model) 
        result_provider.upsert_result(
            result_type, full_model.table_config, res, mark_stale = any_stale, request = request
        )

    return 'ok'

POSTPROCESS_TYPE = 'postproc_storage'
_request_postprocess_model_storage = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _storage_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_type == 'deterministic_run_project':
        lmetamodels = lproj.metamodels
    
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'

    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing storage - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            mdl.table_config.id, revision = mdl.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)

        any_stale = full_model.reattach_results(result_provider, True, request_id = request.trigger_request_id)

        res = stor_results_to_interface_sprake(full_model) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(
            result_type, full_model.table_config, res, mark_stale = any_stale, request = request
        )

    return 'ok'

POSTPROCESS_TYPE = 'postproc_net'
_request_postprocess_model_net = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _net_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_type == 'deterministic_run_project':
            lmetamodels = lproj.metamodels
        
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'

    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing net energy - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            mdl.table_config.id, revision = mdl.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)

        any_stale = full_model.reattach_results(
            result_provider, True, request_id = request.trigger_request_id
        )
        
        res = net_results_to_interface_sprake(full_model) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(
            result_type, full_model.table_config, res, mark_stale = any_stale, request = request
        )

    return 'ok'

POSTPROCESS_TYPE = 'postproc_finance_benefits'
_request_postprocess_finance_benefits = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _finance_benefits_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_type == 'deterministic_run_project':
            lmetamodels = lproj.metamodels
        
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'
    
    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing financial benefits - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        fnc = mm.finance

        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            fnc.table_config.id, revision = fnc.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)
        full_finance = cast(NewsegsFinance, mm_provider._fm_provider.get_component(mm.finance.id))
        full_finance.set_model(full_model, dirty = False)

        any_stale = full_model.reattach_results(
            result_provider, True, request_id = request.trigger_request_id
        )

        res = finance_benefits_results_to_interface_sprake(full_model, full_finance) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(
            result_type, full_finance.table_config, res, mark_stale = any_stale, request = request
        )

    return 'ok'

POSTPROCESS_TYPE = 'postproc_finance_costs'
_request_postprocess_finance_costs = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _finance_costs_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_type == 'deterministic_run_project':
            lmetamodels = lproj.metamodels
        
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'

    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing financial costs - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        fnc = mm.finance
        
        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            fnc.table_config.id, revision = fnc.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)
        full_finance = cast(NewsegsFinance, mm_provider._fm_provider.get_component(mm.finance.id))
        full_finance.set_model(full_model, dirty = False)

        any_stale = full_model.reattach_results(
            result_provider, True, request_id = request.trigger_request_id
        )

        res = finance_costs_results_to_interface_sprake(full_model, full_finance) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(
            result_type, full_finance.table_config, res, mark_stale = any_stale, request = request
        )
    return 'ok'

POSTPROCESS_TYPE = 'postproc_finance_value'
_request_postprocess_finance_value = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['deterministic_run_metamodel', 'deterministic_run_project'])
def _finance_value_to_interface_sprake(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    result_type = POSTPROCESS_TYPE, # Use default argument trick to hold value of POSTPROCESS_TYPE
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if request.trigger_request_type == 'deterministic_run_project':
            lmetamodels = lproj.metamodels
        
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))
        lmetamodels = [lmm,]

    else:
        return 'ok'

    n_mm = len(lmetamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(lmetamodels):
        progress_callback(step, n_steps, f'Postprocessing financial value - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        fnc = mm.finance
        
        if result_provider.result_exists(
            result_type, request.trigger_request_id, 
            fnc.table_config.id, revision = fnc.table_config.revision
        ) is not False:
            continue

        mm_provider = cast(
            FromDatabaseNewsegsMetamodelProvider,
            provider.metamodel_provider
        )
        full_model = mm_provider._em_provider.get_component(mm.model.id)
        full_finance = cast(NewsegsFinance, mm_provider._fm_provider.get_component(mm.finance.id))
        full_finance.set_model(full_model, dirty = False)

        any_stale = full_model.reattach_results(
            result_provider, True, request_id = request.trigger_request_id
        )


        res = finance_value_results_to_interface_sprake(full_model, full_finance) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(
            result_type, full_finance.table_config, res, mark_stale = any_stale, request = request
        )

    return 'ok'

# -----------------------------------------------
# DSA
# -----------------------------------------------

POSTPROCESS_TYPE = 'postproc_dsa_metamodel'
_request_postprocess_dsa_metamodel = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['dsa_run_metamodel'])
def _dsa_to_interface(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))

    if result_provider.result_exists(
        'postproc_dsa_single_metamodel_data', request.trigger_request_id, 
        lmm.table_config.id, revision = lmm.table_config.revision
    ) is not False:
        return 'ok'

    dsa_results, rev = result_provider.get_result(
        'dsa_single_metamodel', lmm.table_config, True
    )

    if dsa_results is None:
        return 'missing'
    any_stale = rev != lmm.table_config.revision

    index_vars = ['variable', 'bound']
    if not set(dsa_results.index.names) == set(index_vars):
        dsa_results = dsa_results.set_index(index_vars)
    res_table, label_table = post_dsa_results.dsa_results_to_tables(dsa_results)

    data_table = provider._component_provider.get_lightweight_dataholding_component(lmm.table_config.id)

    result_provider.upsert_result('postproc_dsa_single_metamodel_data', data_table, res_table, mark_stale = any_stale, request = request)
    result_provider.upsert_result('postproc_dsa_single_metamodel_labels', data_table, label_table, mark_stale = any_stale, request = request)

    return 'ok'

POSTPROCESS_TYPE = 'postproc_dsa_project'
_request_postprocess_dsa_project = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['dsa_run_project'])
def _dsa_project_to_interface(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    """Convert the results of a whole-project DSA into the tables of each metamodel.

    Stores, on the project table configuration, the tables of every metamodel (indexed by 'metamodel', 'variable'
    and 'statistic') and their labels; and, on the table configuration of each metamodel, its own tables, as
    after a DSA of that metamodel alone. Pairwise comparisons are made when they are shown.
    """
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    if result_provider.result_exists(
        'postproc_dsa_project_data', request.trigger_request_id,
        lproj.table_config.id, revision = lproj.table_config.revision
    ) is not False:
        return 'ok'

    dsa_results, rev = result_provider.get_result('dsa_project', lproj.table_config, True)
    if dsa_results is None:
        return 'missing'
    any_stale = rev != lproj.table_config.revision

    res_tables, label_tables = {}, {}
    for lmm in lproj.metamodels:
        try:
            single = dsa.dsa_multiple_for_metamodel(dsa_results, lmm.id)
        except KeyError:
            # Metamodel added since the DSA was run
            continue
        if len(single) < 2:
            continue
        res_table, label_table = post_dsa_results.dsa_results_to_tables(single.set_index(['variable', 'bound']))
        res_tables[lmm.id], label_tables[lmm.id] = res_table, label_table

        mm_data_table = provider._component_provider.get_lightweight_dataholding_component(lmm.table_config.id)
        result_provider.upsert_result('postproc_dsa_single_metamodel_data', mm_data_table, res_table, mark_stale = any_stale, request = request)
        result_provider.upsert_result('postproc_dsa_single_metamodel_labels', mm_data_table, label_table, mark_stale = any_stale, request = request)

    if not res_tables:
        return 'missing'

    data_table = provider._component_provider.get_lightweight_dataholding_component(lproj.table_config.id)
    result_provider.upsert_result(
        'postproc_dsa_project_data', data_table,
        pd.concat(res_tables, names = ['metamodel']), mark_stale = any_stale, request = request
    )
    result_provider.upsert_result(
        'postproc_dsa_project_labels', data_table,
        pd.concat(label_tables, names = ['metamodel']), mark_stale = any_stale, request = request
    )

    return 'ok'

# -----------------------------------------------
# PSA
# -----------------------------------------------

POSTPROCESS_TYPE = 'postproc_psa_metamodel'
_request_postprocess_psa_metamodel = register_postprocess_request(POSTPROCESS_TYPE)(_postprocess_request_factory(POSTPROCESS_TYPE))

@register_postprocess_procedure(POSTPROCESS_TYPE, MODEL_TYPE, ['psa_run_metamodel'])
def _psa_to_interface(
    request: PostprocessRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(request.project_id)

    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    lmm = next(iter(filter(lambda x: x.id == mm_id, lproj.metamodels)))

    if result_provider.result_exists(
        'postproc_psa_single_metamodel_data', request.trigger_request_id, 
        lmm.table_config.id, revision = lmm.table_config.revision
    ) is not False:
        return 'ok'

    psa_results, rev = result_provider.get_result(
        'psa_single_metamodel', lmm.table_config, True, lmm.table_config.revision
    )

    if psa_results is None:
        return 'missing'
    any_stale = rev != lmm.table_config.revision

    res_table, ppv = post_psa_results.psa_results_to_tables(psa_results)

    data_table = provider._component_provider.get_lightweight_dataholding_component(lmm.table_config.id)

    result_provider.upsert_result(
        'postproc_psa_single_metamodel_data', data_table,
        res_table, mark_stale = any_stale, request = request
    )
    result_provider.upsert_result(
        'postproc_psa_single_metamodel_prob_positive_npv', data_table,
        ppv, mark_stale = any_stale, request = request
    )

    return 'ok'
