"""The deterministic run of every metamodel of a project.
"""
from dataclasses import dataclass
import datetime
import time
from typing import Callable, cast


from newsegsmodelapp.plugins.pages.processes.common_deterministic import DETERMINISTIC_STEPS, deterministic_run_metamodel
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface

REQUEST_TYPE = 'deterministic_run_project'

@dataclass
class DeterministicRunProjectRunRequest(RunRequest):
    """Request to run the NewSEGS Energy Model and finance model of every metamodel of a project.
    """
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def request_deterministic_run_project(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict|None = None):
    """Create the request for the deterministic run of every metamodel of a project.

    Args:
        project_id: Id of the project.
        project_provider: Provider of projects, metamodels and variables.
        config: The layout configuration of the page.

    Returns:
        The request.
    """
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
    """Run every metamodel of a project, in turn, in a worker.

    Reports progress by step, and stops if cancellation is requested.

    Args:
        request: The request being executed.
        project_provider: Provider of projects, metamodels and variables.
        result_provider: Provider of results.
        run_id: Id of the run.
        progress_callback: Function reporting progress: takes the progress, the total, and a message.
        check_cancel_status: Function returning whether cancellation of the run has been requested.

    Returns:
        The status message, `ok` on success.
    """
    started_ns = time.time_ns()
    proj = cast(NewsegsProject, project_provider.get_component(request.project_id))

    metamodels = proj.metamodels

    n_mm = len(metamodels)

    n_steps = n_mm * DETERMINISTIC_STEPS

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
            start_step = i * DETERMINISTIC_STEPS,
            total_steps = n_steps,
            sequence_number = i + 1,
            run_started_ns = started_ns,
        )

    return 'ok'
