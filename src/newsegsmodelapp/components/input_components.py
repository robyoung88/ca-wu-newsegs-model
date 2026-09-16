import copy
import time
from typing import Any, Optional

from dash import dcc, html, no_update
from dash_bootstrap_components._components.Input import Input as dbc_Input # Bit of a faff to get around the pyright behaviour https://github.com/microsoft/pyright/issues/3131
from dash_bootstrap_components._components.Button import Button as dbc_Button
from dash_bootstrap_components._components.Badge import Badge as dbc_Badge
from dash.exceptions import PreventUpdate
import numpy as np

from useful_types import SequenceNotStr

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components.constants import CONFIGURATION_UPDATE_TRIGGER_ID, VARIABLE_PARAMETER_KEYS
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelapp.newsegsbrowser.icons import get_icon
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelapp.registers import register_input_handler
from newsegsmodelapp.registers import get_feedback_graph_artist, get_input_container_content_creator, get_input_section_header_content_creator, get_single_input_header_content_creator

def create_numeric_variable_parameter_input(
    param_id: VariableInstanceParameterComponentID,
    placeholder: int | float | str = 0.0,
    value: int | float | None = None,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1
):
    input_id = param_id.as_dict()

    if float(int(step)) == float(step):
        step = int(step)
        cn = f'dynamic-step-field step-val-{step:d}'
    else:
        cn = f'dynamic-step-field step-val-{step:f}'

    return dbc_Input(
        id = input_id,
        type = 'number',
        value = value,
        placeholder = placeholder,
        min = min,
        max = max,
        step = 'any',
        className = cn,
        debounce = True,
    )

def create_numeric_card_variable_parameter_input(
    icon_name: str | SequenceNotStr[str],
    label: str,
    param_id: VariableInstanceParameterComponentID,
    placeholder: int | float = 0.0,
    value: int | float | None = None,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1,
    reset_button = True,
    status_text: str = "Shared with all",
    status_colour: str = "success",
):
    button_elements = []
    if reset_button:

        set_button_id = copy.copy(param_id)
        set_button_id.type = 'value-set-default-button'

        button_elements = [
            html.Details([
                html.Summary(),
                html.Div([
                    create_value_reset_button(param_id),
                    create_value_set_default_button(param_id),
                ])
            ])
        ]
    return html.Div(
        button_elements + [
        html.H5(
            [
                get_icon(icon_name, None, 'default'),
                html.Span(label+":", className='mr-3'),
                create_variable_status_badge(param_id, status_text = status_text, colour = status_colour),
            ],
            style={'display':'inline'}
        ),
        create_numeric_variable_parameter_input(
            param_id,
            placeholder,
            value,
            min,
            max,
            step
        ),
        ],
        className = 'numeric-card-input'
    )

@register_input_handler('parameter', 'single-input-config')
def update_single_parameter(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    input_values: list[Any],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    new_val: Optional[Any] = None, # Include this so we can call from other parameter setting functions, not just dash callbacks
):

    if new_val is None:
        new_val = callback_utils.get_triggered_value()
        if new_val is None:
            new_val = 0
    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()
    variable_keys = {k: triggered_id.get(k) for k in VARIABLE_PARAMETER_KEYS}

    input_returns: list[Any] = [no_update] * len(input_ids)
    header_returns: list[Any] = [no_update] * len(header_ids)
    trigger_returns: list[Any] = [no_update] * len(trigger_ids)

    now = time.time_ns()
    
    update_ok, deterministic_changed, dsa_changed, psa_changed, raw_params = mm.update_variable_from_interface(
        value = new_val, **variable_keys # pyright: ignore[reportArgumentType]
    )

    # Feed back current parameters
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'parameter':
            pi = id['parameter_index']
            new_param = raw_params[pi] # pyright: ignore[reportCallIssue, reportArgumentType]
            if not isinstance(new_param, np.ndarray):
                input_returns[idx] = new_param
            else:
                vi = id['vector_location']
                new_val = new_param.flat[vi] # pyright: ignore[reportArgumentType, reportCallIssue]
                input_returns[idx] = new_val

    # Update headers
    for idx, id in enumerate(header_ids):
        try:
            content_creator = get_single_input_header_content_creator(
                id['supersection'], id['section'], mm.model.model_type
            )
        except KeyError:
            content_creator = None
        if content_creator:
            varid =  make_varid(**triggered_id)
            header_returns[idx] = content_creator(varid, mm)

    # Update triggers
    for idx, id in enumerate(trigger_ids):
        match id['supersection']:
            case 'deterministic':
                if deterministic_changed:
                    trigger_returns[idx] = now
            case 'dsa':
                if dsa_changed:
                    trigger_returns[idx] = now
            case 'psa':
                if psa_changed:
                    trigger_returns[idx] = now

    # Sync project to store
    project_provider.upsert_component(proj)

    # TODO: Feed back to inputs if the update is not ok (set invalid)

    return input_returns, header_returns, trigger_returns

