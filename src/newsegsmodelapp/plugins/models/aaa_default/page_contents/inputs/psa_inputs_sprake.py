"""Register input container and input header container content creators for psa supersection"""
import logging
logger = logging.getLogger(__name__)

import copy
import json
import time
from typing import Any, Optional, cast

import dash
from dash.exceptions import PreventUpdate
from dash import dcc, html, no_update
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.variable_identification import VariableInstanceComponentID, VariableInstanceParameterComponentID
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel, make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent
from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.components.composite_input_components import generic_create_psa_input_container_contents
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
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

    # Don't need to invalidate metamodels, as PSA will run anyway,
    # but do need to invalidate at project level
    # TODO: Invalidate only PSA outputs
    # Currently, we have to invalidate all outputs even though these
    # settings only apply to the PSA.
    provider._component_provider.increment_revision(lproj.table_config.id)
    
    provider.increment_revision(lproj.id)
    
    return return_dict
