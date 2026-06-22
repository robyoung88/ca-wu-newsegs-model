from collections.abc import Sequence
from typing import Literal
from typing import TypeVar
from typing import overload
from typing import Optional
from typing import List
import datetime
import uuid

from dash import html
import dash_bootstrap_components as dbc
from useful_types import SequenceNotStr

from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance

from newsegsbrowser.icons import get_icon

def create_numeric_card_input(
    icon_name: str | SequenceNotStr[str],
    label: str,
    input_id: str
):
    return html.Div([
        html.H5([
            get_icon(icon_name, None, 'default'),
            html.Span(label+":", className='mr-3')
        ],
        style={'display':'inline'}),
        dbc.Input(id=input_id,
                  type='number',
                  placeholder=0.0,
                  debounce=True,
                  style={
                    'display':'inline-block',
                    'float':'right',
                    'width':'30%'
                  })
    ])

def create_numeric_card_input_compound_key(
    icon_name: str | SequenceNotStr[str],
    label: str,
    type_id: str,
    key: str,
    section: str | None = None,
    subindex: int = 0,
    parameter_index: int = 0,
    vector_location: int = 0,
    placeholder: int | float = 0.0,
    value: int | float | None = None,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1
):
    if section is None:
        section = 'None'
    
    input_id = {
        'type': type_id,
        'key': key,
        'section': section,
        'subindex': subindex,
        'parameter_index': parameter_index,
        'vector_location': vector_location,
    }
    if float(int(step)) == float(step):
        step = int(step)
        cn = f'dynamic-step-field step-val-{step:d}'
    else:
        cn = f'dynamic-step-field step-val-{step:f}'

    
    return html.Div([
        html.H5(
            [
                get_icon(icon_name, None, 'default'),
                html.Span(label+":", className='mr-3')
            ],
            style={'display':'inline'}
        ),
        dbc.Input(
            id = input_id,
            type = 'number',
            value = value,
            placeholder = placeholder,
            debounce = True,
            min = min,
            max = max,
            step = 'any',
            style = {
                'display':'inline-block',
                'float':'right',
                'width':'30%'
            },
            className = cn
        )
    ])

def unescape_html_icons(html_text):
    return (
        html_text
        .replace('<th>&lt;','<th><')
        .replace('"&gt;&lt;','"><')
        .replace('i&gt;', 'i>')
    )

##### Functions for app control - Actions, Queue items etc #####

def compose_configuration(
    name: str,
    mdl: newsegsmodel.NewsegsModel | str,
    fnc: newsegsfinance.NewsegsFinance | str,
    model_class: str = 'SprakeModel',
    finance_class: str = 'SprakeFinance',
) -> dict:
    """
    A 'Composed Configuration' - a named combination of a model and a finance.

    Args:
        name: A compulsory name for the configuration.
        mdl: A NewsegsModel or a model id.
        fnc: A NewsegsFinance or a finance id.
        model_class (Optional): A string giving the class of the model.
        finance_class (Optional): A string giving the class of the finance.
    """
    if isinstance(mdl, newsegsmodel.NewsegsModel):
        mdl_id = mdl.id
    else:
        mdl_id = mdl
    
    if isinstance(fnc, newsegsfinance.NewsegsFinance):
        fnc_id = fnc.id
    else:
        fnc_id = fnc
    
    rval = {
        'uuid': str(uuid.uuid4()),
        'name': name,
        'model_id': mdl_id,
        'finance_id': fnc_id,
        'model_class': model_class,
        'finance_class': finance_class,
    }
    rval['id'] = 'c-' + rval['uuid']
    
    return rval

def model_interface_action(
    metamodel_id,
    section,
    key,
    subindex,
    parameter_index,
    vector_location,
    input_time = None,
    **kwargs
):
    if input_time is None:
        input_time = datetime.datetime.now()
    return {
        'type': 'model_config_interface_update',
        'metamodel_id': metamodel_id,
        'section': section,
        'key': key,
        'subindex': subindex,
        'parameter_index': parameter_index,
        'vector_location': vector_location,
        'time': input_time.timestamp(),
    }

def finance_interface_action(
    metamodel_id,
    section,
    key,
    subindex,
    parameter_index,
    vector_location,
    input_time = None,
    **kwargs
):
    if input_time is None:
        input_time = datetime.datetime.now()
    return {
        'type': 'finance_config_interface_update',
        'metamodel_id': metamodel_id,
        'section': section,
        'key': key,
        'subindex': subindex,
        'parameter_index': parameter_index,
        'vector_location': vector_location,
        'time': input_time.timestamp(),
    }

def model_run_request(
    metamodel_id,
    model_id,
    request_time = None
):
    if request_time is None:
        request_time = datetime.datetime.now()
    return {
        'type': 'model_run_request',
        'metamodel_id': metamodel_id,
        'model_id': model_id,
        'time': request_time.timestamp()
    }

def finance_run_request(
    metamodel_id,
    finance_id,
    model_id,
    request_time = None
):
    if request_time is None:
        request_time = datetime.datetime.now()
    return {
        'type': 'finance_run_request',
        'metamodel_id': metamodel_id,
        'finance_id': finance_id,
        'model_id': model_id,
        'time': request_time.timestamp()
    }
