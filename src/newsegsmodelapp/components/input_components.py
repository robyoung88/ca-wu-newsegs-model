import copy
import time
from typing import Any, Optional

from dash import dcc, html, no_update
from dash_bootstrap_components._components.Input import Input as dbc_Input # Bit of a faff to get around the pyright behaviour https://github.com/microsoft/pyright/issues/3131
from dash_bootstrap_components._components.Button import Button as dbc_Button
from dash.exceptions import PreventUpdate
import numpy as np

from useful_types import SequenceNotStr

from newsegsmodelapp.components.constants import CONFIGURATION_UPDATE_TRIGGER_ID, VARIABLE_PARAMETER_KEYS
from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelapp.newsegsbrowser.icons import get_icon
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
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
    reset_button = True
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
                html.Span(label+":", className='mr-3')
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
    proj = project_provider.get_project(active_project_id)
    mm = proj.get_focussed_metamodel()
    variable_keys = {k: triggered_id.get(k) for k in VARIABLE_PARAMETER_KEYS}

    input_returns: list[Any] = [no_update] * len(input_ids)
    header_returns: list[Any] = [no_update] * len(header_ids)
    trigger_returns: list[Any] = [no_update] * len(trigger_ids)

    now = time.time_ns()
    
    update_ok, deterministic_changed, dsa_changed, psa_changed, raw_params = mm.update_variable_from_interface(
        value = new_val, **variable_keys
    )

    # Feed back current parameters
    for idx, id in enumerate(input_ids):
        if id['purpose'] == 'parameter':
            pi = id['parameter_index']
            new_param = raw_params[pi]
            if not isinstance(new_param, np.ndarray):
                input_returns[idx] = new_param
            else:
                vi = id['vector_location']
                new_val = new_param.flat[vi]
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
    param_id: VariableInstanceParameterComponentID
):
    trigger_id = copy.copy(param_id)
    trigger_id.type = 'input-group-config-update-trigger'
    trigger_id.purpose = 'trigger'
    return dcc.Store(id = trigger_id.as_dict())

