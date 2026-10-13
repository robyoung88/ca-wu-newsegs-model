from dataclasses import dataclass
import datetime
from typing import Callable, cast

import sqlalchemy as sa

from newsegsmodelapp.plugins.pages.processes.common_deterministic import deterministic_run_metamodel
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface

REQUEST_TYPE = 'deterministic_run_project'

@dataclass
class DeterministicRunProjectRunRequest(RunRequest):
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def request_deterministic_run_project(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict|None = None):
    return DeterministicRunProjectRunRequest(
        project_id = project_id,
        request_label = 'Deterministic project run - ' + str(datetime.datetime.now())
    )

@register_run_procedure(REQUEST_TYPE)
def execute_deterministic_run_project(
    request: DeterministicRunProjectRunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    metamodels = proj.metamodels

    n_mm = len(metamodels)

    n_steps = n_mm * 4 - 1
    step = 0

    # Ensure that the output tables get updated
    # proj.table_config.revision += 1

    for i, mm in enumerate(metamodels):
        deterministic_run_metamodel(
            mm,
            proj,
            request,
            project_provider,
            result_provider,
            run_id,
            progress_callback,
            check_cancel_status,
            start_step = i*3,
            total_steps = n_steps,
            sequence_number = i + 1
        )

        # progress_callback(step, n_steps, f'Setting model variables - metamodel {i+1} of {n_mm}')
        # step += 1

        # if check_cancel_status():
        #     raise InterruptedError(f'Process {run_id} has been cancelled.')

        # revisions = {
        #     'grid': mm.model.grid.revision,
        #     'generation': mm.model.generation.revision,
        #     'consumption_storage': mm.model.consumption_storage.revision
        # }
    

        # mm.sync_model_with_changed_variables_deterministic()

        # progress_callback(step, n_steps, f'Running model - metamodel {i+1} of {n_mm}')
        # step += 1

        # mm.model.run()
        # mm.model.table_config.revision += 1
        # project_provider.upsert_component(mm.model.table_config)

        # if check_cancel_status():
        #     raise InterruptedError(f'Process {run_id} has been cancelled.')

        # progress_callback(step, n_steps, f'Running finance - metamodel {i+1} of {n_mm}')
        # step += 1

        # mm.finance.run()
        # mm.finance.table_config.revision += 1
        # project_provider.upsert_component(mm.finance.table_config)

        # if check_cancel_status():
        #     raise InterruptedError(f'Process {run_id} has been cancelled.')

        # progress_callback(step, n_steps, f'Saving results - metamodel {i+1} of {n_mm}')

        # mm.model.grid.revision = revisions['grid']
        # mm.model.generation.revision = revisions['generation']
        # mm.model.consumption_storage.revision = revisions['consumption_storage']

        # result_provider.upsert_result('deterministic_grid', mm.model.grid, mm.model.get_grid_result(), request = request)
        # result_provider.upsert_result('deterministic_generation', mm.model.generation, mm.model.get_generation_result(), request = request)
        # result_provider.upsert_result('deterministic_consumption_storage', mm.model.consumption_storage, mm.model.get_consumption_storage_result(), request = request)

        # # Touch the project to update modified_order and invalidate cache
        # project_provider.touch_project(request.project_id)

    return 'ok'
