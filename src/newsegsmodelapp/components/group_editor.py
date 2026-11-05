"""The group editor of an input on the site configuration page: every group's value, and moving configurations between
groups.

A group is one instance of a variable (a Variable) and the configurations using it. The editor is built when its row is
opened (see `input_components.create_lazy_input_details`). It holds a row for each group, with the group's value (the
focussed group's is edited in the main input) and its configuration icons, and a row for a new value.

Selecting an icon and choosing a row to move it to happens in the browser (`assets/group_editor.js`), which writes the
move to the row's `group-move-request` store. `react_to_input_change` passes the move, and changes of the values of the
other groups (`group-value-input`), to the handlers here. Both redraw only the row's editor and summary, and the main
input, header and triggers of the row when the focussed configuration's Variable changes.
"""
import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass, field
import json
import time
from typing import Any, Sequence, cast

from dash import ctx, dcc, html, no_update
from dash.exceptions import PreventUpdate
import numpy as np

from newsegsmodelapp.backend.db import db_staleness
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components import callback_utils, staleness
from newsegsmodelapp.components.icons import ICON_COLOUR_CLASSES, get_icon
from newsegsmodelapp.components.input_components import (
    VariableGroup,
    apply_parameter_change,
    format_variable_value,
    get_variable_groups,
    update_single_parameter,
    _signal_summary_refresh,
)
from newsegsmodelapp.components.variable_identification import VariableGroupComponentID, VariableInstanceParameterComponentID
from newsegsmodelapp.registers import (
    get_input_editor_content_creator,
    get_single_input_header_content_creator,
    register_input_editor_content_creator,
    register_input_handler,
)
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

NEW_VARIABLE = 'new'
"""The target of a move which gives the configuration its own copy of its Variable."""

SUPERSECTION = 'deterministic'

# -----------------------------------------------
# Moves
# -----------------------------------------------

@dataclass
class GroupMoves:
    """What `move_metamodels_to_group` changed.

    Attributes:
        moved: Indices of the configurations whose Variable changed.
        removed: Ids of the Variables left without a configuration, and removed from the project.
        created: Ids of the Variables created for a new value.
    """
    moved: list[int] = field(default_factory = list)
    removed: list[str] = field(default_factory = list)
    created: list[str] = field(default_factory = list)

def move_metamodels_to_group(
    provider: FromDatabaseNewsegsProjectProvider,
    lproj: LightweightNewsegsProject,
    varid: str,
    mm_indices: Sequence[int],
    target: str,
) -> GroupMoves:
    """Move configurations to a group: give them a Variable of the project, or each a copy of its own.

    All the moves are applied as one operation: the Variables are reassigned, then those left without a configuration
    are removed, and the configurations, their tables and the project are revised once. Each moved configuration has the
    processes that the swap of Variable affects marked stale. The configurations need not include the focussed one.

    A configuration already using the target, or already alone in its group when the target is a new value, is left as
    it is, so no group is left without a configuration.

    Args:
        provider: Provider of the project.
        lproj: The lightweight project. Its configurations' Variables are updated.
        varid: Id of the variable.
        mm_indices: Indices of the configurations to move.
        target: Id of a Variable of the project for the variable, or `NEW_VARIABLE`.

    Returns:
        What changed.

    Raises:
        ValueError: If the target is not a Variable of the project for the variable, or a configuration does not exist
            or has no Variable for the variable. Nothing is changed.
    """
    groups = [x for x in get_variable_groups(lproj, varid) if x.var_uid is not None]
    group_sizes = {x.var_uid: len(x.metamodel_indices) for x in groups}
    if target != NEW_VARIABLE and target not in group_sizes:
        raise ValueError(f'{target} is not a Variable of the project for {varid}')
    for idx in mm_indices:
        if not 0 <= idx < len(lproj.metamodels) or varid not in lproj.metamodels[idx].variables:
            raise ValueError(f'Configuration {idx} has no Variable for {varid}')

    # (configuration index, old Variable, new Variable)
    moves: list[tuple[int, str, str]] = []
    result = GroupMoves()
    for idx in dict.fromkeys(mm_indices):
        old_uid = lproj.metamodels[idx].variables[varid]
        if target == NEW_VARIABLE:
            if group_sizes[old_uid] == 1:
                continue
            var = provider.variable_provider.duplicate_variable(old_uid)
            provider.add_variables_to_project(lproj.id, [var])
            group_sizes[old_uid] -= 1
            result.created.append(var.id)
            moves.append((idx, old_uid, var.id))
        elif old_uid != target:
            moves.append((idx, old_uid, target))
    if not moves:
        return result

    old_vars = {old: provider.variable_provider.get_variable(old) for _, old, _ in moves}
    for idx, _, new_uid in moves:
        lproj.metamodels[idx].variables[varid] = new_uid
    result.moved = [idx for idx, _, _ in moves]

    in_use = {x.variables.get(varid) for x in lproj.metamodels}
    result.removed = [x for x in dict.fromkeys(old for _, old, _ in moves) if x not in in_use]
    if result.removed:
        provider.remove_variables_from_project(lproj.id, result.removed)

    moved_lmms = [lproj.metamodels[idx] for idx in result.moved]
    for lmm in moved_lmms:
        provider.metamodel_provider.refresh_metamodel_variable_junction(
            lmm, [provider.variable_provider.get_lightweight_variable(lmm.variables[varid])]
        )

    provider._component_provider.increment_revision(
        [x.table_config.id for x in moved_lmms] + [lproj.table_config.id]
    )
    provider.metamodel_provider.increment_revision([x.id for x in moved_lmms])
    provider.increment_revision(lproj.id)

    for idx, old_uid, new_uid in moves:
        db_staleness.mark_inputs_changed(
            lproj.metamodels[idx].id,
            staleness.processes_affected_by_variable_swap(
                old_vars[old_uid], provider.variable_provider.get_variable(new_uid)
            ),
        )

    provider.delete_orphan_variables()
    return result

