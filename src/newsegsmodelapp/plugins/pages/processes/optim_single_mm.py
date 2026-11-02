"""Optim single mm module.

TODO: Describe the purpose of the module.
"""
from dataclasses import dataclass
import datetime
import json
import time
from typing import Callable, cast

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import optim


REQUEST_TYPE = 'optim_run_metamodel'

@dataclass
class OptimRunMetamodelRunRequest(RunRequest):
    """Optim Run Metamodel Run Request.

    TODO: Add a description.
    """
    request_type: str = REQUEST_TYPE

@register_run_request(REQUEST_TYPE)
def _(project_id: str, project_provider: NewsegsProjectProviderInterface, config: dict | None = None):
    mm_id = project_provider.get_focussed_metamodel_id(project_id)
    config = config.copy() if config else {}
    config.update({'metamodel_id': mm_id})
    return OptimRunMetamodelRunRequest(
        project_id = project_id,
        request_label = 'Optimisation run - ' + str(datetime.datetime.now()),
        payload = json.dumps(config)
    )

@register_run_procedure(REQUEST_TYPE)
def execute_optim_single_mm_run(
    request: OptimRunMetamodelRunRequest,
    project_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    run_id: int,
    progress_callback: Callable[[float, float, str], None],
    check_cancel_status: Callable[[], bool],
) -> str:
    """Execute optim single mm run.

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
    run_config = json.loads(request.payload)
    mm_id = run_config.get('metamodel_id')

    if not mm_id:
        raise ValueError('Metamodel ID not provided for single run.')
    for mm in proj.metamodels:
        if mm.id == mm_id:
            break
    else:
        raise KeyError(f'Metamodel {mm_id} not found for project {proj.id} - available values are {[x.id for x in proj.metamodels]}.')

    # TODO: This needs replacing with a dedicated configuration one day.
    if hasattr(proj.dsa_config, 'optim_config'):
        raw_config = proj.dsa_config.optim_config
    else:
        raw_config = {}
    bounds_config = raw_config.get('bounds', {})

    optim_vars = {}
    for varid, var in mm.variables.items():
        if var.optim_possible and var.optim_selectable and var.optim_selected:
            var_bounds = bounds_config.get(varid, {})
            lower = var_bounds.get('lower', 0)
            upper = var_bounds.get('upper', 10000)
            if lower is None or upper is None:
                continue
            if not lower < upper:
                continue
            optim_vars[varid] = optim.OptimVariable(varid, lower = lower, upper = upper) # pyright: ignore[reportArgumentType]

    if len(optim_vars) == 0:
        return 'Optimisation not run - no variables selected with valid bounds'

    if check_cancel_status():
        raise InterruptedError(f'Optimisation process {run_id} has been cancelled.')

    stat = run_config.get('statistic', 'net_present_value_discounted')
    method = run_config.get('optim-method')

    vars = [x for x in optim_vars.values()]

    # Upsert now just in case modifications go wrong.
    #proj.table_config.revision += 1
    #project_provider.upsert_component(proj)

    original_parameters = {k.varid:mm.variables[k.varid].parameters for k in vars}

    mm_copy = cast(NewsegsMetaModel, project_provider.metamodel_provider.duplicate_component(mm_id))
    mm_copy.reattach_variables(proj)
    for k in vars:
        varid = k.varid
        var = project_provider.variable_provider.duplicate_variable(mm_copy.variables[varid].id)
        mm_copy.variables[varid] = var

    if check_cancel_status():
        raise InterruptedError(f'Optimisation process {run_id} has been cancelled.')
    
    opt = optim.run_optimisation(
        mm_copy,
        vars,
        target = stat,
        method = method,
        progress = lambda x, y: progress_callback(x,y, 'Optimisation underway'),
        cancel_status = check_cancel_status,
    )
    if opt.success:
        mm_copy.name = mm.name + ' - Opt'
        proj.metamodels.append(mm_copy) # pyright: ignore[reportAttributeAccessIssue]
        for k in vars:
            varid = k.varid
            proj.add_variable(mm_copy.variables[varid])
        project_provider.upsert_component(proj)

    new_parameters = {k.varid: mm_copy.variables[k.varid].parameters for k in vars}

    rval = {
        'success': opt.success,
        'opt': opt,
        'original_parameters': original_parameters,
        'new_parameters': new_parameters,
        'varids': [k.varid for k in vars]
    }
    
    result_provider.upsert_result('optimisation_result', proj.table_config, rval, request = request)
    db_staleness.record_process_run(mm_id, 'optim', started_ns)
    if isinstance(project_provider, FromDatabaseNewsegsProjectProvider):
        project_provider.delete_orphan_variables()

    return 'ok'
    