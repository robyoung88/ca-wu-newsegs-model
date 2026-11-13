"""The groups of an input on the PSA page: a summary line with every group's mean and SD (or value), and the group
editor, in which every group's parameters can be edited and configurations moved between groups.

As on the DSA page (see `dsa_group_editor`), the editor's focussed row keeps the ids of the focussed configuration's
inputs, and the other groups' inputs are `group-value-input`s carrying their Variable's id, handled by
`group_editor`'s `group-value` handler, which saves through `input_components.apply_parameter_change` and redraws the
editor with the saved values (so a rejected value returns to the saved one). The PSA's selection is kept in sync
across Variables, and its project settings (samples, seed, draws) are not grouped.
"""
from typing import Mapping, Sequence, cast

from dash import html

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.components.group_editor import create_group_editor_frame, create_group_row, group_component_id
from newsegsmodelapp.components.input_components import _config_icons, get_variable_groups
from newsegsmodelapp.components.variable_dash_component import vdc
from newsegsmodelapp.registers import register_input_editor_content_creator
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

SUPERSECTION = 'psa'

def _is_constant(var: FullLightweightVariable) -> bool:
    return vdc.psa_parameter_labels(var.distribution) == ['Value']

def _formatted(var: FullLightweightVariable, value) -> str:
    """A value as the PSA header shows it (see `vdc.create_psa_header`), or `-` when it isn't known"""
    if value is None:
        return '-'
    if 'constant' in var.distribution or var.formatter_dp is None:
        return vdc._autoformat(value)
    return vdc._default_formatter_scalar(var.formatter_dp)(value)

def mean_and_sd(var: FullLightweightVariable) -> str:
    """A Variable's mean ± SD, or its value for a constant, as the PSA page shows it."""
    if _is_constant(var):
        return _formatted(var, var.last_deterministic_value)
    return f'{_formatted(var, var.last_deterministic_value)} ± {_formatted(var, var.last_std)}'

def confidence_interval(var: FullLightweightVariable) -> str:
    """A Variable's 95% confidence interval, or `-` when it isn't known."""
    if var.psa_ci_lower is None or var.psa_ci_upper is None:
        return '-'
    return f'{_formatted(var, var.psa_ci_lower)}, {_formatted(var, var.psa_ci_upper)}'

def distributions_differ(variables: Sequence[FullLightweightVariable]) -> bool:
    """Whether Variables have different distributions; not expected, but possible from an uploaded configuration."""
    return len({x.distribution for x in variables}) > 1

def _differs(variables: Sequence[FullLightweightVariable]) -> bool:
    """Whether Variables differ in distribution or SD"""
    return distributions_differ(variables) or len({repr(x.last_std) for x in variables}) > 1

def count_variables_with_different_distributions_or_sds(
    lproj: LightweightNewsegsProject, variables: Mapping[str, FullLightweightVariable]
) -> int:
    """The number of the variables shown on the PSA page whose groups have different distributions or SDs.

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
        if group_vars and group_vars[0].psa_show and _differs(group_vars):
            n += 1
    return n

def create_psa_sharing_summary_contents(
    proj: LightweightNewsegsProject,
    varid: str,
    variables: Mapping[str, FullLightweightVariable],
) -> list:
    """Create what the PSA row's summary line shows: nothing unless there are several groups; otherwise each group's
    configurations and mean ± SD (or value), and `≠ distribution` if their distributions differ.

    The confidence intervals are left out, to keep the line short; the header and the editor show them.

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
        line.append(html.Span([*_config_icons(group.metamodel_indices), ' ', mean_and_sd(var)], className = class_name))
    if distributions_differ([variables[cast(str, x.var_uid)] for x in groups]):
        line.append(html.Span('≠ distribution', className = 'psa-distribution-differs', title = 'The groups have different distributions'))
    return line

# -----------------------------------------------
# The editor
# -----------------------------------------------

def _cells(varid: str, var: FullLightweightVariable, is_focussed: bool, show_distribution: bool) -> list:
    id_for = None if is_focussed else (lambda purpose, index = 0: group_component_id(varid, var.id, SUPERSECTION, purpose, index))
    cells = []
    if show_distribution:
        cells.append(html.Div(var.distribution.title(), className = 'psa-group-distribution'))
    cells.extend(html.Div(x, className = 'group-editor-value psa-group-parameter') for x in vdc.create_psa_input_parameters(var, id_for))
    if not _is_constant(var):
        cells.append(html.Div(confidence_interval(var), className = 'psa-group-ci'))
    return cells

def _head(variables: Sequence[FullLightweightVariable], show_distribution: bool) -> list:
    constants = [_is_constant(x) for x in variables]
    head = [html.Span('Distribution')] if show_distribution else []
    if all(constants):
        head.append(html.Span('Value'))
    elif not any(constants):
        head.extend([html.Span('Mean'), html.Span('SD'), html.Span('95% CI')])
    else:
        head.extend([html.Span('Parameters'), html.Span('95% CI')])
    return head + [html.Span('Group')]

def create_psa_group_editor_contents(varid: str, active_project_id: str, project_provider: NewsegsProjectProviderInterface) -> list:
    """Create the PSA row's editor: the distribution, and a row for each group with its parameters, confidence
    interval and configurations.

    The distribution is shown once above the rows, or as a column when the groups' distributions differ. A constant has
    a Value, and no confidence interval. The focussed configuration's row holds its usual inputs; a project with one
    configuration has that row alone.

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
    group_vars = [variables[cast(str, x.var_uid)] for x in groups]
    focussed_index = lproj.focussed_metamodel_index
    show_distribution = distributions_differ(group_vars)
    distribution_line = [] if show_distribution else [html.Div(vdc.create_psa_distribution_component(group_vars[0]), className = 'distribution-label')]

    if len(lproj.metamodels) <= 1:
        row = html.Div(_cells(varid, group_vars[0], True, False), className = 'group-editor-row psa-group-row')
        return [html.Div(distribution_line + [row], className = 'group-editor group-editor-psa')]

    rows = []
    for group, var in zip(groups, group_vars):
        is_focussed = focussed_index in group.metamodel_indices
        rows.append(create_group_row(
            _cells(varid, var, is_focussed, show_distribution), group, focussed_index, mean_and_sd(var), len(groups),
            className = 'psa-group-row',
        ))
    frame = create_group_editor_frame(varid, SUPERSECTION, _head(group_vars, show_distribution), rows)
    frame[0].children = distribution_line + list(frame[0].children)
    return frame

register_input_editor_content_creator(SUPERSECTION, None, 'default')(create_psa_group_editor_contents)
