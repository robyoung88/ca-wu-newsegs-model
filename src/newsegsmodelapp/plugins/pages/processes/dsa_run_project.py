"""The deterministic sensitivity analysis (DSA) of every metamodel of a project: the whole-project DSA.
"""
import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass
import datetime
import json
import time
from typing import Callable, cast

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.plugins.pages.processes.common_deterministic import DETERMINISTIC_STEPS, deterministic_run_metamodel
from newsegsmodelapp.plugins.pages.processes.progress_messages import runs_progress_message
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import dsa

REQUEST_TYPE = 'dsa_run_project'

@dataclass
class DSARunProjectRunRequest(RunRequest):
    """Request to run a DSA of every metamodel of a project.
    """
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def _(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict | None = None):
    return DSARunProjectRunRequest(
        project_id = project_id,
        request_label = 'DSA run for whole project - ' + str(datetime.datetime.now()),
        payload = json.dumps({})
    )

def _synchronise_and_save_selection(proj, project_provider: FromDatabaseNewsegsProjectProvider) -> list[str]:
    """Synchronise the DSA selection across the metamodels, and save the variables that changed.

    Returns:
        The ids of the metamodels holding a changed variable.
    """
    variables = {id(v): v for mm in proj.metamodels for v in mm.variables.values()}
    before = {k: v.dsa_selected for k, v in variables.items()}
    dsa.synchronise_dsa_selection(proj.metamodels)
    changed = [v for k, v in variables.items() if v.dsa_selected != before[k]]
    if not changed:
        return []

    for var in changed:
        project_provider.variable_provider.upsert_variable(var)
    changed_ids = {id(v) for v in changed}
    changed_mm_ids = [
        mm.id for mm in proj.metamodels
        if any(id(v) in changed_ids for v in mm.variables.values())
    ]
    project_provider._component_provider.increment_revision(
        [proj.table_config.id] + [mm.table_config.id for mm in proj.metamodels if mm.id in changed_mm_ids]
    )
    project_provider.invalidate_cache_for_component(proj.id)
    db_staleness.mark_inputs_changed(changed_mm_ids, 'dsa')
    return changed_mm_ids

@register_run_procedure(REQUEST_TYPE)
def execute_dsa_project_run(
    request: DSARunProjectRunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    """Run a deterministic sensitivity analysis of every metamodel of a project, in a worker.

    The DSA selection of variables common to the metamodels is first synchronised (and saved), then every
    metamodel is evaluated with each selected variable at its lower and upper bounds in turn, each metamodel using
    its own bounds. The results are attached to the project table configuration, and the individual results of
    each metamodel to its own, so that the single configuration views show them.

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
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    proj = project_provider.get_project(request.project_id)
    metamodels = list(proj.metamodels)
    if not metamodels:
        raise ValueError(f'Project {proj.id} has no metamodels for a DSA.')

    progress_callback(0, 1, 'DSA: Synchronising the variable selection')
    _synchronise_and_save_selection(proj, provider)
    # The inputs are read now: changes made after this keep the DSA stale
    started_ns = time.time_ns()

    n_mm = len(metamodels)
    n_steps = n_mm * DETERMINISTIC_STEPS
    def deterministic_progress_callback(step, total, message):
        progress_callback(step, n_steps, 'DSA: Reference run - ' + message)

    for i, mm in enumerate(metamodels):
        deterministic_run_metamodel(
            mm, proj, request, project_provider, result_provider, run_id,
            deterministic_progress_callback, check_cancel_status,
            start_step = i * DETERMINISTIC_STEPS,
            total_steps = n_steps,
            sequence_number = i + 1,
            run_started_ns = started_ns,
        )

    t0 = time.time_ns()

    def internal_progress_callback(step, total):
        if check_cancel_status():
            raise InterruptedError(f'DSA process {run_id} has been cancelled.')

        tot_secs = (time.time_ns() - t0) * 1e-9
        progress_callback(step, total, runs_progress_message('DSA (all configurations)', step, total, tot_secs))

    dsa_results_frame = dsa.run_dsa_multiple(
        metamodels,
        progress = internal_progress_callback,
        cancel_status = check_cancel_status,
        precomputed_deterministic = True,
        synchronise = False,
    )

    # The deterministic runs may have incremented the revisions held in the database
    lproj = provider.get_lightweight_project(proj.id)
    revisions = {lmm.id: lmm.table_config.revision for lmm in lproj.metamodels}

    result_provider.upsert_result(
        'dsa_project',
        proj.table_config,
        dsa_results_frame,
        request = request,
        revision = lproj.table_config.revision,
    )
    for mm in metamodels:
        single = dsa.dsa_multiple_for_metamodel(dsa_results_frame, mm.id)
        if len(single) < 2:
            # Nothing varied in this metamodel; leave its previous individual results
            continue
        result_provider.upsert_result(
            'dsa_single_metamodel',
            mm.table_config,
            single.set_index(['variable', 'bound']),
            request = request,
            revision = revisions.get(mm.id),
        )
    db_staleness.record_process_run([mm.id for mm in metamodels], 'dsa', started_ns)

    return 'ok'
