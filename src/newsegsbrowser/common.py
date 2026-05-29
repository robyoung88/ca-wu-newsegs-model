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

from src.newsegsmodel import newsegsmodel
from src.newsegsfinance import newsegsfinance

def flatten_mixed_list(mixed_list: Sequence[List[str] | str]) -> List[str]:
    flat_list=[]
    for item in mixed_list:
        if isinstance(item, str):
            flat_list += [item]
        else:
            flat_list += item
    return flat_list

def len_mixed_list(mixed_list: Sequence[List[str] | str]) -> List[int]:
    lens=[]
    for item in mixed_list:
        if isinstance(item, str):
            lens += [1]
        else:
            lens += [len(item)]
    return lens

T = TypeVar('T')

def repeat_list_by_index(
    l: Sequence[T], 
    repeats: int | Sequence[int]
) -> List[T]:
    if not isinstance(repeats, Sequence):
        repeats = [repeats] * len(l)
    assert len(l) == len(repeats), '`repeats` must be a scalar or same length as the list'
    olist = []
    for i in range(len(l)):
        olist.extend([l[i]] * repeats[i])
    return olist

DEFAULT_ICONS = {
    'latlon': 'bi bi-geo-alt',
    'osgb': 'bi bi-map',
    'generation': 'bi bi-lightning-charge',
    'gen-wind': 'bi bi-wind',
    'gen-pv': 'bi bi-sun',
    'storage': 'bi bi-battery-half',
    'import-export': 'bi bi-arrow-down-up',
    'consumption-building': 'bi bi-houses',
    'consumption-building-nunits': 'bi bi-houses',
    'consumption-building-hlp': 'bi bi-fire',
    'consumption-building-gfa': 'bi bi-rulers',
    'consumption-building-dhw-ref': ['bi bi-droplet', 'bi bi-thermometer-high'],
    'consumption-building-dhw-var': ['bi bi-droplet', 'bi bi-plus-slash-minus'],
    'consumption-direct': 'bi bi-plug',
    'consumption-direct-appliance': 'bi bi-lamp',
    'consumption-direct-ev': 'bi bi-ev-front',
    'consumption-direct-appliance-reduction': 'bi bi-graph-down-arrow',
    'consumption-direct-ev-anncharge': 'bi bi-ev-station',
    'consumption-direct-ev-nperunit': 'bi bi-ev-front',
    'cost': 'bi bi-cash-coin',
    'cost-recurrent': 'bi bi-arrow-repeat',
    'cost-generation': ['bi bi-cash-stack', 'bi bi-lightning-charge'],
    'cost-storage': ['bi bi-cash-stack', 'bi bi-battery-half'],
    'cost-sales': 'bi bi-receipt-cutoff',
    'cost-residents': 'bi bi-people',
    'cost-export': 'bi bi-box-arrow-up-right',
    'cost-residents-standing': 'bi bi-people',
    'cost-residents-perunit': ['bi bi-people', 'bi bi-lightning-charge'],
    'cost-import': 'bi bi-box-arrow-in-down-right',
    'cost-import-fixed': 'bi bi-cash-coin',
    'cost-import-perunit': ['bi bi-cash-coin', 'bi bi-box-arrow-in-down-right'],
    'model-settings': 'bi bi-cpu',
    'model-settings-time-horizon': 'bi bi-calendar3-range',
    'finance-settings': 'bi bi-bank',
    'finance-settings-benefit-discount' : ['bi bi-receipt-cutoff', 'bi bi-arrow-down-right'],
    'finance-settings-cost-discount' : ['bi bi-cash-stack', 'bi bi-arrow-down-right'],
    'results': 'bi bi-bar-chart',
    'add-config': 'bi bi-plus-circle',
    'config-1': 'bi bi-1-circle-fill',
    'config-2': 'bi bi-2-circle-fill',
    'config-3': 'bi bi-3-circle-fill',
    'config-4': 'bi bi-4-circle-fill',
    'config-duplicate': 'bi bi-copy',
    'config-remove': 'bi bi-dash-circle',
    'config-focus': 'bi bi-crosshair',
    'config-download': 'bi bi-box-arrow-down',
    'config-upload': 'bi bi-box-arrow-in-up',
    'results-download': 'bi bi-table',
    'show-graph': 'bi bi-graph-up',
}