# -----------------------------------------------
# Layout
# -----------------------------------------------

def _row_id(varid: str, type_: str, purpose: str, supersection: str = SUPERSECTION) -> VariableInstanceParameterComponentID:
    section, key, subindex = varid.rsplit('.', 2)
    return VariableInstanceParameterComponentID(
        type = type_, purpose = purpose, supersection = supersection, section = section, key = key,
        subindex = int(subindex) if subindex.isdigit() else subindex,
    )

def group_component_id(
    varid: str,
    var_uid: str,
    supersection: str = SUPERSECTION,
    purpose: str = 'group-value',
    parameter_index: int = 0,
) -> VariableGroupComponentID:
    """The identification of an input of the editor for a group other than the focussed configuration's.

    Its type is `group-value-input`, not `single-input-config`, so that `react_to_input_change` doesn't write the focussed
    configuration's values into it. Its purpose chooses the handler: `group-value` for a parameter, and the DSA editor's
    `group-dsaboundtype`, `group-dsa-bound-lower` and `group-dsa-bound-upper`.
    """
    row = _row_id(varid, 'group-value-input', purpose, supersection)
    return VariableGroupComponentID(**{**row.as_dict(), 'parameter_index': parameter_index, 'var_uid': var_uid})

def group_value_input_id(varid: str, var_uid: str, supersection: str = SUPERSECTION, purpose: str = 'group-value', parameter_index: int = 0) -> dict:
    """The id of an input of the editor for a group other than the focussed configuration's (see `group_component_id`)."""
    return group_component_id(varid, var_uid, supersection, purpose, parameter_index).as_dict()

def create_group_move_request_store(param_id: VariableInstanceParameterComponentID) -> dcc.Store:
    """Create the store of a row to which the browser writes a move: `{'mm_index', 'target'}`.

    `mm_index` is the index of the configuration, or `all`; `target` the id of a Variable, or `NEW_VARIABLE`.

    Args:
        param_id: Identification of the variable parameter that the row edits.

    Returns:
        The store.
    """
    store_id = VariableInstanceParameterComponentID(**{**param_id.as_dict(), 'type': 'group-move-request', 'purpose': 'move'})
    return dcc.Store(id = store_id.as_dict())

