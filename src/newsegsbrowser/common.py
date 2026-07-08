import inspect
import time

from collections.abc import Sequence
from dataclasses import KW_ONLY, dataclass, field
from dataclasses import asdict as dc_asdict
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

def create_numeric_input_compound_key(
    type_id: str,
    key: str,
    section: str | None = None,
    subindex: int = 0,
    parameter_index: int = 0,
    vector_location: int = 0,
    placeholder: int | float | str = 0.0,
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
    
    return dbc.Input(
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
    return html.Div([
        html.H5(
            [
                get_icon(icon_name, None, 'default'),
                html.Span(label+":", className='mr-3')
            ],
            style={'display':'inline'}
        ),
        create_numeric_input_compound_key(
            type_id,
            key,
            section,
            subindex,
            parameter_index,
            vector_location,
            placeholder,
            value,
            min,
            max,
            step
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

@dataclass
class Action:
    """
    Class for dispatching actions
    """
    
    _: KW_ONLY
    type: str
    time: float = field(default_factory = time.time)
    debounce: bool = True

    @classmethod
    def from_dict(cls, env):      
        return cls(**{
            k: v for k, v in env.items() 
            if k in inspect.signature(cls).parameters
        })
    
    def as_dict(self):
        return dc_asdict(self)

@dataclass
class VariableAction(Action):
    metamodel_id: str
    section: str
    key: str
    subindex: int = 0
    _: KW_ONLY
    type: str = field(init = False)
    model_class: Literal['model', 'finance'] = 'model'

@dataclass
class ModelConfigInterfaceAction(VariableAction):
    parameter_index: int = 0
    vector_location: int = 0

    def __post_init__(self):
        match self.model_class:
            case 'model':
                self.type = 'model_config_interface_update'
            case 'finance':
                self.type = 'finance_config_interface_update'

@dataclass
class DSAImpactingInterfaceAction(VariableAction):
    
    action_key: str = 'dsa_input_change'
    bounds_type_change: bool = False
    selected_status_change: bool = False
    _: KW_ONLY
    type: str = 'dsa_impacting_interface_action'

@dataclass
class PSAImpactingInterfaceAction(VariableAction):
    
    action_key: str = 'psa_input_change'
    selected_status_change: bool = False
    _: KW_ONLY
    type: str = 'psa_impacting_interface_action'

@dataclass
class MetaModelProcessAction(Action):
    metamodel_id: str = ''
    type: Literal[ # pyright: ignore[reportIncompatibleVariableOverride]
        'result_update_request',
        'dsa_run_request',
        'psa_run_request'
    ]
    action_key: str = field(init = False)

    def __post_init__(self):
        match self.type:
            case 'result_update_request':
                self.action_key = 'result_update'
            case 'dsa_run_request':
                self.action_key = 'dsa_run'
            case 'psa_run_request':
                self.action_key = 'psa_run'
            case _:
                self.action_key = ''

@dataclass
class ModelRunAction(MetaModelProcessAction):
    metamodel_id: str = ''
    model_id: str = ''
    type: str = 'model_run_request' # pyright: ignore[reportIncompatibleVariableOverride]
    action_key: str = 'model_run'

    def __post_init__(self):
        """
        Override the setting of MetaModelProcessAction action key
        """
        return

@dataclass
class FinanceRunAction(ModelRunAction):
    type: str = 'finance_run_request'
    action_key: str = 'finance_run'
    finance_id: str = ''

@dataclass
class ResultUpdateAction(MetaModelProcessAction):
    type: str = 'result_update_request' # pyright: ignore[reportIncompatibleVariableOverride]

@dataclass
class DSARunAction(MetaModelProcessAction):
    type: str = 'dsa_run_request' # pyright: ignore[reportIncompatibleVariableOverride]

@dataclass
class PSARunAction(MetaModelProcessAction):
    type: str = 'psa_run_request' # pyright: ignore[reportIncompatibleVariableOverride]
    samples: int = 1000
    return_draws: bool = False
    seed: float | None = None

def model_interface_action(
    **kwargs
):
    return ModelConfigInterfaceAction.from_dict(kwargs)

def finance_interface_action(
    **kwargs
):
    kwargs.update({
        'model_class': 'finance'
    })
    return ModelConfigInterfaceAction.from_dict(kwargs)

def dsa_impacting_interface_action(
    **kwargs
):
    """
    Action to raise if an interface change has impacted a DSA value.

    Primary outcome is the update of DSA headers.
    """
    return DSAImpactingInterfaceAction.from_dict(kwargs)

def psa_impacting_interface_action(
    **kwargs
):
    """
    Action to raise if an interface change has impacted a PSA value.

    Primary outcome is the update of PSA headers.
    """
    return PSAImpactingInterfaceAction.from_dict(kwargs)

def model_run_interface_action(
    **kwargs
):
    return ModelRunAction.from_dict(kwargs)

def result_update_interface_action(
    **kwargs
):
    return ResultUpdateAction.from_dict(kwargs)

def model_run_request(
    **kwargs
):
    return ModelRunAction.from_dict(kwargs)

def finance_run_request(
   **kwargs
):
    return FinanceRunAction.from_dict(kwargs)


def metamodel_process_request(
    **kwargs
):
    return MetaModelProcessAction.from_dict(kwargs)

def dsa_run_request(
    **kwargs
):
    return DSARunAction.from_dict(kwargs)

def psa_run_request(
    **kwargs
):
    return PSARunAction.from_dict(kwargs)
