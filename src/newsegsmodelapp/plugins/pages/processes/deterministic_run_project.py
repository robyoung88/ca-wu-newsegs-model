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

    return 'ok'