def _icon_button(idx: int, is_focussed: bool) -> html.Button:
    return html.Button(
        html.I(className = ' '.join([
            get_icon(f'config-{idx+1}', style_name = 'raw'), ICON_COLOUR_CLASSES[idx % len(ICON_COLOUR_CLASSES)]
        ])),
        type = 'button',
        className = 'group-editor-icon' + (' focussed' if is_focussed else ''),
        title = f'Config {idx+1}' + (' (focussed)' if is_focussed else ''),
        # Dragged to a row as well as clicked to move (assets/group_editor.js)
        draggable = 'true',
        **{
            'data-mm-index': str(idx),
            'aria-label': f'Select Config {idx+1} to move',
            'aria-pressed': 'false',
        },
    )

def _insert_button(target: str, label: str) -> html.Button:
    return html.Button(
        html.I(className = 'bi bi-box-arrow-in-down'),
        type = 'button',
        className = 'group-editor-insert',
        title = f'Move here',
        **{'data-target': target, 'data-label': label, 'aria-label': f'Move here: {label}'},
    )

def create_group_editor_contents(varid: str, active_project_id: str, project_provider: NewsegsProjectProviderInterface) -> list:
    """Create the group editor of a variable: a row for each group and one for a new value.

    Rows are ordered by their lowest configuration, so they don't move when the focus changes. The focussed group's value
    is edited in the main input, so it has no input here.

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
    if len(lproj.metamodels) <= 1 or not groups:
        return []
    lvars = {x.id: x for x in provider.variable_provider.get_lightweight_variable([cast(str, x.var_uid) for x in groups])}
    focussed_index = lproj.focussed_metamodel_index

    rows = []
    for group in groups:
        var_uid = cast(str, group.var_uid)
        lvar = lvars[var_uid]
        label = format_variable_value(lvar)
        is_focussed_group = focussed_index in group.metamodel_indices
        # Arrays are lists when read from the database; one of a single value is edited as a number
        raw_value = np.asarray(lvar.raw_parameter_0)
        is_scalar = raw_value.size == 1
        if is_focussed_group or not is_scalar:
            value = html.Span(f'{label} (edit above)' if is_focussed_group else label, className = 'group-editor-value-text')
        else:
            configs = ', '.join(str(i+1) for i in group.metamodel_indices)
            value = html.Label([
                html.Span(f'Value used by Config {configs}', className = 'visually-hidden'),
                dbc.Input(
                    id = group_value_input_id(varid, var_uid),
                    type = 'number',
                    value = raw_value.item(),
                    min = lvar.interface_min,
                    max = lvar.interface_max,
                    step = 'any',
                    debounce = True,
                    size = 'sm',
                    className = 'group-editor-value-input',
                ),
            ])
        rows.append(create_group_row(
            [html.Div(value, className = 'group-editor-value')],
            group, focussed_index, label, len(groups),
        ))

    return create_group_editor_frame(varid, SUPERSECTION, [html.Span('Value'), html.Span('Group')], rows)

def create_group_row(cells: list, group: VariableGroup, focussed_index: int, label: str, n_groups: int, className: str = ''):
    """Create a row of a group editor: its cells, then the group's configuration icons and its actions.

    Args:
        cells: The cells of the row: the group's values and settings.
        group: The group.
        focussed_index: Index of the focussed configuration.
        label: Short description of the group's value, for the confirmations and labels of buttons.
        n_groups: The number of groups of the variable; "Use for all" is offered when there are several.
        className: Further classes of the row.

    Returns:
        The row.
    """
    var_uid = cast(str, group.var_uid)
    actions = [_insert_button(var_uid, label)]
    if n_groups > 1:
        actions.append(html.Button(
            html.I(className = 'bi bi-arrows-angle-expand'),
            type = 'button',
            className = 'group-editor-all',
            title = 'Use for all',
            **{'data-target': var_uid, 'data-label': label, 'aria-label': f'Use {label} for all configurations'},
        ))
    is_focussed_group = focussed_index in group.metamodel_indices
    return html.Div(
        [
            *cells,
            # Wraps below the cells as one, when it doesn't fit beside them
            html.Div([
                html.Div([_icon_button(i, i == focussed_index) for i in group.metamodel_indices], className = 'group-editor-icons'),
                html.Div(actions, className = 'group-editor-actions'),
            ], className = 'group-editor-side'),
        ],
        className = ' '.join(x for x in ('group-editor-row', 'focussed' if is_focussed_group else '', className) if x),
        **{'data-var-uid': var_uid, 'data-label': label, 'data-size': str(len(group.metamodel_indices))},
    )

def create_group_editor_frame(varid: str, supersection: str, head: list, rows: list) -> list:
    """Create a group editor from its rows: with a heading, the row for a new Variable and the confirmation.

    Args:
        varid: Id of the variable.
        supersection: The supersection of the row (e.g. `deterministic`, `dsa`), whose move request store it writes to.
        head: The headings of the columns.
        rows: The rows of the groups (see `create_group_row`).

    Returns:
        The children of the row's `input-group-editor` container.
    """
    # Shown only while a configuration is selected to be moved, or dragged (assets/group_editor.js)
    new_row = html.Div(
        [
            html.Div(html.Span('New Variable', className = 'group-editor-value-text'), className = 'group-editor-value'),
            html.Div([
                html.Div(html.Span('Drop here', className = 'group-editor-drop-label'), className = 'group-editor-icons'),
                html.Div([_insert_button(NEW_VARIABLE, 'a new Variable')], className = 'group-editor-actions'),
            ], className = 'group-editor-side'),
        ],
        className = 'group-editor-row new-value',
        **{'data-var-uid': NEW_VARIABLE},
    )
    store_id = create_group_move_request_store(_row_id(varid, 'group-move-request', 'move', supersection)).id
    return [html.Div(
        [
            html.Div(head, className = 'group-editor-head'),
            *rows,
            new_row,
            html.Div(
                [
                    html.Span(className = 'group-editor-confirm-text'),
                    html.Button('Confirm', type = 'button', className = 'btn btn-sm btn-danger group-editor-confirm-yes'),
                    html.Button('Cancel', type = 'button', className = 'btn btn-sm btn-outline-secondary group-editor-confirm-no'),
                ],
                className = 'group-editor-confirm',
                hidden = True,
                role = 'alert',
            ),
        ],
        className = f'group-editor group-editor-{supersection}',
        **{'data-move-store': json.dumps(store_id, sort_keys = True, separators = (',', ':'))},
    )]

register_input_editor_content_creator(SUPERSECTION, None, 'default')(create_group_editor_contents)

# -----------------------------------------------
# Handlers
# -----------------------------------------------

def _redraw_editor(triggered_id: dict, calling_dict: dict, active_project_id: str, project_provider, return_dict: dict):
    """Rebuild the row's editor, which is open since it was used"""
    for idx, editor_id in enumerate(calling_dict.get('editor_ids', [])):
        if all(editor_id.get(k) == triggered_id.get(k) for k in ('section', 'key', 'subindex', 'supersection')):
            app_state = calling_dict.get('app_state')
            model_type = json.loads(app_state).get('model_type', 'default') if app_state else 'default'
            creator = get_input_editor_content_creator(editor_id['supersection'], editor_id['section'], model_type)
            return_dict['editor_children'][idx] = creator(make_varid(**triggered_id), active_project_id, project_provider)

