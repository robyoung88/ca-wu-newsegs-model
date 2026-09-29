from dataclasses import asdict
import json
from typing import Callable

from newsegsmodelapp.registers import PostprocessRequest, RunRequest, register_postprocess_procedure, register_postprocess_request
from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

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
        rdict['trigger_run_id'] = request.trigger_run_id if request.trigger_run_id != -1 else rdict.pop('run_id', -1)
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

def _result_already_exists(
    result_provider: NewsegsResultProviderInterface,
    result_type: str,
    component: NewsegsComponent,
    run_id: int = -1,
):
    if run_id != -1:
        # Check under the triggering run if provided
        exist_res, exist_res = result_provider.get_run_result(
            result_type, run_id, component,
        )
        if exist_res is not None:
            return True
    else:
        # We have a generic request - find latest result
        exist_res, exist_rev = result_provider.get_result(
            result_type, component, False
        )
        if exist_res is not None:
            return True
    return False


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

        if _result_already_exists(
            result_provider, result_type, mdl.table_config, request.trigger_run_id,
        ):
            continue

        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = gen_results_to_interface_sprake(mdl)
        result_provider.upsert_result(
            result_type, mdl.table_config, res, mark_stale = any_stale, request = request
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

        if _result_already_exists(
            result_provider, result_type, mdl.table_config, request.trigger_run_id,
        ):
            continue

        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = consumption_results_to_interface_sprake(mdl) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(result_type, mdl.table_config, res, mark_stale = any_stale, request = request)

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

        if _result_already_exists(
            result_provider, result_type, mdl.table_config, request.trigger_run_id,
        ):
            continue
                
        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = stor_results_to_interface_sprake(mdl) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(result_type, mdl.table_config, res, mark_stale = any_stale, request = request)

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

        if _result_already_exists(
            result_provider, result_type, mdl.table_config, request.trigger_run_id,
        ):
            continue
                
        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = net_results_to_interface_sprake(mdl) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(result_type, mdl.table_config, res, mark_stale = any_stale, request = request)

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

        if _result_already_exists(
            result_provider, result_type, fnc.table_config, request.trigger_run_id,
        ):
            continue

        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = finance_benefits_results_to_interface_sprake(mdl, fnc) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result(result_type, fnc.table_config, res, mark_stale = any_stale, request = request)

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

        if _result_already_exists(
            result_provider, result_type, fnc.table_config, request.trigger_run_id,
        ):
            continue

        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = finance_costs_results_to_interface_sprake(mdl, fnc) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_finance_costs', fnc.table_config, res, mark_stale = any_stale, request = request)

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

        if _result_already_exists(
            result_provider, result_type, fnc.table_config, request.trigger_run_id,
        ):
            continue

        any_stale = mdl.reattach_results(result_provider, True, run_id = request.trigger_run_id)

        res = finance_value_results_to_interface_sprake(mdl, fnc) # pyright: ignore[reportArgumentType]
        result_provider.upsert_result('postproc_finance_value', fnc.table_config, res, mark_stale = any_stale, request = request)

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
    proj = project_provider.get_project(request.project_id)
        
    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    mm = proj.get_metamodel_by_id(mm_id)


    if _result_already_exists(
        result_provider, 'postproc_dsa_single_metamodel_data', mm.table_config, request.trigger_run_id,
    ):
        return 'ok'
    
    dsa_results, rev = result_provider.get_result('dsa_single_metamodel', mm.table_config, True)
    if dsa_results is None:
        return 'missing'
    any_stale = rev != mm.table_config.revision

    index_vars = ['variable', 'bound']
    if not set(dsa_results.index.names) == set(index_vars):
        dsa_results = dsa_results.set_index(index_vars)
    res_table, label_table = post_dsa_results.dsa_results_to_tables(dsa_results)

    result_provider.upsert_result('postproc_dsa_single_metamodel_data', mm.table_config, res_table, mark_stale = any_stale, request = request)
    result_provider.upsert_result('postproc_dsa_single_metamodel_labels', mm.table_config, label_table, mark_stale = any_stale, request = request)

    return 'ok'

# -----------------------------------------------
# DSA
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
    proj = project_provider.get_project(request.project_id)
        
    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    mm = proj.get_metamodel_by_id(mm_id)

    if _result_already_exists(
        result_provider, 'postproc_psa_single_metamodel_data', mm.table_config, request.trigger_run_id,
    ):
        return 'ok'

    psa_results, rev = result_provider.get_result('psa_single_metamodel', mm.table_config, True)
    if psa_results is None:
        return 'missing'
    any_stale = rev != mm.table_config.revision

    res_table, ppv = post_psa_results.psa_results_to_tables(psa_results)

    result_provider.upsert_result('postproc_psa_single_metamodel_data', mm.table_config, res_table, mark_stale = any_stale, request = request)
    result_provider.upsert_result('postproc_psa_single_metamodel_prob_positive_npv', mm.table_config, ppv, mark_stale = any_stale, request = request)

    return 'ok'
