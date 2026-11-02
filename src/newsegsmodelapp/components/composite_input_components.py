"""Components which require both input_compoents and variable_dash_component"""

import dash
from dash_bootstrap_components._components.Row import Row as dbc_Row

from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelapp.components.input_components import create_blank_single_input_header_element, create_input_group_config_update_trigger, create_numeric_card_variable_parameter_input, get_variable_sharing_status
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

    One input for each variable of the metamodel whose interface section is `section`.

    Args:
        section: The section.
        lproj: The lightweight project.
        lmm: The lightweight metamodel.
        variableprovider: Provider of variables.

    Returns:
        List of components.
    """
    contents = []
    var_uids = list(lmm.variables.values())
    lwvars = variableprovider.get_lightweight_variable(var_uids)
    for varid, lvar in zip(lmm.variables.keys(), lwvars):
        if lvar.interface_section == section: # and lvar.configuration_show: # TODO: Add configuration_show into lighweight variable
            #if not isinstance(var, variable.ScalarVariable):
            #    raise TypeError(f'Cannot handle variables of type {type(var)}')
            # Create an input
            paramid = VariableInstanceParameterComponentID.from_lightweight_variable(
                lvar,
                type = 'single-input-config',
                supersection = 'deterministic',
            )
            var_sharing_status = get_variable_sharing_status(lproj, lmm, varid) # pyright: ignore[reportArgumentType]
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
                        status_text= var_sharing_status[0], 
                        status_colour = var_sharing_status[1],
                    ),
                    create_input_group_config_update_trigger(paramid), # pyright: ignore[reportCallIssue]
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
