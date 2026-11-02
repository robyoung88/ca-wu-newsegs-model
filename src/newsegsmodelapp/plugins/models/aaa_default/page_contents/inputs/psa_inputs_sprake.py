"""Register input container and input header container content creators for psa supersection"""
import logging
logger = logging.getLogger(__name__)

import copy
import json
import time
from typing import Any, Optional, cast

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent
from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.components.composite_input_components import generic_create_psa_input_container_contents
from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.components import staleness
from newsegsmodelapp.registers import register_input_container_content_creator, register_input_handler, register_single_input_header_content_creator
from newsegsmodelapp.components.variable_dash_component import vdc as var_dc
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

MODEL_TYPE = 'sprake'
@register_input_container_content_creator('psa', None, MODEL_TYPE)
def _(
    proj_id: str,
    proj_provider: NewsegsProjectProviderInterface,
) -> list[dash.development.base_component.Component]:
    provider = cast(FromDatabaseNewsegsProjectProvider, proj_provider)
    logger.debug('Getting lightweight project - Creating PSA Input Container contents')
    lproj = provider.get_lightweight_project(proj_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]
    return generic_create_psa_input_container_contents(
        lmm, provider.variable_provider
    )

@register_single_input_header_content_creator('psa', None, MODEL_TYPE)
def _(
    varid: str,
    var: variable.Variable | FullLightweightVariable,
) -> list[dash.development.base_component.Component]:
    if not var or not isinstance(var, (variable.Variable, FullLightweightVariable)):
        return []
    return var_dc.create_psa_header(var) # pyright: ignore[reportArgumentType]

@register_input_container_content_creator('psa', 'psa-settings', MODEL_TYPE)
def _(
    proj_id: str,
    proj_provider: NewsegsProjectProviderInterface,
) -> list[dash.development.base_component.Component]:
    provider = cast(FromDatabaseNewsegsProjectProvider, proj_provider)
    logger.debug('Getting lightweight project - Creating PSA Settings Input Container contents')
    lproj = provider.get_lightweight_project(proj_id)
    psa_config = provider._component_provider.get_component(lproj.psa_config.id)
    if not psa_config:
        return []
    return [
        n_samples_input(psa_config),
        random_seed_input(psa_config),
        return_draws_input(psa_config)
    ]
    

def n_samples_input(
    psa_config: PSAComponent,
    id = VariableInstanceParameterComponentID(
        'single-input-config', 'psa-settings',
        'psa', 'psa-settings',
        'samples', 0
    )):
    """Create the input of the number of samples of the PSA.

    Args:
        psa_config: The PSA configuration of the project.
        id: Identification of the component.

    Returns:
        The input.
    """
    overall_id = id

    header_id = copy.copy(id)
    header_id.type = 'single-input-header'
    header_id.purpose = 'header'

    trigger_id = copy.copy(id)
    trigger_id.type = 'input-group-config-update-trigger'
    trigger_id.purpose = 'trigger'

    return html.Div([
        html.H4('Number of samples:', id = header_id.as_dict()),
        dbc.InputGroup([
            dbc.InputGroupText('N'), # pyright: ignore[reportCallIssue]
            dbc.Input(
                overall_id.as_dict(),
                placeholder = 'N',
                value = psa_config.samples,
                min = 0,
                max = 10000,
                step = 1,
                debounce = True,
            ), # pyright: ignore[reportCallIssue]
            dcc.Store(id = trigger_id.as_dict(),)
        ]) # pyright: ignore[reportCallIssue]
        ],    
        className = 'input-settings'
    )

def random_seed_input(
    psa_config: PSAComponent,
    id = VariableInstanceParameterComponentID(
        'single-input-config', 'psa-settings',
        'psa', 'psa-settings',
        'seed', 0
)):
    """Create the input of the random seed of the PSA.

    Args:
        psa_config: The PSA configuration of the project.
        id: Identification of the component.

    Returns:
        The input.
    """
    overall_id = id

    header_id = copy.copy(id)
    header_id.type = 'single-input-header'
    header_id.purpose = 'header'

    trigger_id = copy.copy(id)
    trigger_id.type = 'input-group-config-update-trigger'
    trigger_id.purpose = 'trigger'

    return html.Div([
        html.H4('Random Seed:', id = header_id.as_dict()),
        dbc.InputGroup([
            dbc.InputGroupText('Seed'), # pyright: ignore[reportCallIssue]
            dbc.Input(
                overall_id.as_dict(),
                placeholder = 'N',
                value = psa_config.seed,
                min = 0,
                max = 10000,
                step = 1,
                debounce = True,
            ), # pyright: ignore[reportCallIssue]
            dcc.Store(id = trigger_id.as_dict(),)
        ]) # pyright: ignore[reportCallIssue]
        ],    
        className = 'input-settings'
    )

def return_draws_input(
    psa_config: PSAComponent,
    id = VariableInstanceParameterComponentID(
        'single-input-config', 'psa-settings',
        'psa', 'psa-settings',
        'return_draws', 0
)):
    """Create the input which chooses whether the PSA returns the draws made.

    Args:
        psa_config: The PSA configuration of the project.
        id: Identification of the component.

    Returns:
        The input.
    """
    overall_id = id

    header_id = copy.copy(id)
    header_id.type = 'single-input-header'
    header_id.purpose = 'header'

    trigger_id = copy.copy(id)
    trigger_id.type = 'input-group-config-update-trigger'
    trigger_id.purpose = 'trigger'

    return html.Div([
        html.H4('Keep drawn parameters:', id = header_id.as_dict()),
        daq.ToggleSwitch(
            id = overall_id.as_dict(),
            value = psa_config.return_draws,
            size = 36,
            className = 'input-toggle',
        ),
        dcc.Store(id = trigger_id.as_dict(),)
        ],    
        className = 'input-settings'
    )

