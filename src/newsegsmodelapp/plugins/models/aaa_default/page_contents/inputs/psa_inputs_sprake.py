
"""Register input container and input header container content creators for psa supersection"""
import copy
import json
import time
from typing import Any, Optional

import dash
from dash.exceptions import PreventUpdate
from dash import dcc, html, no_update
import dash_bootstrap_components as dbc
import dash_daq as daq

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.variable_identification import VariableInstanceComponentID, VariableInstanceParameterComponentID
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel, make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
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
    return generic_create_psa_input_container_contents(
        get_focussed_metamodel(proj_id, proj_provider)
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
    
    proj = proj_provider.get_project(proj_id)
    if not proj:
        return []
    return [
        n_samples_input(proj),
        random_seed_input(proj),
        return_draws_input(proj)
    ]
    

def n_samples_input(
        proj: NewsegsProject,
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
                value = proj.psa_config.samples,
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
    proj: NewsegsProject,
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
                value = proj.psa_config.seed,
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
    proj: NewsegsProject,
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
            value = proj.psa_config.return_draws,
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

    proj = project_provider.get_project(active_project_id)

    now = time.time_ns()

    modified = False
    match triggered_id['key']:
        case 'seed':
            if proj.psa_config.seed != new_val:
                proj.psa_config.seed = new_val
                proj.psa_config.revision += 1
                modified = True
        case 'samples':
            new_val = max(min(int(new_val), 10000), 10) # pyright: ignore[reportArgumentType]
            if proj.psa_config.samples != int(new_val):
                proj.psa_config.samples = int(new_val)
                proj.psa_config.revision += 1
                modified = True
        case 'return_draws':
            if proj.psa_config.return_draws != new_val:
                proj.psa_config.return_draws = new_val # pyright: ignore[reportAttributeAccessIssue]
                proj.psa_config.revision += 1
                modified = True
        case _:
            print (f'No handler for key {triggered_id["key"]}')


    if not modified:
        return return_dict

    # Feed back current parameters
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'psa-settings':
            return_dict['input_values'][idx] = new_val

     # Update triggers
    for idx, id in enumerate(trigger_ids):
        return_dict['trigger_data'][idx] = now
  
    # Sync project to store
    project_provider.upsert_component(proj)

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

    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()
    varid =  make_varid(**triggered_id)
    var = mm.variables.get(varid)
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

    # Sync project to store
    project_provider.upsert_component(proj)
    
    return return_dict
