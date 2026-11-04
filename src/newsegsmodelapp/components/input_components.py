"""Components for the inputs of variable parameters: numeric fields and cards, reset and default buttons, rows with lazily built editors, and the handlers of changes.
"""
import logging
logger = logging.getLogger(__name__)

import copy
import json
import time
from typing import Any, Optional, cast

from dash import dcc, html
from dash.exceptions import PreventUpdate
import numpy as np

from useful_types import SequenceNotStr

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelapp.components.constants import VARIABLE_PARAMETER_KEYS
from newsegsmodelapp.components import callback_utils, staleness
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelapp.components.icons import get_icon
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsvariable.update_variable import update_variable
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelapp.registers import register_input_handler
from newsegsmodelapp.registers import get_input_editor_content_creator, get_single_input_header_content_creator
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

def create_numeric_variable_parameter_input(
    param_id: VariableInstanceParameterComponentID,
    placeholder: int | float | str = 0.0,
    value: int | float | None = None,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1
):
    """Create a numeric field for a parameter of a variable.

    The field steps dynamically according to the step, and its id is that of the parameter.

    Args:
        param_id: Identification of the variable parameter that the component edits.
        placeholder: Placeholder shown when the field is empty.
        value: The value.
        min: Minimum value of the field.
        max: Maximum value of the field.
        step: Step of the field.

    Returns:
        The input.
    """
    input_id = param_id.as_dict()

    if float(int(step)) == float(step):
        step = int(step)
        cn = f'dynamic-step-field step-val-{step:d}'
    else:
        cn = f'dynamic-step-field step-val-{step:f}'

    return dbc.Input(
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
    """Create a card with a labelled numeric field for a parameter of a variable.

    The card has an icon, the field, optionally buttons to reset the value and set the default, and a badge showing whether the variable is shared.

    Args:
        icon_name: Name(s) of the icon(s), from `components.icons`.
        label: The label.
        param_id: Identification of the variable parameter that the component edits.
        placeholder: Placeholder shown when the field is empty.
        value: The value.
        min: Minimum value of the field.
        max: Maximum value of the field.
        step: Step of the field.
        reset_button: Whether to include the button which resets the value.
        status_text: Text of the badge which shows whether the variable is shared.
        status_colour: Bootstrap colour of the badge.

    Returns:
        The card.
    """
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
                html.Span(label+":", className='me-2'),
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
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
    new_val: Optional[Any] = None, # Include this so we can call from other parameter setting functions, not just dash callbacks
) -> dict[str, Any]:

    """Input handler for a change in a single parameter of a variable.

    Updates the variable of the active project with the new value, and sets the outputs of the callback according to what the change affected - the deterministic value, the DSA bounds and the PSA statistics. Registered for the purpose `parameter` of `single-input-config` components.

    Args:
        triggered_id: The id of the component which triggered the callback.
        input_ids: The ids of the input components of the callback.
        header_ids: The ids of the header containers of the callback.
        trigger_ids: The ids of the trigger stores of the callback.
        calling_dict: Other keyword arguments of the calling callback.
        active_project_id: Id of the active project.
        project_provider: Provider of projects, metamodels and variables.
        return_dict: Dictionary of the outputs of the callback, to be updated and returned.
        new_val: The new value; by default the value of the triggering component.

    Returns:
        The updated `return_dict`.
    """
    if new_val is None:
        new_val = callback_utils.get_triggered_value()
        if new_val is None:
            new_val = 0

    variable_keys = {k: triggered_id.get(k) for k in VARIABLE_PARAMETER_KEYS}
    varid = make_varid(**variable_keys)
    update_variable_keys = {k: v for k,v in variable_keys.items() if k in {'parameter_index', 'vector_location'}}
    
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Updating a single parameter')
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    var_instance_id = lmm.variables[varid]
    var = provider.variable_provider.get_variable(var_instance_id)
    
    now = time.time_ns()
    
    update_ok, deterministic_changed, dsa_changed, psa_changed, raw_params = update_variable(
        var, value = new_val, **update_variable_keys # pyright: ignore[reportArgumentType]
    )

    # Feed back current parameters
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'parameter':
            pi = id['parameter_index']
            new_param = raw_params[pi] # pyright: ignore[reportCallIssue, reportArgumentType]
            if not isinstance(new_param, np.ndarray):
                return_dict['input_values'][idx] = new_param
            else:
                vi = id['vector_location']
                new_val = new_param.flat[vi] # pyright: ignore[reportArgumentType, reportCallIssue]
                return_dict['input_values'][idx] = new_val

    # Update headers
    for idx, id in enumerate(header_ids):
        try:
            content_creator = get_single_input_header_content_creator(
                id['supersection'], id['section'], lmm.model.model_type
            )
        except KeyError:
            content_creator = None
        if content_creator:
            return_dict['header_children'][idx] = content_creator(varid, var)

    # Update triggers
    for idx, id in enumerate(trigger_ids):
        match id['supersection']:
            case 'deterministic':
                if deterministic_changed:
                    return_dict['trigger_data'][idx] = now
            case 'dsa':
                if dsa_changed:
                    return_dict['trigger_data'][idx] = now
            case 'psa':
                if psa_changed:
                    return_dict['trigger_data'][idx] = now

    if update_ok:
        # Sync the variable
        provider.variable_provider.upsert_variable(var)

        # Mark the model components as revised
        table_components_to_revise = []
        metamodels_to_revise = []
        for mm in lproj.metamodels:
            if var.id in set(mm.variables.values()):
                table_components_to_revise.append(mm.table_config.id)
                table_components_to_revise.append(mm.model.table_config.id)
                table_components_to_revise.append(mm.finance.table_config.id)
                metamodels_to_revise.append(mm.id)
        table_components_to_revise.append(lproj.table_config.id)
        
        provider._component_provider.increment_revision(table_components_to_revise)
        provider.metamodel_provider.increment_revision(metamodels_to_revise)
        provider.increment_revision(lproj.id)

        db_staleness.mark_inputs_changed(
            metamodels_to_revise,
            staleness.processes_affected(deterministic_changed, dsa_changed, psa_changed),
        )
    
    return return_dict

