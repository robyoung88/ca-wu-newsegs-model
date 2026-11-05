"""The groups of an input on the DSA page: a summary line with every group's value and bounds, and the group editor,
in which every group's value, bound type and bounds can be edited and configurations moved between groups.

The editor's focussed row keeps the ids of the focussed configuration's inputs (`single-input-config` and the
`dsaboundtype` dropdown), so their handlers in `react_to_input_change` act on it. The other groups' inputs are
`group-value-input`s carrying the id of their Variable (see `group_editor.group_component_id`), handled here and in
`group_editor`. Moves use `group_editor`'s handler, which redraws this editor.
"""
import logging
logger = logging.getLogger(__name__)

import json
import time
from typing import Any, Mapping, Sequence, cast

from dash import dcc, html
from dash.exceptions import PreventUpdate
import numpy as np

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils, staleness
from newsegsmodelapp.components.group_editor import (
    _redraw_editor,
    create_group_editor_frame,
    create_group_row,
    group_component_id,
)
from newsegsmodelapp.components.input_components import _config_icons, _signal_summary_refresh, get_variable_groups
from newsegsmodelapp.components.variable_dash_component import vdc
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelapp.registers import register_input_editor_content_creator, register_input_handler
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

SUPERSECTION = 'dsa'

# -----------------------------------------------
# Changes of the DSA settings of a Variable
# -----------------------------------------------

def _save_dsa_change(provider: FromDatabaseNewsegsProjectProvider, lproj: LightweightNewsegsProject, var):
    """Save a Variable whose DSA settings changed, and mark the DSA stale for the configurations using it"""
    provider.variable_provider.upsert_variable(var)
    provider.increment_revision(lproj.id)
    provider._component_provider.increment_revision(lproj.table_config.id)
    db_staleness.mark_inputs_changed(staleness.metamodels_using_variable(lproj, var.id), 'dsa')

def set_dsa_bound(provider: FromDatabaseNewsegsProjectProvider, lproj: LightweightNewsegsProject, var, purpose: str, value: Any) -> bool:
    """Set a DSA bound of a Variable of a project, and save it if it changed.

    Args:
        provider: Provider of the project.
        lproj: The lightweight project.
        var: The Variable; not necessarily the focussed configuration's.
        purpose: `bound-lower` or `bound-upper`.
        value: The bound, in the terms of the Variable's bound type.

    Returns:
        Whether the bound changed.
    """
    attribute = 'dsa_lower' if purpose.endswith('bound-lower') else 'dsa_upper'
    if np.array_equal(np.asarray(value, dtype = object), np.asarray(getattr(var, attribute), dtype = object)):
        return False
    setattr(var, attribute, value)
    _save_dsa_change(provider, lproj, var)
    return True

def set_dsa_bound_type(provider: FromDatabaseNewsegsProjectProvider, lproj: LightweightNewsegsProject, var, bound_type: str) -> bool:
    """Set the DSA bound type of a Variable of a project, with the bounds its distribution suggests for the type.

    Args:
        provider: Provider of the project.
        lproj: The lightweight project.
        var: The Variable; not necessarily the focussed configuration's.
        bound_type: The bound type.

    Returns:
        Whether the type changed.
    """
    if not bound_type or bound_type == var.dsa_bounds_type:
        return False
    var.dsa_bounds_type = bound_type
    var.dsa_lower, var.dsa_upper = var.distribution.dsa_auto_values(var)
    _save_dsa_change(provider, lproj, var)
    return True

# -----------------------------------------------
# Comparison and summary of the groups
# -----------------------------------------------

def _settings(var: FullLightweightVariable) -> tuple:
    return (var.dsa_bounds_type, json.dumps(var.dsa_lower, default = str), json.dumps(var.dsa_upper, default = str))

