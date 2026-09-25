"""Components which require both input_compoents and variable_dash_component"""

import dash
from dash_bootstrap_components._components.Row import Row as dbc_Row

from newsegsmodelapp.components.input_components import create_blank_single_input_header_element, create_input_group_config_update_trigger, create_numeric_card_variable_parameter_input, get_variable_sharing_status
from newsegsmodelapp.components.variable_dash_component.vdc_dsa import create_dsa_input
from newsegsmodelapp.components.variable_dash_component.vdc_psa import create_psa_input
from newsegsmodelapp.components.variable_dash_component.vdc_optim import create_optim_input
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import make_varid
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsvariable import variable


def generic_create_deterministic_input_container_contents(
    section: str,
    proj: NewsegsProject,
    mm: NewsegsMetaModel,
) -> list[dash.development.base_component.Component]:
    contents = []
    for varid, var in mm.variables.items():
        if var.interface_section == section and var.configuration_show:
            if not isinstance(var, variable.ScalarVariable):
                raise TypeError(f'Cannot handle variables of type {type(var)}')
            # Create an input
            paramid = VariableInstanceParameterComponentID.from_variable(
                var,
                type = 'single-input-config',
                supersection = 'deterministic',
            )
            var_sharing_status = get_variable_sharing_status(proj, mm, varid) # pyright: ignore[reportArgumentType]
            contents.append(
                dbc_Row([
                    create_blank_single_input_header_element(paramid),
                    create_numeric_card_variable_parameter_input(
                        var.icon_name,
                        f'{var.label} ({var.unit})',
                        paramid,
                        value = var.get_deterministic_value(), # pyright: ignore[reportArgumentType]
                        min = var.interface_min,
                        max = var.interface_max,
                        step = var.interface_step if var.interface_step else 1,
                        status_text= var_sharing_status[0], 
                        status_colour = var_sharing_status[1],
                    ),
                    create_input_group_config_update_trigger(paramid), # pyright: ignore[reportCallIssue]
                ]
                ) # type: ignore
            )

    return contents

def generic_create_dsa_input_container_contents(
    mm: NewsegsMetaModel,
) -> list[dash.development.base_component.Component]:
    contents = []
    for var in mm.variables.values():
        contents.append(create_dsa_input(var))

    return contents

def generic_create_psa_input_container_contents(
    mm: NewsegsMetaModel,
) -> list[dash.development.base_component.Component]:
    contents = []
    for var in mm.variables.values():
        contents.append(create_psa_input(var))

    return contents

def generic_create_optim_input_container_contents(
    mm: NewsegsMetaModel,
) -> list[dash.development.base_component.Component]:
    contents = []
    for var in mm.variables.values():
        contents.append(create_optim_input(var))

    return contents