@overload
def get_icon(
    icon_name: str,
    icon_class: Optional[SequenceNotStr[str] | str]=...,
    style_name: Literal['default', 'unpadded']=...,
) -> html.I:
    ...

@overload
def get_icon(
    icon_name: str,
    *,
    style_name: Literal['default', 'unpadded']=...,
) -> html.I:
    ...

@overload
def get_icon(
    icon_name: str,
    icon_class: Optional[SequenceNotStr[str] | str],
    style_name: Literal['raw'],
) -> str:
    ...

@overload
def get_icon(
    icon_name: str,
    *,
    style_name: Literal['raw'],
) -> str:
    ...

@overload
def get_icon(
    icon_name: SequenceNotStr[str],
    icon_class: Optional[SequenceNotStr[str]],
    style_name: Literal['default', 'unpadded']=...,
) -> html.Span:
    ...

@overload
def get_icon(
    icon_name: SequenceNotStr[str],
    *,
    style_name: Literal['default', 'unpadded']=...,
) -> html.Span:
    ...

@overload
def get_icon(
    icon_name: SequenceNotStr[str],
    icon_class: Optional[SequenceNotStr[str]],
    style_name: Literal['raw'],
) -> List[str]:
    ...

@overload
def get_icon(
    icon_name: SequenceNotStr[str],
    *,
    style_name: Literal['raw'],
) -> List[str]:
    ...

@overload
def get_icon(
    icon_name: None,
    icon_class: str,
    style_name: Literal['default', 'unpadded']=...
) -> html.I:
    ...

@overload
def get_icon(
    *,
    icon_class: str,
    style_name: Literal['default', 'unpadded']=...
) -> html.I:
    ...

@overload
def get_icon(
    icon_name: None,
    icon_class: str,
    style_name: Literal['raw'],
) -> str:
    ...

@overload
def get_icon(
    *,
    icon_class: str,
    style_name: Literal['raw'],
) -> str:
    ...

@overload
def get_icon(
    icon_name: None,
    icon_class: SequenceNotStr[str],
    style_name: Literal['default', 'unpadded']=...
) -> html.Span:
    ...

@overload
def get_icon(
    *,
    icon_class: SequenceNotStr[str],
    style_name: Literal['default', 'unpadded']=...
) -> html.Span:
    ...

@overload
def get_icon(
    icon_name: None,
    icon_class: SequenceNotStr[str],
    style_name: Literal['raw'],
) -> List[str]:
    ...

@overload
def get_icon(
    *,
    icon_class: SequenceNotStr[str],
    style_name: Literal['raw'],
) -> List[str]:
    ...

