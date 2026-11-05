"""The optimisation of a single metamodel.
"""
from dataclasses import dataclass
import datetime
import json
import time
from typing import Callable, cast

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.plugins.models.aaa_default.processes.output.optim_feedback import is_improvement
from newsegsmodelapp.registers import RunRequest, register_run_procedure, register_run_request
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity import optim
from newsegsmodelframework.util import naming


REQUEST_TYPE = 'optim_run_metamodel'

NO_VARIABLES_MESSAGE = 'Optimisation not run - no variables selected'

@dataclass
class OptimRunMetamodelRunRequest(RunRequest):
    """Request to optimise a metamodel.
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
    """Run the optimisation of one metamodel, in a worker.

    Varies the variables selected for optimisation within their bounds, using the method and statistic of the
    metamodel's `optim_config`. Raises `InvalidOptimBoundsError`, naming the variables, if any selected variable
    has bounds that cannot be used, so that nothing is run. Raises `ValueError` if no metamodel is named in the
    request and `KeyError` if it is not in the project.

    Saves an `optimisation_result` (see `optimisation_result`) for the feedback shown afterwards: whether the
    optimisation ran and succeeded, the statistic before and after, and how each variable changed. On success, the
    optimised copy of the metamodel is added to the project, named "<name> - Opt" (made unique), and focussed, if
    it improves on the statistic; otherwise the project and its focus are left as they were.

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

    selected = {
        varid: var for varid, var in mm.variables.items()
        if var.optim_possible and var.optim_selectable and var.optim_selected
    }
    if len(selected) == 0:
        result_provider.upsert_result(
            'optimisation_result', proj.table_config,
            {'status': 'not_run', 'success': False, 'message': NO_VARIABLES_MESSAGE},
            request = request,
        )
        return NO_VARIABLES_MESSAGE

    # Run with every selected variable or none, so that the optimisation is of the selection the user made
    optim.check_optim_bounds(list(selected.values()))

    optim_vars = {}
    for varid, var in selected.items():
        lower, upper = var.get_optim_bounds()
        optim_vars[varid] = optim.OptimVariable(varid, lower = lower, upper = upper) # pyright: ignore[reportArgumentType]

    if check_cancel_status():
        raise InterruptedError(f'Optimisation process {run_id} has been cancelled.')

    stat = mm.optim_config.statistic
    method = mm.optim_config.method

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

    # The statistic before optimisation, at the parameters of the configuration
    progress_callback(0, 1, 'Optimisation: evaluating the configuration')
    start_value = optim.evaluate_statistic(mm_copy, stat)

    opt = optim.run_optimisation(
        mm_copy,
        vars,
        target = stat,
        method = method,
        progress = lambda x, y: progress_callback(x,y, 'Optimisation underway'),
        cancel_status = check_cancel_status,
    )
    improved = bool(opt.success) and is_improvement(
        start_value,
        optim.statistic_from_objective(stat, float(opt.fun)), # pyright: ignore[reportArgumentType]
        optim.statistic_is_maximised(stat), # pyright: ignore[reportArgumentType]
    )
    if improved:
        mm_copy.name = naming.unique_name(mm.name + ' - Opt', (x.name for x in proj.metamodels))
        proj.metamodels.append(mm_copy) # pyright: ignore[reportAttributeAccessIssue]
        for k in vars:
            varid = k.varid
            proj.add_variable(mm_copy.variables[varid])
        # The optimised configuration is focussed, so that the user sees it; the page reloads the
        # project when the optimisation completes
        proj.set_focussed_metamodel(mm_copy.id)
        project_provider.upsert_component(proj)

    new_parameters = {k.varid: mm_copy.variables[k.varid].parameters for k in vars}

    rval = optimisation_result(
        mm, mm_copy if improved else None, vars, stat, start_value, opt, original_parameters, new_parameters
    )

    result_provider.upsert_result('optimisation_result', proj.table_config, rval, request = request)
    db_staleness.record_process_run(mm_id, 'optim', started_ns)
    if isinstance(project_provider, FromDatabaseNewsegsProjectProvider):
        project_provider.delete_orphan_variables()

    return 'ok'

def optimisation_result(
    mm: NewsegsMetaModel,
    mm_copy: NewsegsMetaModel | None,
    variables: list[optim.OptimVariable],
    stat: str,
    start_value: float,
    opt,
    original_parameters: dict,
    new_parameters: dict,
) -> dict:
    """The result of an optimisation, saved as `optimisation_result` for the feedback shown after it.

    Args:
        mm: The metamodel optimised.
        mm_copy: The optimised copy of the metamodel added to the project, or None if none was added.
        variables: The variables varied.
        stat: The statistic optimised.
        start_value: The statistic before optimisation.
        opt: The scipy result of the optimisation.
        original_parameters: The parameters of each variable before optimisation, by varid.
        new_parameters: The parameters of each variable after optimisation, by varid.

    Returns:
        A dictionary of:
            status: `success` or `failure` (`not_run` is saved when no variables are selected).
            success: Whether the optimisation succeeded.
            statistic: The statistic optimised.
            maximised: Whether the statistic is maximised, rather than minimised.
            start_value: The statistic before optimisation.
            final_value: The best value of the statistic found, with its natural sign.
            variables: For each variable, its `varid`, `label`, value `before` and `after` (of the parameter
                varied), and its `lower` and `upper` bounds.
            metamodel_name: Name of the metamodel optimised.
            new_metamodel_id, new_metamodel_name: The optimised copy added to the project; None if none was
                added, on failure or when the optimisation did not improve on the statistic.
            message: The message of the optimiser.
            opt, original_parameters, new_parameters, varids: The details, for diagnostics.
    """
    success = bool(opt.success)
    return {
        'status': 'success' if success else 'failure',
        'success': success,
        'statistic': stat,
        'maximised': optim.statistic_is_maximised(stat), # pyright: ignore[reportArgumentType]
        'start_value': float(start_value),
        'final_value': float(optim.statistic_from_objective(stat, float(opt.fun))), # pyright: ignore[reportArgumentType]
        'variables': [
            {
                'varid': v.varid,
                'label': mm.variables[v.varid].label,
                'before': float(original_parameters[v.varid][v.param_index]),
                'after': float(new_parameters[v.varid][v.param_index]),
                'lower': float(v.lower),
                'upper': float(v.upper),
            }
            for v in variables
        ],
        'metamodel_name': mm.name,
        'new_metamodel_id': mm_copy.id if mm_copy is not None else None,
        'new_metamodel_name': mm_copy.name if mm_copy is not None else None,
        'message': str(opt.message),
        'opt': opt,
        'original_parameters': original_parameters,
        'new_parameters': new_parameters,
        'varids': [v.varid for v in variables],
    }
    