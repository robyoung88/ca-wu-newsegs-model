import logging
logger = logging.getLogger(__name__)

from typing import Callable

from newsegsmodelapp.registers import RunRequest
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

def deterministic_run_metamodel(
    mm: NewsegsMetaModel,
    proj: NewsegsProject,
    request: RunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
    start_step: int = 0,
    total_steps: int = 3,
    sequence_number: int = 1
):
    step = start_step
    progress_callback(step, total_steps, f'Setting model variables - config {sequence_number}')

    revisions = {
        'grid': mm.model.grid.revision,
        'generation': mm.model.generation.revision,
        'consumption_storage': mm.model.consumption_storage.revision
    }

    mm.sync_model_with_changed_variables_deterministic()

    if check_cancel_status():
        raise InterruptedError(f'Process {run_id} has been cancelled.')

    # Each result is dependent on the previous module.
    # We assume that results available for the current revision of a module
    # will be valid if the previous module has results.
    try_get_grid = mm.model.grid.revision == revisions['grid']
    try_get_generation = try_get_grid and mm.model.generation.revision == revisions['generation']
    try_get_cs = try_get_generation and mm.model.consumption_storage.revision == revisions['consumption_storage']

    model_run_from = 'start'
    if try_get_grid:
        grid_res, grid_rev = result_provider.get_result(
            'deterministic_grid', mm.model.grid,
            allow_stale = False
        )
        if grid_res is None:
            try_get_generation = False
            try_get_cs = False
        else:
            mm.model._grid_result = grid_res
            model_run_from = 'grid'
    if try_get_generation:
        generation_res, generation_rev = result_provider.get_result(
            'deterministic_generation', mm.model.generation,
            allow_stale = False
        )
        if generation_res is None:
            try_get_cs = False
        else:
            mm.model._generation_result = generation_res
            model_run_from = 'generation'
    if try_get_cs:
        cs_res, cs_rev = result_provider.get_result(
            'deterministic_consumption_storage', mm.model.consumption_storage,
            allow_stale = False
        )
        if cs_res is not None:
            mm.model._cs_result = cs_res
            model_run_from = 'complete'   

    table_increment = False
    """Increment the metamodel and project tables"""
    step += 1
    if model_run_from == 'complete':
        progress_callback(step, total_steps, f'Model already run - config {sequence_number}')
    else:
        progress_callback(step, total_steps, f'Running model - config {sequence_number}')
        mm.model.run(run_from = model_run_from)
        # There should be no need to increment the table config;
        # If it was necessary this should have happened in the sync_model_with_changed_variables_deterministic
        # However, if there are simply no results and the model is unchanged, then rightly nothing should be
        # incremented.
        if mm.model.chain_modified:
            table_increment = True
            project_provider.metamodel_provider._em_provider.upsert_component(mm.model)

    if check_cancel_status():
        raise InterruptedError(f'Process {run_id} has been cancelled.')

    step += 1
    if model_run_from == 'complete':
        # Nothing to do for finance, skip
        progress_callback(step, total_steps, f'Finance already run - config {sequence_number}')
        pass
    else:
        progress_callback(step, total_steps, f'Running finance - config {sequence_number}')
        mm.finance.run()
        # There should be no need to increment the table config;
        # If it was necessary this should have happened in the sync_model_with_changed_variables_deterministic
        # However, if there are simply no results and the model is unchanged, then rightly nothing should be
        # incremented.
        if mm.finance.chain_modified:
            table_increment = True
            project_provider.metamodel_provider._fm_provider.upsert_component(mm.finance)

        # Invalidate downstream tables
        if table_increment:
            project_provider._component_provider.increment_revision([
                proj.table_config.id,
                mm.table_config.id,
            ])
            # Invalidate cache on project (only the table_config has been modified, the project itself is unchanged)
            project_provider.invalidate_cache_for_component(proj.id)

    if check_cancel_status():
        raise InterruptedError(f'Deterministic single configuration process {run_id} has been cancelled.')

    step += 1
    progress_callback(step, total_steps, f'Saving results - config {sequence_number}')

    if model_run_from == 'start':
        logger.info(
            'Upserting deterministic grid result for Metamodel ID = %s; and Grid ID = %s; '
            'for Request ID = %d; Run ID = %d; Triggering Request ID = %d;',
            mm.id, mm.model.grid.id,
            request.request_id, request.run_id, request.trigger_request_id
        )
        result_provider.upsert_result(
            'deterministic_grid', mm.model.grid, 
            mm.model.get_grid_result(), request = request
        )
    else:
        logger.info(
            'Duplicating deterministic grid result for Metamodel ID = %s; and Grid ID = %s; '
            'for Request ID = %d; Run ID = %d, Triggering Request ID = %d;',
            mm.id, mm.model.grid.id,
            request.request_id, request.run_id, request.trigger_request_id
        )
        result_provider.duplicate_result(
            'deterministic_grid', mm.model.grid, request,
        )

    if model_run_from in ('start', 'grid'):
        logger.info(
            'Upserting deterministic generation result for Metamodel ID = %s; and Generation ID = %s; '
            'for Request ID = %d; Run ID = %d, Triggering Request ID = %d;',
            mm.id, mm.model.generation.id,
            request.request_id, request.run_id, request.trigger_request_id
        )
        result_provider.upsert_result(
            'deterministic_generation', mm.model.generation,
            mm.model.get_generation_result(), request = request
        )
    else:
        logger.info(
            'Duplicating deterministic generation result for Metamodel ID = %s; and Generation ID = %s; '
            'for Request ID = %d; Run ID = %d, Triggering Request ID = %d;',
            mm.id, mm.model.generation.id,
            request.request_id, request.run_id, request.trigger_request_id
        )
        result_provider.duplicate_result(
            'deterministic_generation', mm.model.generation, request
        )

    if model_run_from in ('start', 'grid', 'generation'):
        logger.info(
            'Upserting deterministic consumption storage result for Metamodel ID = %s; and Consumption_Storage ID = %s; '
            'for Request ID = %d; Run ID = %d, Triggering Request ID = %d;',
            mm.id, mm.model.consumption_storage.id,
            request.request_id, request.run_id, request.trigger_request_id
        )
        result_provider.upsert_result(
            'deterministic_consumption_storage', mm.model.consumption_storage, 
            mm.model.get_consumption_storage_result(), request = request
        )
    else:
        logger.info(
            'Duplicating deterministic consumption storage result for Metamodel ID = %s; and Consumption_Storage ID = %s; '
            'for Request ID = %d; Run ID = %d, Triggering Request ID = %d;',
            mm.id, mm.model.consumption_storage.id,
            request.request_id, request.run_id, request.trigger_request_id
        )
        result_provider.duplicate_result(
            'deterministic_consumption_storage', mm.model.consumption_storage, request
        )
