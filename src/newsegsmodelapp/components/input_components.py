import copy

from dash import dcc, html
from dash_bootstrap_components._components.Input import Input as dbc_Input # Bit of a faff to get around the pyright behaviour https://github.com/microsoft/pyright/issues/3131
from dash_bootstrap_components._components.Button import Button as dbc_Button

from useful_types import SequenceNotStr

from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID
from newsegsmodelapp.newsegsbrowser.icons import get_icon
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsvariable import variable

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

def create_value_reset_button(
    param_id: VariableInstanceParameterComponentID
):
    button_id = copy.copy(param_id)
    button_id.type = 'value-reset-button'
    
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

def create_value_set_default_button(
    param_id: VariableInstanceParameterComponentID
):
    button_id = copy.copy(param_id)
    button_id.type = 'value-set-default-button'
    
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