def create_value_reset_button(
    param_id: VariableInstanceParameterComponentID
):
    button_id = copy.copy(param_id)
    button_id.type = 'action-button'
    button_id.purpose = 'value-reset'
    #button_id.type = 'value-reset-button'
    
    return dbc_Button(
        html.I(
            className = get_icon('value-reset', style_name = 'raw'),
            style = {'display': 'inline'}
        ),
        color = 'light',
        id = button_id.as_dict(),
        title = 'Reset to default',
        outline = False,
        size = 'sm'
    )

@register_input_handler('value-reset', 'action-button')
def _reset_value(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    input_values: list[Any],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
):
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()

    varid = make_varid(**triggered_id)
    var = mm.variables.get(varid)
    if var is None:
        raise PreventUpdate

    input_returns: list[Any] = [no_update] * len(input_ids)

    parameter_index = triggered_id.get('parameter_index', 0)
    reset_value = var._default_parameters[parameter_index]

    # Act as if it was a direct parameter set
    return update_single_parameter(
        triggered_id,
        input_ids,
        input_values,
        header_ids,
        trigger_ids,
        active_project_id,
        project_provider,
        reset_value
    )

def create_value_set_default_button(
    param_id: VariableInstanceParameterComponentID
):
    button_id = copy.copy(param_id)
    button_id.type = 'action-button'
    button_id.purpose = 'value-set-default'
    #button_id.type = 'value-set-default-button'
    
    return dbc_Button(
        html.I(
            className = get_icon('value-set-default', style_name = 'raw'),
            style = {'display': 'inline'}
        ),
        color = 'light',
        id = button_id.as_dict(),
        title = 'Set default to current value',
        outline = False,
        size = 'sm',
        class_name = 'set-default',
    )

@register_input_handler('value-set-default', 'action-button')
def _set_default_value(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    input_values: list[Any],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
):
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()

    varid = make_varid(**triggered_id)
    var = mm.variables.get(varid)
    if var is None:
        raise PreventUpdate

    var.replace_default_parameters()
    var.revision += 1
    project_provider.upsert_component(proj)

    # No need for anything to happen
    raise PreventUpdate

    input_returns: list[Any] = [no_update] * len(input_ids)
    header_returns: list[Any] = [no_update] * len(header_ids)
    trigger_returns: list[Any] = [no_update] * len(trigger_ids)

    return input_returns, header_returns, trigger_returns

def create_blank_single_input_header_element(
    param_id: VariableInstanceParameterComponentID
):
    header_id = copy.copy(param_id)
    header_id.type = 'single-input-header'
    header_id.purpose = 'header'
    return html.Div(id = header_id.as_dict(), style = {'display': 'none'})

def create_input_group_config_update_trigger(
    param_id: VariableInstanceParameterComponentID,
    purpose: str = 'trigger',
):
    trigger_id = copy.copy(param_id)
    trigger_id.type = 'input-group-config-update-trigger'
    trigger_id.purpose = purpose
    return dcc.Store(id = trigger_id.as_dict())

# -----------------------------------------------
# Variable group cycling
# -----------------------------------------------

def get_metamodel_groups_for_var(proj: NewsegsProject, varid: str) -> list[set[int]]:
    """
    Finds groups of metamodels (1-indexed) sharing the variable with `varid`.
    Returns a list of sets containing metamodel 1-based indices.
    """
    var_to_mm_indices: dict[int, set[int]] = {}
    if not varid in proj._variables_by_varid:
        print(f'{varid} not in project variables - available keys are {proj._variables_by_varid.keys()}')
        return []
    for uid, var in proj._variables_by_varid[varid].items():
        var_inst_id = id(var)
        for idx, mm in enumerate(proj.metamodels, start = 1):
            if varid in mm.variables and id(mm.variables[varid]) == var_inst_id:
                var_to_mm_indices.setdefault(var_inst_id, set()).add(idx)
            
    return list(var_to_mm_indices.values())

def get_variable_sharing_status(proj, current_mm: NewsegsMetaModel, varid: str) -> tuple[str, str]:
    """
    Determines status label and badge color scheme for a given variable.
    """
    total_mms = len(proj.metamodels)
    if total_mms <= 1:
        return "Independent", "secondary"

    groups = get_metamodel_groups_for_var(proj, varid)
    current_mm_idx = proj.metamodels.index(current_mm) + 1

    # Find group containing the current metamodel
    current_group = next((g for g in groups if current_mm_idx in g), {current_mm_idx})

    if len(current_group) == total_mms:
        return "Shared with all", "success"
    elif len(current_group) == 1:
        return "Independent", "secondary"
    else:
        indices_str = ", ".join(str(i) for i in sorted(current_group))
        return f"Shared with MM: {indices_str}", "info"

