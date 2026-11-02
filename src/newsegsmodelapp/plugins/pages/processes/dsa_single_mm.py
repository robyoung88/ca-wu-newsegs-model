"""Dsa single mm module.

TODO: Describe the purpose of the module.
"""
import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass
import datetime
import json
import time
from typing import Callable

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.plugins.pages.processes.common_deterministic import deterministic_run_metamodel
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework import newsegssensitivity
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

REQUEST_TYPE = 'dsa_run_metamodel'

@dataclass
class DSARunMetamodelRunRequest(RunRequest):
    """DSA Run Metamodel Run Request.

    TODO: Add a description.
    """
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def _(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict | None = None):
    mm_id = project_provider.get_focussed_metamodel_id(project_id)
    return DSARunMetamodelRunRequest(
        project_id = project_id,
        request_label = 'DSA run for single metamodel - ' + str(datetime.datetime.now()),
        payload = json.dumps({
            'metamodel_id': mm_id
        })
    )

@register_run_procedure(REQUEST_TYPE)
def execute_dsa_single_mm_run(
    request: DSARunMetamodelRunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    """Execute dsa single mm run.

    TODO: Add a description.

    Args:
        request: TODO.
        project_provider: TODO.
        result_provider: TODO.
        run_id: TODO.
        progress_callback: TODO.
        check_cancel_status: TODO.

    Returns:
        TODO.
    """
    started_ns = time.time_ns()
    proj = project_provider.get_project(request.project_id)

    # TODO: get dsa configuration from project dsa config
    
    run_config = json.loads(request.payload)

    mm_id = run_config.get('metamodel_id')
    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    for mm in proj.metamodels:
        if mm.id == mm_id:
            break
    else:
        raise KeyError(f'Metamodel {mm_id} not found for project {proj.id} - available values are {[x.id for x in proj.metamodels]}.')

    # Ensure that the output tables get updated
    #proj.table_config.revision += 1
    #mm.table_config.revision += 1

    t0 = time.time_ns()

    def internal_progress_callback(step, total):
        if check_cancel_status():
            raise InterruptedError(f'DSA process {run_id} has been cancelled.')

        t1 = time.time_ns()
        tot_secs = (t1 - t0) * 1e-9
        if step > 0:
            per_iter = tot_secs / step
            msg = f'DSA: Run {step} of {total}, {per_iter:.1f} sec/run. Elapsed time: {tot_secs:.0f} seconds.'
        else:
            msg = f'DSA: Run {step} of {total}. Elapsed time: {tot_secs:.0f} seconds.'

        progress_callback(step, total, msg)

    def deterministic_progress_callback(step, total, message):
        msg = 'DSA: Reference run'
        progress_callback(0, 1, msg)

    # By running the deterministic through this process, the module revisions will
    # be correctly modified
    logger.debug(
        'DSA run: - Pre-Deterministic. Metamodel modified: %s',
        mm.modified
    )
    mm = deterministic_run_metamodel(
        mm, proj, request, project_provider, result_provider, run_id,
        deterministic_progress_callback, check_cancel_status,
        run_started_ns = started_ns,
    )
    logger.debug(
        'DSA run: - Post-Deterministic. Metamodel modified: %s',
        mm.modified
    )

    dsa_results_frame = newsegssensitivity.run_dsa(
        mm, 
        progress = internal_progress_callback, 
        cancel_status = check_cancel_status,
        precomputed_deterministic = True
    )

    # Connect this result to the metamodel table config, rather than the project dsa config
    #project_provider.upsert_component(proj)
    result_provider.upsert_result(
        'dsa_single_metamodel', 
        mm.table_config, 
        dsa_results_frame, 
        request = request
    )
    db_staleness.record_process_run(mm.id, 'dsa', started_ns)

    return 'ok'
