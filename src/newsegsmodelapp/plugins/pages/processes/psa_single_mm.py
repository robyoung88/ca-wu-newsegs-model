import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass
import datetime
import time
import json
from typing import Callable

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.plugins.pages.processes.common_deterministic import deterministic_run_metamodel
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import psa


REQUEST_TYPE = 'psa_run_metamodel'

@dataclass
class PSARunMetamodelRunRequest(RunRequest):
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def _(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict | None = None):
    mm_id = project_provider.get_focussed_metamodel_id(project_id)
    return PSARunMetamodelRunRequest(
        project_id = project_id,
        request_label = 'PSA run for single metamodel - ' + str(datetime.datetime.now()),
        payload = json.dumps({
            'metamodel_id': mm_id
        })
    )

@register_run_procedure(REQUEST_TYPE)
def execute_psa_single_mm_run(
    request: PSARunMetamodelRunRequest,
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

    # Ensure that the output tables get updated
    #proj.table_config.revision += 1
    #mm.table_config.revision += 1

    t0 = time.time_ns()

    def internal_progress_callback(step, total):
        if check_cancel_status():
            raise InterruptedError(f'PSA process {run_id} has been cancelled.')

        t1 = time.time_ns()
        tot_secs = (t1 - t0) * 1e-9
        if step > 0:
            per_iter = tot_secs / step
            msg = f'PSA: Run {step} of {total}, {per_iter:.1f} sec/run. Elapsed time: {tot_secs:.0f} seconds.'
        else:
            msg = f'PSA: Run {step} of {total}. Elapsed time: {tot_secs:.0f} seconds.'

        progress_callback(step, total, msg)

    seed = proj.psa_config.seed
    seed = int(seed) if seed is not None and seed != '' else seed

    def deterministic_progress_callback(step, total, message):
        msg = 'PSA: Reference run'
        progress_callback(0, 1, msg)

    # By running the deterministic through this process, the module revisions will
    # be correctly modified
    logger.debug(
        'PSA run: - Pre-Deterministic. Metamodel modified: %s',
        mm.modified
    )
    mm = deterministic_run_metamodel(
        mm, proj, request, project_provider, result_provider, run_id,
        deterministic_progress_callback, check_cancel_status,
        run_started_ns = started_ns,
    )
    logger.debug(
        'PSA run: - Post-Deterministic. Metamodel modified: %s',
        mm.modified
    )

    psa_results = psa.run_psa(
        mm,
        samples = proj.psa_config.samples,
        return_draws = proj.psa_config.return_draws,
        seed = seed,
        progress = internal_progress_callback,
        cancel_status = check_cancel_status,
        precomputed_deterministic = True
    )

    # Connect this result to the metamodel table config, rather than the project dsa config
    #project_provider.upsert_component(proj)
    result_provider.upsert_result('psa_single_metamodel', mm.table_config, psa_results, request = request)
    db_staleness.record_process_run(mm.id, 'psa', started_ns)

    return 'ok'
