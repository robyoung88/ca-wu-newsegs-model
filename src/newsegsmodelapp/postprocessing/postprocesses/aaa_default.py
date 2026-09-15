from dataclasses import asdict
import json
from typing import Callable, cast

from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_consumption_results import consumption_results_to_interface_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_finance_benefits_results import finance_benefits_results_to_interface_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_finance_costs_results import finance_costs_results_to_interface_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_finance_value_results import finance_value_results_to_interface_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_gen_results import gen_results_to_interface_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_net_results import net_results_to_interface_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.post_sprake_storage_results import stor_results_to_interface_sprake
from newsegsmodelapp.registers import PostprocessRequest, RunRequest, register_postprocess_procedure, register_postprocess_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

def _postprocess_request_factory(postproc_request_type: str):
    def make_request(request: RunRequest):
        rdict = asdict(request)
        request_type = rdict.pop('request_type', '')
        _ = rdict.pop('request_class', '')
        rdict['request_type'] = postproc_request_type
        rdict['trigger_request_type'] = request_type
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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing generation - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result('postproc_generation', mdl.table_config, False)
        if exist_res is not None:
            continue

        
        any_stale = mdl.reattach_results(result_provider, True)

        res = gen_results_to_interface_sprake(mdl)
        result_provider.upsert_result('postproc_generation', mdl.table_config, res, mark_stale = any_stale)

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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing consumption - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result('postproc_consumption', mdl.table_config, False)
        if exist_res is not None:
            continue

        any_stale = mdl.reattach_results(result_provider, True)

        res = consumption_results_to_interface_sprake(mdl) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_consumption', mdl.table_config, res, mark_stale = any_stale)

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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing storage - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result('postproc_storage', mdl.table_config, False)
        if exist_res is not None:
            continue
                
        any_stale = mdl.reattach_results(result_provider, True)

        res = stor_results_to_interface_sprake(mdl) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_storage', mdl.table_config, res, mark_stale = any_stale)

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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing net energy - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result('postproc_net', mdl.table_config, False)
        if exist_res is not None:
            continue
                
        any_stale = mdl.reattach_results(result_provider, True)

        res = net_results_to_interface_sprake(mdl) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_net', mdl.table_config, res, mark_stale = any_stale)

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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing financial benefits - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model
        fnc = mm.finance

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result(
            'postproc_finance_benefits',
            fnc.table_config,
            False
        )
        if exist_res is not None:
            continue

        any_stale = mdl.reattach_results(result_provider, True)

        res = finance_benefits_results_to_interface_sprake(mdl, fnc) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_finance_benefits', fnc.table_config, res, mark_stale = any_stale)

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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing financial costs - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model
        fnc = mm.finance

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result(
            'postproc_finance_costs',
            fnc.table_config,
            False
        )
        if exist_res is not None:
            continue

        any_stale = mdl.reattach_results(result_provider, True)

        res = finance_costs_results_to_interface_sprake(mdl, fnc) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_finance_costs', fnc.table_config, res, mark_stale = any_stale)

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
) -> str:
    if request.trigger_request_type == 'deterministic_run_project':
        proj = project_provider.get_project(request.project_id)
        metamodels = proj.metamodels
    elif request.trigger_request_type == 'deterministic_run_metamodel':
        proj = project_provider.get_project(request.project_id)
    
        run_config = json.loads(request.payload)
        mm_id = run_config.get('metamodel_id')
        if not mm_id:
            raise ValueError('Metamodel ID not provided for single run.')
        mm = proj.get_metamodel_by_id(mm_id)
        metamodels = [mm,]
    else:
        return 'ok'

    n_mm = len(metamodels)
    n_steps = n_mm
    step = 0
    for i, mm in enumerate(metamodels):
        progress_callback(step, n_steps, f'Postprocessing financial value - model {i+1} of {n_mm}')
        step += 1

        if check_cancel_status():
            raise InterruptedError(f'Process {run_id} has been cancelled.')

        mdl = mm.model
        fnc = mm.finance

        # Check if result exists
        exist_res, exist_rev = result_provider.get_result(
            'postproc_finance_value',
            fnc.table_config,
            False
        )
        if exist_res is not None:
            continue

        any_stale = mdl.reattach_results(result_provider, True)

        res = finance_value_results_to_interface_sprake(mdl, fnc) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_finance_value', fnc.table_config, res, mark_stale = any_stale)

    return 'ok'