def create_value_reset_button(
    param_id: VariableInstanceParameterComponentID
):
    """Create the button which resets a parameter to its last saved value.

    Args:
        param_id: Identification of the variable parameter that the component edits.

    Returns:
        The button.
    """
    button_id = copy.copy(param_id)
    button_id.type = 'input-action-button'
    button_id.purpose = 'value-reset'
    #button_id.type = 'value-reset-button'
    
    return dbc.Button(
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

@register_input_handler('value-reset', 'input-action-button')
def _reset_value(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
):
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug('Getting lightweight project - Resetting a variable')
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    varid = make_varid(**triggered_id)
    var_uid = lmm.variables[varid]
    var = provider.variable_provider.get_variable(var_uid)
    
    if var is None:
        raise PreventUpdate

    parameter_index = triggered_id.get('parameter_index', 0)
    reset_value = var._default_parameters[parameter_index]

    # Act as if it was a direct parameter set
    return update_single_parameter(
        triggered_id,
        input_ids,
        header_ids,
        trigger_ids,
        calling_dict,
        active_project_id,
        project_provider,
        return_dict,
        new_val = reset_value
    )

def create_value_set_default_button(
    param_id: VariableInstanceParameterComponentID
):
    """Create the button which sets the current value of a parameter as its default.

    Args:
        param_id: Identification of the variable parameter that the component edits.

    Returns:
        The button.
    """
    button_id = copy.copy(param_id)
    button_id.type = 'input-action-button'
    button_id.purpose = 'value-set-default'
    #button_id.type = 'value-set-default-button'
    
    return dbc.Button(
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

@register_input_handler('value-set-default', 'input-action-button')
def _set_default_value(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any]
):
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug("Getting lightweight project - Setting a variable's default value")
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    varid = make_varid(**triggered_id)
    var_uid = lmm.variables[varid]
    var = provider.variable_provider.get_variable(var_uid)

    if var is None:
        raise PreventUpdate

    var.replace_default_parameters()
    provider.variable_provider.upsert_variable(var, force = True)
    
    # No need for anything to happen
    return return_dict

def create_blank_single_input_header_element(
    param_id: VariableInstanceParameterComponentID
):
    """Create an empty, hidden header element for a single input.

    Gives the callbacks somewhere to write to when the input has no header.

    Args:
        param_id: Identification of the variable parameter that the component edits.

    Returns:
        The element.
    """
    header_id = copy.copy(param_id)
    header_id.type = 'single-input-header'
    header_id.purpose = 'header'
    return html.Div(id = header_id.as_dict(), style = {'display': 'none'})

def create_input_group_config_update_trigger(
    param_id: VariableInstanceParameterComponentID,
    purpose: str = 'trigger',
):
    """Create the store which signals that the configuration of an input group has been updated.

    Args:
        param_id: Identification of the variable parameter that the component edits.
        purpose: The purpose field of the component id.

    Returns:
        The store.
    """
    trigger_id = copy.copy(param_id)
    trigger_id.type = 'input-group-config-update-trigger'
    trigger_id.purpose = purpose
    return dcc.Store(id = trigger_id.as_dict())

# -----------------------------------------------
# Lazily built editors
# -----------------------------------------------

def create_lazy_input_details(
    summary_children: Any,
    param_id: VariableInstanceParameterComponentID,
    className: str | None = None,
) -> html.Details:
    """Create a row which builds its editor only when it is opened.

    The row is a `Details` holding a `Summary`, whose clicks are counted by `react_to_input_change`, and an empty
    `input-group-editor` container. An odd count opens the row, and the editor content creator registered for the
    supersection and section of `param_id` (see `registers.register_input_editor_content_creator`) fills the container.
    Reopening the row builds the editor again, so that it shows the current values.

    The row also holds a hidden `single-input-config` with the purpose `editor-anchor`. The Dash renderer only calls
    `react_to_input_change` for a row with a component matching its first output, and the editor's inputs don't exist
    until it is built. No handler writes to the anchor, and its value never changes.

    Redraw only the children of the editor container, never the `Details` or the `Summary`: a new `Summary` restarts the
    count while the `Details` stays as it was, and the count and the open state then disagree. Rebuilding the whole input
    container is safe, since it resets both.

    Don't put interactive components in the `Summary`: clicks on them are counted too.

    Args:
        summary_children: The children of the summary, shown whether the row is open or closed.
        param_id: Identification of the variable parameter that the row edits.
        className: Class of the `Details`.

    Returns:
        The row.
    """
    summary_id = copy.copy(param_id)
    summary_id.type = 'input-summary'
    summary_id.purpose = 'group-editor-toggle'

    editor_id = copy.copy(param_id)
    editor_id.type = 'input-group-editor'
    editor_id.purpose = 'editor'

    anchor_id = copy.copy(param_id)
    anchor_id.type = 'single-input-config'
    anchor_id.purpose = 'editor-anchor'

    return html.Details(
        [
            html.Summary(summary_children, id = summary_id.as_dict()),
            html.Div([], id = editor_id.as_dict()),
            dcc.Input(id = anchor_id.as_dict(), type = 'hidden'),
        ],
        className = className,
    )

@register_input_handler('group-editor-toggle', 'input-summary')
def _build_opened_editor(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
):
    # An odd count of clicks opens the row; nothing is built when it closes
    n_clicks = callback_utils.get_triggered_value()
    if not n_clicks or n_clicks % 2 == 0:
        raise PreventUpdate

    # The editor of the same parameter as the summary
    editor_index = next(
        (
            idx for idx, id in enumerate(calling_dict.get('editor_ids', []))
            if all(id.get(k) == v for k, v in triggered_id.items() if k not in ('type', 'purpose'))
        ),
        None,
    )
    if editor_index is None:
        logger.warning('No editor container for opened row %s', triggered_id)
        raise PreventUpdate

    app_state = calling_dict.get('app_state')
    model_type = json.loads(app_state).get('model_type', 'default') if app_state else 'default'
    try:
        content_creator = get_input_editor_content_creator(
            triggered_id['supersection'], triggered_id['section'], model_type
        )
    except KeyError:
        logger.warning(
            'No input editor content creator for supersection %s, section %s and model type %s',
            triggered_id['supersection'], triggered_id['section'], model_type
        )
        raise PreventUpdate

    return_dict['editor_children'][editor_index] = content_creator(
        make_varid(**triggered_id), active_project_id, project_provider
    )
    return return_dict

# -----------------------------------------------
# Variable group cycling
# -----------------------------------------------

def _variables_by_varid(
    proj: LightweightNewsegsProject,
    varid: str
) -> list[str]:
    var_uids = []
    for lmm in proj.metamodels:
        var_uid = lmm.variables.get(varid, None)
        if var_uid is not None and var_uid not in var_uids:
            var_uids.append(var_uid)
    return var_uids

def get_metamodel_groups_for_var(proj: LightweightNewsegsProject, varid: str) -> list[set[int]]:
    """
    Finds groups of metamodels (1-indexed) sharing the variable with `varid`.
    Returns a list of sets containing metamodel 1-based indices.
    """
    var_to_mm_indices: dict[str, set[int]] = {}
    for idx, lmm in enumerate(proj.metamodels, start = 1):
        if varid in lmm.variables:
            var_to_mm_indices.setdefault(lmm.variables[varid], set()).add(idx)
            
    return list(var_to_mm_indices.values())

def get_variable_sharing_status(
    proj: LightweightNewsegsProject,
    current_mm: LightweightNewsegsMetaModel, 
    varid: str
) -> tuple[str, str]:
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
    """Create the badge which shows, and toggles, whether a variable is shared by all configurations.

    Args:
        param_id: Identification of the variable parameter that the component edits.
        status_text: Text of the badge which shows whether the variable is shared.
        colour: Bootstrap colour of the badge.

    Returns:
        The badge.
    """
    badge_id = copy.copy(param_id)
    badge_id.type = 'input-action-button'
    badge_id.purpose = 'variable-status-toggle'

    return dbc.Badge(
        status_text,
        id = badge_id.as_dict(),
        color = colour,
        className = "me-2 variable-status-badge",
        style = {"cursor": "pointer"}
    )

@register_input_handler('variable-status-toggle', 'input-action-button')
def _toggle_variable_sharing(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
) -> dict:
    val = callback_utils.get_triggered_value()
    if val is None:
        return return_dict

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    varid = make_varid(**triggered_id)

    groups = get_metamodel_groups_for_var(lproj, varid)
    if not groups or len(groups) < 1 or (len(groups) == 1 and len(groups[0]) <= 1):
        return return_dict
    
    current_mm_idx = lproj.metamodels.index(lmm) + 1
    old_var = project_provider.variable_provider.get_variable(lmm.variables[varid])
    
    # Locate current group index
    current_group_idx = next(i for i, g in enumerate(groups) if current_mm_idx in g)

    vars_to_delete = []
    if len(groups[current_group_idx]) == 1:
        # MM is alone in the group - will need to delete the variable as we exit.
        vars_to_delete.append(lmm.variables[varid])

    # Cycle to the next group index
    next_group_idx = (current_group_idx + 1)# % len(groups)
    if next_group_idx >= len(groups):
        if len(groups[-1]) == 1:
            # Was independent and so should cycle to joining the first variable group
            next_group_idx = 0
            var_uid = _variables_by_varid(lproj, varid)[next_group_idx]
            lmm.variables[varid] = var_uid
        else:
            # Should spawn a new variable
            var = project_provider.variable_provider.duplicate_variable(lmm.variables[varid])
            lmm.variables[varid] = var.id
            project_provider.add_variables_to_project(lproj.id, [var])
    else:
        var_uid = _variables_by_varid(lproj, varid)[next_group_idx]
        lmm.variables[varid] = var_uid

    if vars_to_delete:
        project_provider.remove_variables_from_project(lproj.id, vars_to_delete)

    # Update the variable junction table for the metamodel
    var = project_provider.variable_provider.get_lightweight_variable(lmm.variables[varid])
    project_provider.metamodel_provider.refresh_metamodel_variable_junction(
        lmm,
        [var]
    )

    # Invalidate tables
    project_provider._component_provider.increment_revision(
        [
            lmm.table_config.id,
            lproj.table_config.id
        ]
    )
    project_provider.metamodel_provider.increment_revision(lmm.id)
    project_provider.increment_revision(lproj.id)

    db_staleness.mark_inputs_changed(
        lmm.id,
        staleness.processes_affected_by_variable_swap(
            old_var, project_provider.variable_provider.get_variable(lmm.variables[varid])
        ),
    )

    if isinstance(project_provider, FromDatabaseNewsegsProjectProvider):
        project_provider.delete_orphan_variables()

    # Return update signals to refresh input card headers and values

    # Feed back current parameters
    rps = (var.raw_parameter_0, var.raw_parameter_1)
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'parameter':
            pi = id['parameter_index']
            new_param = rps[pi] # pyright: ignore[reportCallIssue, reportArgumentType]
            if not isinstance(new_param, np.ndarray):
                return_dict['input_values'][idx] = new_param
            else:
                vi = id['vector_location']
                new_val = new_param.flat[vi] # pyright: ignore[reportArgumentType, reportCallIssue]
                return_dict['input_values'][idx] = new_val

    # Update headers
    for idx, id in enumerate(header_ids):
        try:
            content_creator = get_single_input_header_content_creator(
                id['supersection'], id['section'], lmm.model.model_type
            )
        except KeyError:
            content_creator = None
        if content_creator:
            varid =  make_varid(**triggered_id)
            return_dict['header_children'][idx] = content_creator(varid, lmm)

    now = time.time_ns()

    # Update triggers
    for idx, id in enumerate(trigger_ids):
        return_dict['trigger_data'][idx] = now
        
    return return_dict

@register_input_handler('toggle-optim-active', 'input-toggle')
def _set_variable_optim_active(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
) -> dict[str, Any]:
    val = callback_utils.get_triggered_value()
    if val is None:
        raise PreventUpdate

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    logger.debug("Getting lightweight project - Toggling a variable's activation status for optimisation")
    lproj = provider.get_lightweight_project(active_project_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    varid = make_varid(**triggered_id)
    varprovider = cast(FromDatabaseVariableProvider, project_provider.variable_provider)
    varuid =lmm.variables.get(varid)
    if varuid is None:
        raise PreventUpdate
    var = varprovider.get_full_lightweight_variable(varuid)

    if var is None:
        raise PreventUpdate

    if var.optim_selected == val:
        raise PreventUpdate

    var.optim_selected = val
    varprovider.set_variable_metadata(var.id, 'optim_selected', var.optim_selected)

    provider.invalidate_cache_for_component(lproj.id)
    db_staleness.mark_inputs_changed(staleness.metamodels_using_variable(lproj, varuid), 'optim')
    
    now = time.time_ns()
    # Update triggers in case there is any formatting that needs to be done.
    for idx, id in enumerate(trigger_ids):
        return_dict['trigger_data'][idx] = now

    return return_dict
