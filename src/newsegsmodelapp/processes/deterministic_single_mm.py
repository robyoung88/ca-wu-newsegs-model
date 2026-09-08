from dataclasses import dataclass
import datetime
import json
from typing import Callable, cast

import sqlalchemy as sa

from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface

REQUEST_TYPE = 'deterministic_single_mm'

@dataclass
class DeterministicSingleMMRunRequest(RunRequest):
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def request_deterministic_single_mm_run(proj: NewsegsProject, engine: sa.Engine):
    mm = proj.get_focussed_metamodel()
    return DeterministicSingleMMRunRequest(
        project_id = proj.id,
        request_id = 'Deterministic run - ' + str(datetime.datetime.now()),
        payload = json.dumps({
            'metamodel_id': mm.id
        })
    )

@register_run_procedure(REQUEST_TYPE)
def execute_deterministic_single_mm_run(
    request: DeterministicSingleMMRunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    run_config = json.loads(request.payload)

    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    for mm in proj.metamodels:
        if mm.id == mm_id:
            break
    else:
        raise KeyError(f'Metamodel {mm_id} not found for project {proj.id} - available values are {[x.id for x in proj.metamodels]}.')

    n_steps = 3
    step = 0
    progress_callback(step, n_steps, f'Setting model variables.')

    mm.sync_model_with_changed_variables_deterministic()

    if check_cancel_status():
        raise InterruptedError(f'Process {run_id} has been cancelled.')

    step += 1
    progress_callback(step, n_steps, f'Running model.')

    mm.model.run()

    if check_cancel_status():
        raise InterruptedError(f'Process {run_id} has been cancelled.')

    step += 1
    progress_callback(step, n_steps, f'Running finance.')

    mm.finance.run()


    if check_cancel_status():
        raise InterruptedError(f'Process {run_id} has been cancelled.')

    step += 1
    progress_callback(step, n_steps, f'Saving results.')

    project_provider.upsert_component(proj)
    result_provider.upsert_result('deterministic_grid', mm.model.grid, mm.model.get_grid_result())
    result_provider.upsert_result('deterministic_generation', mm.model.generation, mm.model.get_generation_result())
    result_provider.upsert_result('deterministic_consumption_storage', mm.model.consumption_storage, mm.model.get_consumption_storage_result())

    return 'ok'