def dsa_bounds_differ(variables: Sequence[FullLightweightVariable]) -> bool:
    """Whether Variables have different DSA bound types or bound settings.

    Bounds calculated from the same settings on different values don't differ: the same relative bound gives different
    values on different values.

    Args:
        variables: The Variables, e.g. of the groups of a variable.

    Returns:
        Whether they differ.
    """
    return len({_settings(x) for x in variables}) > 1

def count_variables_with_different_bounds(lproj: LightweightNewsegsProject, variables: Mapping[str, FullLightweightVariable]) -> int:
    """The number of the variables shown on the DSA page whose groups have different DSA bound types or settings.

    Args:
        lproj: The lightweight project.
        variables: The Variables of the project, by id.

    Returns:
        The number of variables.
    """
    varids = dict.fromkeys(varid for lmm in lproj.metamodels for varid in lmm.variables)
    n = 0
    for varid in varids:
        group_vars = [variables[x.var_uid] for x in get_variable_groups(lproj, varid) if x.var_uid in variables]
        if group_vars and group_vars[0].dsa_show and dsa_bounds_differ(group_vars):
            n += 1
    return n

def _value_and_bounds(var: FullLightweightVariable) -> str:
    fmt = vdc.dsa_value_formatter(var)
    return f'{fmt(var.last_deterministic_value)} [{fmt(var.dsa_value_lower)}, {fmt(var.dsa_value_upper)}]'

def create_dsa_sharing_summary_contents(
    proj: LightweightNewsegsProject,
    varid: str,
    variables: Mapping[str, FullLightweightVariable],
) -> list:
    """Create what the DSA row's summary line shows: nothing unless there are several groups; otherwise each group's
    configurations, value and calculated bounds, and `≠ bounds` if their bound types or settings differ.

    Args:
        proj: The lightweight project.
        varid: Id of the variable.
        variables: The Variables of the project, by id; it needs only those of the groups.

    Returns:
        The children of the summary.
    """
    groups = [x for x in get_variable_groups(proj, varid) if x.var_uid is not None]
    if len(proj.metamodels) <= 1 or len(groups) <= 1:
        return []
    focussed_index = proj.focussed_metamodel_index
    line = []
    for group in groups:
        if line:
            line.append(' · ')
        var = variables[cast(str, group.var_uid)]
        class_name = 'variable-sharing-group' + (' focussed' if focussed_index in group.metamodel_indices else '')
        line.append(html.Span([*_config_icons(group.metamodel_indices), ' ', _value_and_bounds(var)], className = class_name))
    if dsa_bounds_differ([variables[cast(str, x.var_uid)] for x in groups]):
        line.append(html.Span('≠ bounds', className = 'dsa-bounds-differ', title = 'The groups have different bound types or settings'))
    return line

# -----------------------------------------------
# The editor
# -----------------------------------------------

def _row_param_id(var: FullLightweightVariable) -> VariableInstanceParameterComponentID:
    return VariableInstanceParameterComponentID.from_lightweight_variable(var, type = 'single-input-config', supersection = SUPERSECTION)

def _focussed_cells(var: FullLightweightVariable) -> list:
    """The cells of the focussed row: the focussed configuration's inputs, with their usual ids and handlers"""
    parts = vdc.create_dsa_input_parts(var)
    return [
        html.Div(parts['parameters'], className = 'group-editor-value dsa-group-parameters'),
        html.Div(parts['bound_type_selector'], className = 'dsa-group-bound-type'),
        html.Div(parts['bounds'], className = 'dsa-group-bounds'),
    ]

def _group_cells(varid: str, var: FullLightweightVariable) -> list:
    """The cells of another group's row: the same inputs, identified by the group's Variable"""
    def id_for(purpose: str, parameter_index: int = 0):
        return group_component_id(varid, var.id, SUPERSECTION, purpose, parameter_index)
    parts = vdc.create_dsa_input_parts(var, id_for = id_for)
    return [
        html.Div(parts['parameters'], className = 'group-editor-value dsa-group-parameters'),
        html.Div(parts['bound_type_selector'], className = 'dsa-group-bound-type'),
        html.Div(parts['bounds'], className = 'dsa-group-bounds'),
    ]

