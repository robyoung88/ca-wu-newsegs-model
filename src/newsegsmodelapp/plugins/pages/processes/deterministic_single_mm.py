from dataclasses import dataclass
import datetime
import json
import time
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
    started_ns = time.time_ns()
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
        sequence_number = 1,
        run_started_ns = started_ns,
    )

    return 'ok'
