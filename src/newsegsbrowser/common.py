from collections.abc import Sequence
from typing import Literal

from dash import html
import dash_bootstrap_components as dbc

def flatten_mixed_list(mixed_list):
    flat_list=[]
    for item in mixed_list:
        if isinstance(item, str):
            flat_list += [item]
        else:
            flat_list += item
    return flat_list

def len_mixed_list(mixed_list):
    lens=[]
    for item in mixed_list:
        if isinstance(item, str):
            lens += [1]
        else:
            lens += [len(item)]
    return lens

def repeat_list_by_index(l, repeats):
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
    'config-4': 'bi bi-4-circle-fill'
}
def get_icon(icon_name:None|Sequence|str=None,
             icon_class:None|Sequence|str=None,
             style_name:Literal['default','raw','unpadded']='default'):
    
    # Icon for missing names:
    mi = "bi bi-exclamation-circle"
    # The bootstrap pad and margin classes for default styles
    default_pad_class = 'p-1 m-2'
    left_sequence_pad_class = 'me-0 ms-2 py-1 pe-0 ps-1 my-2'
    mid_sequence_pad_class = 'py-1 px-0 my-2 mx-0'
    right_sequence_pad_class = 'py-1 pe-1 ps-0 my-2 me-2 ms-0'

    if not icon_name is None:
        if isinstance(icon_name, str):
            if not icon_class is None:
                if not (isinstance(icon_class, str) or len(icon_class) == 1):
                    raise ValueError('icon_class must match length of icon_name')
                if not isinstance(icon_class, str):
                    icon_class = icon_class[0]
            else:
                icon_class = ""
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
                return get_icon(icon_class=ic, style_name=style_name)
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
                    icon_class = icon_class * len(icon_name)
            else:
                icon_class = [""] * len(icon_name)
            
            ilistraw = [get_icon(x, style_name='raw') for x in icon_name]
            # Some icons may be lists themselves. Run a quick expansion
            class_reps = len_mixed_list(ilistraw)
            icon_class = repeat_list_by_index(icon_class, class_reps)
            ilistraw = flatten_mixed_list(ilistraw)

            match style_name:
                case 'raw':
                    return ilistraw
                case 'unpadded':
                    return html.Span([
                        html.I(className=' '.join([ilistraw[i],icon_class[i]]).strip()) for i in range(len(ilistraw))
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

def create_numeric_card_input(icon_name,
                              label,
                              input_id):
    return html.Div([
        html.H5([
            get_icon(icon_name),
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

def unescape_html_icons(html_text):
    return (
        html_text
        .replace('<th>&lt;','<th><')
        .replace('"&gt;&lt;','"><')
        .replace('i&gt;', 'i>')
    )