def create_variable_status_badge(
    param_id: VariableInstanceParameterComponentID, 
    status_text: str = "Shared with all", 
    colour: str = "success"
):
    badge_id = copy.copy(param_id)
    badge_id.type = 'action-button'
    badge_id.purpose = 'variable-status-toggle'

    return html.Span([
        dbc_Badge(
            status_text,
            id = badge_id.as_dict(),
            color = colour,
            className = "ml-2 variable-status-badge",
            style = {"cursor": "pointer"}
        ),
        create_input_group_config_update_trigger(param_id, purpose='variable-status-trigger')
    ])

@register_input_handler('variable-status-toggle', 'action-button')
def _toggle_variable_sharing(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    input_values: list[Any],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
):
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()
    varid = make_varid(**triggered_id)

    groups = get_metamodel_groups_for_var(proj, varid)
    print(varid, ' ' , groups)
    if not groups or len(groups) < 1 or (len(groups) == 1 and len(groups[0]) <= 1):
        raise PreventUpdate
    
    current_mm_idx = proj.metamodels.index(mm) + 1
    
    # Locate current group index
    current_group_idx = next(i for i, g in enumerate(groups) if current_mm_idx in g)
    print(current_group_idx)

    vars_to_delete = []
    if len(groups[current_group_idx]) == 1:
        # MM is alone in the group - will need to delete the variable as we exit.
        vars_to_delete.append(mm.variables[varid].id)

    # Cycle to the next group index
    next_group_idx = (current_group_idx + 1)# % len(groups)
    if next_group_idx >= len(groups):
        if len(groups[-1]) == 1:
            # Was independent and so should cycle to joining the first variable group
            next_group_idx = 0
            var_uid = list(proj._variables_by_varid[varid].keys())[next_group_idx]
            mm.variables[varid] = proj._variables_by_uid[var_uid]
            mm.revision += 1
        else:
            # Should spawn a new variable
            var = project_provider.variable_provider.duplicate_variable(mm.variables[varid].id)
            mm.variables[varid] = var
            mm.revision += 1
            proj.add_variable(var)
    else:
        var_uid = list(proj._variables_by_varid[varid].keys())[next_group_idx]
        mm.variables[varid] = proj._variables_by_uid[var_uid]
        mm.revision += 1

    if vars_to_delete:
        proj.delete_variable(vars_to_delete)
        proj.revision += 1
    
    project_provider.upsert_component(proj)
    if isinstance(project_provider, FromDatabaseNewsegsProjectProvider):
        project_provider.delete_orphan_variables()

    # Return update signals to refresh input card headers and values
    input_returns: list[Any] = [no_update] * len(input_ids)
    header_returns: list[Any] = [no_update] * len(header_ids)
    trigger_returns: list[Any] = [no_update] * len(trigger_ids)

    # Feed back current parameters
    raw_params = mm.variables[varid].raw_parameters
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'parameter':
            pi = id['parameter_index']
            new_param = raw_params[pi] # pyright: ignore[reportCallIssue, reportArgumentType]
            if not isinstance(new_param, np.ndarray):
                input_returns[idx] = new_param
            else:
                vi = id['vector_location']
                new_val = new_param.flat[vi] # pyright: ignore[reportArgumentType, reportCallIssue]
                input_returns[idx] = new_val

    # Update headers
    for idx, id in enumerate(header_ids):
        try:
            content_creator = get_single_input_header_content_creator(
                id['supersection'], id['section'], mm.model.model_type
            )
        except KeyError:
            content_creator = None
        if content_creator:
            varid =  make_varid(**triggered_id)
            header_returns[idx] = content_creator(varid, mm)

    now = time.time_ns()

    # Update triggers
    for idx, id in enumerate(trigger_ids):
        trigger_returns[idx] = now
        
    return input_returns, header_returns, trigger_returns

@register_input_handler('toggle-optim-active', 'toggle')
def _set_variable_optim_active(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    input_values: list[Any],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
):
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()
    varid = make_varid(**triggered_id)

    var = mm.variables.get(varid)
    if var is None:
        raise PreventUpdate

    if var.optim_selected == val:
        raise PreventUpdate

    var.optim_selected = True
    proj.revision += 1
    project_provider.upsert_component(proj)

    # Return update signals to refresh input card headers and values
    input_returns: list[Any] = [no_update] * len(input_ids)
    header_returns: list[Any] = [no_update] * len(header_ids)
    trigger_returns: list[Any] = [no_update] * len(trigger_ids)

    now = time.time_ns()
    # Update triggers in case there is any formatting that needs to be done.
    for idx, id in enumerate(trigger_ids):
        trigger_returns[idx] = now

    return input_returns, header_returns, trigger_returns
