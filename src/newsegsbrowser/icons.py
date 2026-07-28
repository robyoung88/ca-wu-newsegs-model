"""
An icon library for the NewSEGS model.

Universally uses the bootstrap icon font icon library.
"""

from typing import List, Literal, Optional, overload

from dash import html
from useful_types import SequenceNotStr

from util import flatten_string_lists

DEFAULT_ICONS = {
    'latlon': 'bi bi-geo-alt',
    'osgb': 'bi bi-map',
    'generation': 'bi bi-lightning-charge',
    'gen-wind': 'bi bi-wind',
    'gen-pv': 'bi bi-sun',
    'storage': 'bi bi-battery-half',
    'storage-rte': ['bi bi-battery-half', 'bi bi-arrow-clockwise'],
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
    'cost-ev': 'bi bi-ev-front',
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
    'config-5': 'bi bi-5-circle-fill',
    'config-6': 'bi bi-6-circle-fill',
    'config-7': 'bi bi-7-circle-fill',
    'config-8': 'bi bi-8-circle-fill',
    'config-duplicate': 'bi bi-copy',
    'config-remove': 'bi bi-dash-circle',
    'config-focus': 'bi bi-crosshair',
    'config-download': 'bi bi-box-arrow-down',
    'config-upload': 'bi bi-box-arrow-in-up',
    'results-download': 'bi bi-table',
    'show-graph': 'bi bi-graph-up',
    'nav-landing': 'bi bi-card-text',
    'nav-system-config': 'bi bi-sliders2-vertical',
    'nav-dsa-config': 'bi bi-tornado',
    'nav-psa-config': 'bi bi-dice-3',
    'nav-build-arch-config': 'bi bi-houses',
    'autorun-true': 'bi bi-play-circle-fill',
    'autorun-false': 'bi bi-stop-circle',
    'value-reset': 'bi bi-arrow-clockwise',
    'value-set-default': 'bi bi-sticky',
}

ICON_COLOUR_CLASSES = [
    'text-primary',
    'text-success',
    'text-danger',
    'text-warning',
    'text-info',
    'text-dark',
    'text-secondary'
]

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
            class_reps = flatten_string_lists.len_mixed_list(ilistraw)
            icon_class = flatten_string_lists.repeat_list_by_index(list(icon_class), class_reps)
            ilistraw = flatten_string_lists.flatten_mixed_list(ilistraw)

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