@register_input_handler('psa-settings')
def handle_psa_settings(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
    new_val: Optional[Any] = None, # Include this so we can call from other parameter setting functions, not just dash callbacks
):
    """Input handler for a change to a setting of the PSA (number of samples, seed or return of draws).

    Updates the PSA configuration of the project.

    Args:
        triggered_id: The id of the component which triggered the callback.
        input_ids: The ids of the input components of the callback.
        header_ids: The ids of the header containers of the callback.
        trigger_ids: The ids of the trigger stores of the callback.
        calling_dict: Other keyword arguments of the calling callback.
        active_project_id: Id of the active project.
        project_provider: Provider of projects, metamodels and variables.
        return_dict: Dictionary of the outputs of the callback, to be updated and returned.
        new_val: The new value.

    Returns:
        The updated `return_dict`.
    """
    if new_val is None:
        new_val = callback_utils.get_triggered_value()
        if new_val is None and triggered_id['key'] != 'seed':
            new_val = 0

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Handling PSA settings change')
    lproj = provider.get_lightweight_project(active_project_id)
    psa_config = provider._component_provider.get_component(lproj.psa_config.id)

    now = time.time_ns()

    r0 = psa_config.revision
    modified = False
    match triggered_id['key']:
        case 'seed':
            if psa_config.seed != new_val:
                old_val = psa_config.seed
                psa_config.seed = new_val
        case 'samples':
            new_val = max(min(int(new_val), 10000), 10) 
            if psa_config.samples != int(new_val):
                old_val = psa_config.samples
                psa_config.samples = int(new_val)
        case 'return_draws':
            if psa_config.return_draws != new_val:
                old_val = psa_config.return_draws
                psa_config.return_draws = new_val 
        case _:
            logger.exception('No PSA setting handler for key: %s', triggered_id['key'])

    modified = psa_config.revision != r0
    if not modified:
        return return_dict

    logger.debug(
        'PSA setting changed - %s: %s -> %s',
        triggered_id["key"], old_val, new_val
    )

    # Feed back current parameters
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'psa-settings':
            return_dict['input_values'][idx] = new_val

     # Update triggers
    for idx, id in enumerate(trigger_ids):
        return_dict['trigger_data'][idx] = now

    # Sync configuration to store
    provider._component_provider.upsert_component(psa_config, project_id = active_project_id)
    
    # TODO: Invalidate only PSA outputs
    # Currently, we have to invalidate all outputs even though these
    # settings only apply to the PSA.
    provider._component_provider.increment_revision(lproj.table_config.id)
    
    provider.increment_revision(lproj.id)

    # PSA settings are held for the project, so apply to every configuration
    db_staleness.mark_inputs_changed([x.id for x in lproj.metamodels], 'psa')

    return return_dict

@register_input_handler('psa-active')
def handle_psa_active(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
    new_val: Optional[Any] = None, # Include this so we can call from other parameter setting functions, not just dash callbacks
) -> dict[str, Any]:
    """Input handler for a variable being selected or deselected for the PSA.

    Args:
        triggered_id: The id of the component which triggered the callback.
        input_ids: The ids of the input components of the callback.
        header_ids: The ids of the header containers of the callback.
        trigger_ids: The ids of the trigger stores of the callback.
        calling_dict: Other keyword arguments of the calling callback.
        active_project_id: Id of the active project.
        project_provider: Provider of projects, metamodels and variables.
        return_dict: Dictionary of the outputs of the callback, to be updated and returned.
        new_val: The new value.

    Returns:
        The updated `return_dict`.
    """
    if new_val is None:
        new_val = callback_utils.get_triggered_value()

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Handling PSA activation change')
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = cast(LightweightNewsegsMetaModel, lproj.metamodels[lproj.focussed_metamodel_index])

    varid =  make_varid(**triggered_id)
    var_uid = lmm.variables[varid]
    var = project_provider.variable_provider.get_variable(var_uid)
    
    if not var or new_val == var.psa_selected:
        return return_dict

    var.psa_selected = new_val

    now = time.time_ns()
    # Update triggers with a dictionary, not an integer
    trig_val = json.dumps({
        'message': 'psa_selection_status_modified',
        'time': now
    })
    for idx, id in enumerate(trigger_ids):
        match id['supersection']:
            case 'psa':
                return_dict['trigger_data'][idx] = trig_val

    # Sync variable
    project_provider.variable_provider.upsert_variable(var)

    # Sync the selection onto the independent instances of the variable in the other metamodels,
    # so that a whole-project PSA varies the same variables in every metamodel
    changed_mm_ids = list(staleness.metamodels_using_variable(lproj, var_uid))
    for other_lmm in lproj.metamodels:
        other_uid = other_lmm.variables.get(varid)
        if not other_uid or other_uid == var_uid:
            continue
        other_var = project_provider.variable_provider.get_variable(other_uid)
        if (
            not other_var
            or not (other_var.psa_possible and other_var.psa_selectable)
            or other_var.psa_selected == new_val
        ):
            continue
        other_var.psa_selected = new_val
        project_provider.variable_provider.upsert_variable(other_var)
        for mm_id in staleness.metamodels_using_variable(lproj, other_uid):
            if mm_id not in changed_mm_ids:
                changed_mm_ids.append(mm_id)

    # Don't need to invalidate metamodels, as PSA will run anyway,
    # but do need to invalidate at project level
    # TODO: Invalidate only PSA outputs
    # Currently, we have to invalidate all outputs even though these
    # settings only apply to the PSA.
    provider._component_provider.increment_revision(lproj.table_config.id)
    
    provider.increment_revision(lproj.id)

    db_staleness.mark_inputs_changed(changed_mm_ids, 'psa')

    return return_dict
