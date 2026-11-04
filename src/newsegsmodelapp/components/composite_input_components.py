"""Components which require both input_compoents and variable_dash_component"""

import dash
from dash import html
from dash_bootstrap_components._components.Row import Row as dbc_Row

from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelapp.components.group_editor import create_group_move_request_store
from newsegsmodelapp.components.input_components import (
    create_blank_single_input_header_element,
    create_input_group_config_update_trigger,
    create_lazy_input_details,
    create_numeric_card_variable_parameter_input,
    create_variable_sharing_summary,
    create_variable_sharing_summary_contents,
    create_variable_summary_refresh_trigger,
)
from newsegsmodelapp.components.variable_dash_component.vdc_dsa import create_dsa_input
from newsegsmodelapp.components.variable_dash_component.vdc_psa import create_psa_input
from newsegsmodelapp.components.variable_dash_component.vdc_optim import create_optim_input
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsproject.lightweightnewsegsproject import LightweightNewsegsProject


def generic_create_deterministic_input_container_contents(
    section: str,
    lproj: LightweightNewsegsProject,
    lmm: LightweightNewsegsMetaModel,
    variableprovider: FromDatabaseVariableProvider,
) -> list[dash.development.base_component.Component]:
    """Create the inputs of a section for the deterministic run of a metamodel.

    One input for each variable of the metamodel whose interface section is `section`, with a summary of how the
    configurations of the project share it. The variables of every configuration are fetched in one call.

    Args:
        section: The section.
        lproj: The lightweight project.
        lmm: The lightweight metamodel.
        variableprovider: Provider of variables.

    Returns:
        List of components.
    """
    contents = []
    var_uids = list(dict.fromkeys(uid for x in lproj.metamodels for uid in x.variables.values()))
    lwvars = {x.id: x for x in variableprovider.get_lightweight_variable(var_uids)}
    for varid, var_uid in lmm.variables.items():
        lvar = lwvars[var_uid]
        if lvar.interface_section == section: # and lvar.configuration_show: # TODO: Add configuration_show into lighweight variable
            #if not isinstance(var, variable.ScalarVariable):
            #    raise TypeError(f'Cannot handle variables of type {type(var)}')
            # Create an input
            paramid = VariableInstanceParameterComponentID.from_lightweight_variable(
                lvar,
                type = 'single-input-config',
                supersection = 'deterministic',
            )
            sharing_summary = create_variable_sharing_summary(
                paramid, create_variable_sharing_summary_contents(lproj, varid, lwvars)
            )
            if len(lproj.metamodels) > 1:
                # Opening the summary builds the group editor, which edits and moves between the groups
                sharing_summary = html.Div([
                    create_lazy_input_details(
                        [sharing_summary, html.Span('Hide groups', className = 'group-editor-close-label')],
                        paramid, className = 'group-editor-details',
                    ),
                    create_group_move_request_store(paramid),
                ])
            contents.append(
                dbc_Row([
                    create_blank_single_input_header_element(paramid),
                    create_numeric_card_variable_parameter_input(
                        lvar.icon_name,
                        f'{lvar.label} ({lvar.unit})',
                        paramid,
                        value = lvar.raw_parameter_0, # pyright: ignore[reportArgumentType]
                        #value = var.get_deterministic_value(), # pyright: ignore[reportArgumentType]
                        min = lvar.interface_min,
                        max = lvar.interface_max,
                        step = lvar.interface_step if lvar.interface_step else 1,
                        sharing_summary = sharing_summary,
                    ),
                    create_input_group_config_update_trigger(paramid), # pyright: ignore[reportCallIssue]
                    create_variable_summary_refresh_trigger(paramid),
                ]
                ) # type: ignore
            )

    return contents

def generic_create_dsa_input_container_contents(
    lmm: LightweightNewsegsMetaModel,
    variable_provider: FromDatabaseVariableProvider
) -> list[dash.development.base_component.Component]:
    """Create the inputs for the deterministic sensitivity analysis of a metamodel.

    One DSA input for each variable of the metamodel.

    Args:
        lmm: The lightweight metamodel.
        variable_provider: Provider of variables.

    Returns:
        List of components.
    """
    contents = []
    vars = variable_provider.get_full_lightweight_variable(list(lmm.variables.values()))
    for var in vars:
        contents.append(create_dsa_input(var))

    return contents

def generic_create_psa_input_container_contents(
    lmm: LightweightNewsegsMetaModel,
    variable_provider: FromDatabaseVariableProvider
) -> list[dash.development.base_component.Component]:
    """Create the inputs for the probabilistic sensitivity analysis of a metamodel.

    One PSA input for each variable of the metamodel.

    Args:
        lmm: The lightweight metamodel.
        variable_provider: Provider of variables.

    Returns:
        List of components.
    """
    contents = []
    vars = variable_provider.get_full_lightweight_variable(list(lmm.variables.values()))
    for var in vars:
        contents.append(create_psa_input(var))

    return contents

def generic_create_optim_input_container_contents(
    mm: NewsegsMetaModel,
) -> list[dash.development.base_component.Component]:
    """Create the inputs for the optimisation of a metamodel.

    One optimisation input for each variable of the metamodel.

    Args:
        mm: The metamodel.

    Returns:
        List of components.
    """
    contents = []
    for var in mm.variables.values():
        contents.append(create_optim_input(var))

    return contents