def create_dsa_group_editor_contents(varid: str, active_project_id: str, project_provider: NewsegsProjectProviderInterface) -> list:
    """Create the DSA row's editor: a row for each group, with its value, bound type and bounds, and its configurations.

    The focussed configuration's row holds its usual inputs. A project with one configuration has that row alone.

    Args:
        varid: Id of the variable.
        active_project_id: Id of the project.
        project_provider: Provider of the project.

    Returns:
        The children of the row's `input-group-editor` container.
    """
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(active_project_id)
    groups = [x for x in get_variable_groups(lproj, varid) if x.var_uid is not None]
    if not groups:
        return []
    variables = {x.id: x for x in provider.variable_provider.get_full_lightweight_variable([cast(str, x.var_uid) for x in groups])}
    focussed_index = lproj.focussed_metamodel_index

    if len(lproj.metamodels) <= 1:
        var = variables[cast(str, groups[0].var_uid)]
        return [html.Div(html.Div(_focussed_cells(var), className = 'group-editor-row dsa-group-row'), className = 'group-editor group-editor-dsa')]

    rows = []
    for group in groups:
        var = variables[cast(str, group.var_uid)]
        is_focussed = focussed_index in group.metamodel_indices
        cells = _focussed_cells(var) if is_focussed else _group_cells(varid, var)
        rows.append(create_group_row(cells, group, focussed_index, _value_and_bounds(var), len(groups), className = 'dsa-group-row'))
    head = [html.Span('Value'), html.Span('Bounds'), html.Span('Lower, upper'), html.Span('Group')]
    return create_group_editor_frame(varid, SUPERSECTION, head, rows)

register_input_editor_content_creator(SUPERSECTION, None, 'default')(create_dsa_group_editor_contents)

# -----------------------------------------------
# Handlers of the other groups' DSA settings
# -----------------------------------------------

def _group_variable(triggered_id: dict, lproj: LightweightNewsegsProject, provider: FromDatabaseNewsegsProjectProvider):
    """The Variable of a group input, or None if no configuration uses it any more (e.g. moved by another tab)"""
    varid = make_varid(**triggered_id)
    var_uid = triggered_id['var_uid']
    if not any(x.variables.get(varid) == var_uid for x in lproj.metamodels):
        logger.warning('Rejected a DSA setting of %s for %s, which no configuration uses', varid, var_uid)
        return None
    return provider.variable_provider.get_variable(var_uid)

def _set_group_dsa_setting(triggered_id, calling_dict, active_project_id, project_provider, return_dict, apply):
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(active_project_id)
    var = _group_variable(triggered_id, lproj, provider)
    if var is not None and apply(provider, lproj, var):
        _signal_summary_refresh(return_dict, time.time_ns())
    # Shows the settings as saved, and the bounds of a new bound type
    _redraw_editor(triggered_id, calling_dict, active_project_id, project_provider, return_dict)
    return return_dict

@register_input_handler('group-dsaboundtype', 'group-value-input')
def _set_group_dsa_bound_type(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
):
    bound_type = callback_utils.get_triggered_value()
    if not bound_type:
        raise PreventUpdate
    return _set_group_dsa_setting(
        triggered_id, calling_dict, active_project_id, project_provider, return_dict,
        lambda provider, lproj, var: set_dsa_bound_type(provider, lproj, var, bound_type),
    )

def _set_group_dsa_bound(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
):
    value = callback_utils.get_triggered_value()
    return _set_group_dsa_setting(
        triggered_id, calling_dict, active_project_id, project_provider, return_dict,
        lambda provider, lproj, var: set_dsa_bound(provider, lproj, var, triggered_id['purpose'], value),
    )

register_input_handler('group-dsa-bound-lower', 'group-value-input')(_set_group_dsa_bound)
register_input_handler('group-dsa-bound-upper', 'group-value-input')(_set_group_dsa_bound)