def _focussed_input_value(id: dict, var: FullLightweightVariable) -> Any:
    """The value of an input of the focussed configuration's row, from its Variable, or `no_update` for others"""
    match id['supersection'], id['purpose']:
        case _, 'parameter':
            value = (var.raw_parameter_0, var.raw_parameter_1)[id['parameter_index']]
            if isinstance(value, (list, tuple, np.ndarray)):
                value = np.asarray(value).flat[id['vector_location']]
            return value
        case 'dsa', 'bound-lower':
            return var.dsa_lower
        case 'dsa', 'bound-upper':
            return var.dsa_upper
        # An unset optimisation bound is the limit of the input (see Variable.get_optim_bounds)
        case 'optim', 'bound-lower':
            return var.optim_min if var.optim_min is not None else var.interface_min
        case 'optim', 'bound-upper':
            return var.optim_max if var.optim_max is not None else var.interface_max
        case 'optim', 'plot-intervals':
            return var.optim_plot_intervals
    return no_update

def _feed_back_focussed(triggered_id, input_ids, header_ids, trigger_ids, lproj, provider, return_dict, now):
    """Show the focussed configuration's new Variable in every part of its row: on the DSA page, the DSA and the
    optimisation inputs, toggles and styling, as well as the headers and triggers"""
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]
    varid = make_varid(**triggered_id)
    var = cast(FullLightweightVariable, provider.variable_provider.get_full_lightweight_variable(lmm.variables[varid]))
    for idx, id in enumerate(input_ids):
        return_dict['input_values'][idx] = _focussed_input_value(id, var)

    # The toggles and the optimisation row's styling, which a Variable of other selections changes
    grouping = ctx.outputs_grouping if ctx.using_outputs_grouping else {}
    selected = {'dsa-active': var.dsa_selected, 'toggle-optim-active': var.optim_selected}
    for idx, output in enumerate(grouping.get('toggle_values', [])):
        if output['id']['purpose'] in selected:
            return_dict['toggle_values'][idx] = selected[output['id']['purpose']]
    for idx, output in enumerate(grouping.get('optim_container_class', [])):
        return_dict['optim_container_class'][idx] = (
            'optim-input-single-value-block' + ('' if var.optim_selected else ' deselected')
        )

    for idx, id in enumerate(header_ids):
        try:
            creator = get_single_input_header_content_creator(id['supersection'], id['section'], lmm.model.model_type)
        except KeyError:
            creator = None
        if creator:
            return_dict['header_children'][idx] = creator(varid, var)
    for idx in range(len(trigger_ids)):
        return_dict['trigger_data'][idx] = now

