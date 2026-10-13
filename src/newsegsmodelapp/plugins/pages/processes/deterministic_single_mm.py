from dataclasses import dataclass
import datetime
import json
from typing import Callable

from newsegsmodelapp.plugins.pages.processes.common_deterministic import deterministic_run_metamodel
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface

REQUEST_TYPE = 'deterministic_run_metamodel'

@dataclass
class DeterministicRunMetamodelRunRequest(RunRequest):
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def request_deterministic_single_mm_run(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict | None = None):
    mm_id = project_provider.get_focussed_metamodel_id(project_id)
    return DeterministicRunMetamodelRunRequest(
        project_id = project_id,
        request_label = 'Deterministic run for single metamodel - ' + str(datetime.datetime.now()),
        payload = json.dumps({
            'metamodel_id': mm_id
        })
    )

@register_run_procedure(REQUEST_TYPE)
def execute_deterministic_single_mm_run(
    request: DeterministicRunMetamodelRunRequest,
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
    for mm in proj.metamodels:
        if mm.id == mm_id:
            break
    else:
        raise KeyError(f'Metamodel {mm_id} not found for project {proj.id} - available values are {[x.id for x in proj.metamodels]}.')

    deterministic_run_metamodel(
        mm,
        proj,
        request,
        project_provider,
        result_provider,
        run_id,
        progress_callback,
        check_cancel_status,
        start_step = 0,
        total_steps = 2,
        sequence_number = 1
    )
    # # Ensure that the output tables get updated
    # #proj.table_config.revision += 1

    # n_steps = 3
    # step = 0
    # progress_callback(step, n_steps, f'Setting model variables.')

    # revisions = {
    #     'grid': mm.model.grid.revision,
    #     'generation': mm.model.generation.revision,
    #     'consumption_storage': mm.model.consumption_storage.revision
    # }

    # mm.sync_model_with_changed_variables_deterministic()

    # if check_cancel_status():
    #     raise InterruptedError(f'Process {run_id} has been cancelled.')

    # # Each result is dependent on the previous module.
    # # We assume that results available for the current revision of a module
    # # will be valid if the previous module has results.
    # try_get_grid = mm.model.grid.revision == revisions['grid']
    # try_get_generation = try_get_grid and mm.model.generation.revision == revisions['generation']
    # try_get_cs = try_get_generation and mm.model.consumption_storage.revision == revisions['consumption_storage']

    # model_run_from = 'start'
    # if try_get_grid:
    #     grid_res = result_provider.get_result(
    #         'deterministic_grid', mm.model.grid,
    #         allow_stale = False
    #     )
    #     if grid_res is None:
    #         try_get_generation = False
    #         try_get_cs = False
    #     else:
    #         mm.model._grid_result = grid_res
    #         model_run_from = 'grid'
    # if try_get_generation:
    #     generation_res = result_provider.get_result(
    #         'deterministic_generation', mm.model.generation,
    #         allow_stale = False
    #     )
    #     if generation_res is None:
    #         try_get_cs = False
    #     else:
    #         mm.model._generation_result = generation_res
    #         model_run_from = 'generation'
    # if try_get_cs:
    #     cs_res = result_provider.get_result(
    #         'deterministic_consumption_storage', mm.model.consumption_storage,
    #         allow_stale = False
    #     )
    #     if cs_res is not None:
    #         mm.model._cs_result = cs_res
    #         model_run_from = 'complete'   

    # step += 1
    # if model_run_from == 'complete':
    #     progress_callback(step, n_steps, 'Model already run')
    # else:
    #     progress_callback(step, n_steps, f'Running model.')
    #     mm.model.run(run_from = model_run_from)
    #     mm.model.table_config.revision += 1
    #     project_provider.metamodel_provider._em_provider.upsert_component(mm.model)

    # if check_cancel_status():
    #     raise InterruptedError(f'Process {run_id} has been cancelled.')

    # step += 1
    # progress_callback(step, n_steps, f'Running finance.')

    # if model_run_from == 'complete':
    #     # Nothing to do for finance, skip
    #     pass
    # else:
    #     mm.finance.run()
    #     mm.finance.table_config.revision += 1
    #     project_provider.metamodel_provider._fm_provider.upsert_component(mm.finance)

    #     # Invalidate downstream tables
    #     project_provider._component_provider.increment_revision([
    #         proj.table_config.id,
    #         mm.table_config.id,
    #         mm.model.table_config.id,
    #         mm.finance.table_config.id,
    #     ])

    # if check_cancel_status():
    #     raise InterruptedError(f'Deterministic single configuration process {run_id} has been cancelled.')

    # step += 1
    # progress_callback(step, n_steps, f'Saving results.')

    # if model_run_from == 'start':
    #     result_provider.upsert_result(
    #         'deterministic_grid', mm.model.grid, 
    #         mm.model.get_grid_result(), request = request
    #     )
    # else:
    #     result_provider.duplicate_result(
    #         'deterministic_grid', mm.model.grid, request,
    #     )

    # if model_run_from in ('start', 'grid'):
    #     result_provider.upsert_result(
    #         'deterministic_generation', mm.model.generation,
    #         mm.model.get_generation_result(), request = request
    #     )
    # else:
    #     result_provider.duplicate_result(
    #         'deterministic_generation', mm.model.generation, request
    #     )

    # if model_run_from in ('start', 'grid', 'generation'):
    #     result_provider.upsert_result(
    #         'deterministic_consumption_storage', mm.model.consumption_storage, 
    #         mm.model.get_consumption_storage_result(), request = request
    #     )
    # else:
    #     result_provider.duplicate_result(
    #         'deterministic_consumption_storage', mm.model.consumption_storage, request
    #     )

    return 'ok'