def get_icon(icon_name: None | SequenceNotStr[str] | str = None,
             icon_class: None | SequenceNotStr[str] | str = None,
             style_name: Literal['default', 'raw', 'unpadded'] = 'default'):
    
    # Icon for missing names:
    mi = "bi bi-exclamation-circle"
    # The bootstrap pad and margin classes for default styles
    default_pad_class = 'p-1 m-2'
    left_sequence_pad_class = 'me-0 ms-2 py-1 pe-0 ps-1 my-2'
    mid_sequence_pad_class = 'py-1 px-0 my-2 mx-0'
    right_sequence_pad_class = 'py-1 pe-1 ps-0 my-2 me-2 ms-0'

    if not icon_name is None:
        if isinstance(icon_name, str):
            if icon_class is None:
                icon_class = ''
            elif not isinstance(icon_class, str):
                if len(icon_class) > 1:
                    raise ValueError(f'icon_class must match length of icon_name; icon_name is single string, icon_class is length {len(icon_class)}')
                icon_class = icon_class[0]
            
            fetched_icon = DEFAULT_ICONS.get(icon_name, mi)
            if style_name == 'raw':
                return fetched_icon

            if isinstance(fetched_icon, str):
                match style_name:
                    case 'default':
                        return html.I(className=' '.join([fetched_icon, default_pad_class, icon_class]).strip())
                    case 'unpadded':
                        return html.I(className=' '.join([fetched_icon, icon_class]).strip())
            else:
                ic = [' '.join([x, icon_class]).strip() for x in fetched_icon]
                return get_icon(icon_class = ic, style_name = style_name)
            
            return ""
        else:
            # Assume is sequence
            if len(icon_name) == 1:
                return get_icon(icon_name[0], icon_class, style_name)
            
            if not icon_class is None:
                if not isinstance(icon_class,str) and len(icon_class) > 1:
                    assert len(icon_class) == len(icon_name), 'If multiple icon_classes provided, must match length of icon_name'
                if isinstance(icon_class, str):
                    icon_class = [icon_class]
                if len(icon_class) == 1:
                    icon_class = list(icon_class) * len(icon_name)
            else:
                icon_class = [""] * len(icon_name)
            
            ilistraw = [get_icon(x, None, style_name = 'raw') for x in icon_name]
            # Some icons may be lists themselves. Run a quick expansion
            class_reps = len_mixed_list(ilistraw)
            icon_class = repeat_list_by_index(list(icon_class), class_reps)
            ilistraw = flatten_mixed_list(ilistraw)

            match style_name:
                case 'raw':
                    return ilistraw
                case 'unpadded':
                    return html.Span([
                        html.I(className=' '.join([ilistraw[i], icon_class[i]]).strip()) for i in range(len(ilistraw))
                    ])
                case 'default':
                    ilist = []
                    for i in range(len(ilistraw)):
                        if i == 0 and len(ilistraw) > 1:
                            ilist.append(html.I(className=' '.join([ilistraw[i], left_sequence_pad_class ,icon_class[i]]).strip()))
                        elif i == (len(ilistraw)-1) and len(ilistraw) > 1:
                            ilist.append(html.I(className=' '.join([ilistraw[i], right_sequence_pad_class ,icon_class[i]]).strip()))
                        else:
                            ilist.append(html.I(className=' '.join([ilistraw[i], mid_sequence_pad_class ,icon_class[i]]).strip()))
                    return html.Span(ilist)
            
            return []
    else:
        if icon_class is None:
            raise ValueError('One of `icon_name` or `icon_class` must be provided')
        if isinstance(icon_class, str):
            match style_name:
                case 'raw':
                    return icon_class
                case 'unpadded':
                    return html.I(className=icon_class)
                case 'default':
                    return html.I(className=' '.join([icon_class, default_pad_class]))
            return ""
        else:
            if len(icon_class) == 1:
                return get_icon(icon_class = icon_class[0], style_name=style_name)

            match style_name:
                case 'raw':
                    return icon_class
                case 'unpadded':
                    return html.Span([
                        html.I(className=x) for x in icon_class
                    ])
                case 'default':
                    ilist = []
                    for i in range(len(icon_class)):
                        if i == 0:
                            ilist.append(html.I(className=' '.join([left_sequence_pad_class, icon_class[i]]).strip()))
                        elif i == (len(icon_class)-1):
                            ilist.append(html.I(className=' '.join([right_sequence_pad_class, icon_class[i]]).strip()))
                        else:
                            ilist.append(html.I(className=' '.join([mid_sequence_pad_class, icon_class[i]]).strip()))
                    return html.Span(ilist)
    
    return []

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
    placeholder: int | float = 0.0,
    min: int | float | None = 0.0,
    max: int | float | None = None,
    step: int | float  = 1
):
    if section is None:
        section = 'None'
    
    input_id = {
        'type': type_id,
        'key': key,
        'section': section
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
    model_id,
    input_key,
    input_value,
    key_section = None,
    input_time = None
):
    if input_time is None:
        input_time = datetime.datetime.now()
    return {
        'type': 'model_config_interface_update',
        'model_id': model_id,
        'key': input_key,
        'val': input_value,
        'key_section': key_section,
        'time': input_time.timestamp(),
    }

def finance_interface_action(
    finance_id,
    input_key,
    input_value,
    key_section = None,
    input_time = None
):
    if input_time is None:
        input_time = datetime.datetime.now()
    return {
        'type': 'finance_config_interface_update',
        'finance_id': finance_id,
        'key': input_key,
        'val': input_value,
        'key_section': key_section,
        'time': input_time.timestamp(),
    }

def model_run_request(
    model_id,
    request_time = None
):
    if request_time is None:
        request_time = datetime.datetime.now()
    return {
        'type': 'model_run_request',
        'model_id': model_id,
        'time': request_time.timestamp()
    }

def finance_run_request(
    finance_id,
    model_id,
    request_time = None
):
    if request_time is None:
        request_time = datetime.datetime.now()
    return {
        'type': 'finance_run_request',
        'finance_id': finance_id,
        'model_id': model_id,
        'time': request_time.timestamp()
    }