@register_input_handler('move', 'group-move-request')
def _move_to_group(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
):
    request = callback_utils.get_triggered_value()
    if not isinstance(request, dict):
        raise PreventUpdate

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(active_project_id)
    varid = make_varid(**triggered_id)
    mm_index = request.get('mm_index')
    try:
        indices = list(range(len(lproj.metamodels))) if mm_index == 'all' else [int(mm_index)] # pyright: ignore[reportArgumentType]
        moves = move_metamodels_to_group(provider, lproj, varid, indices, str(request.get('target')))
    except (TypeError, ValueError) as e:
        # e.g. from an editor drawn before another tab changed the project: show it as it is
        logger.warning('Rejected a move of %s: %s', varid, e)
        _redraw_editor(triggered_id, calling_dict, active_project_id, project_provider, return_dict)
        return return_dict

    logger.info('Moved configurations %s of %s; removed %s; created %s', moves.moved, varid, moves.removed, moves.created)
    now = time.time_ns()
    if lproj.focussed_metamodel_index in moves.moved:
        _feed_back_focussed(triggered_id, input_ids, header_ids, trigger_ids, lproj, provider, return_dict, now)
    if moves.moved:
        _signal_summary_refresh(return_dict, now)
    _redraw_editor(triggered_id, calling_dict, active_project_id, project_provider, return_dict)
    return return_dict

@register_input_handler('group-value', 'group-value-input')
def _set_group_value(
    triggered_id: dict,
    input_ids: list[dict[str, str]],
    header_ids: list[dict[str, str]],
    trigger_ids: list[dict[str, str]],
    calling_dict: dict,
    active_project_id: str,
    project_provider: NewsegsProjectProviderInterface,
    return_dict: dict[str, Any],
):
    new_val = callback_utils.get_triggered_value()
    if new_val is None:
        raise PreventUpdate

    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(active_project_id)
    varid = make_varid(**triggered_id)
    var_uid = triggered_id['var_uid']
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]

    if var_uid == lmm.variables.get(varid):
        # The focussed group, from an editor drawn before the focus changed: as an edit of the main input
        return update_single_parameter(
            triggered_id, input_ids, header_ids, trigger_ids, calling_dict, active_project_id, project_provider,
            return_dict, new_val = new_val,
        )

    if not any(x.variables.get(varid) == var_uid for x in lproj.metamodels):
        # e.g. another tab has moved its configurations
        logger.warning('Rejected a value of %s for %s, which no configuration uses', varid, var_uid)
    else:
        var = provider.variable_provider.get_variable(var_uid)
        update_ok, *_ = apply_parameter_change(
            provider, lproj, var, new_val,
            parameter_index = triggered_id.get('parameter_index', 0),
            vector_location = triggered_id.get('vector_location', 0),
        )
        if update_ok:
            _signal_summary_refresh(return_dict, time.time_ns())

    # Shows the saved value, which is the old one if it was rejected
    _redraw_editor(triggered_id, calling_dict, active_project_id, project_provider, return_dict)
    return return_dict
