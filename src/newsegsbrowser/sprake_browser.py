# A Dash Leaflet map browser for manipulating the Sprake Model
import json, uuid
from pyproj import Transformer
from collections.abc import Mapping, Sequence
from typing import Literal

from dash import Dash, html, Input, Output, dcc, State, ALL, no_update
import dash_leaflet as dl
import dash_bootstrap_components as dbc
import dash_daq as daq

from config import settings

_trans_togb = Transformer.from_crs("EPSG:4326", "EPSG:27700")

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

_annual_default_stat_list = [
                                {'label':'Mean',
                                 'value':'mean'},
                                {'label':'Max',
                                 'value':'max'},
                                {'label':'Min',
                                 'value':'min'}
                             ]

_total_default_stat_list = [
                            {'label':'Total',
                             'value':'sum'}
                            ]

_annual_seasonal_stat_list = [
    {'label':'Year Mean',
     'value':'mean_year'},
    {'label':'Year Max',
     'value':'max_year'},
    {'label':'Year Min',
     'value':'min_year'},
    {'label':'Wtr Mean',
     'value':'mean_wtr'},
    {'label':'Wtr Max',
     'value':'max_wtr'},
    {'label':'Wtr Min',
     'value':'min_wtr'},
    {'label':'Spr Mean',
     'value':'mean_spr'},
    {'label':'Spr Max',
     'value':'max_spr'},
    {'label':'Spr Min',
     'value':'min_spr'},
    {'label':'Smr Mean',
     'value':'mean_smr'},
    {'label':'Smr Max',
     'value':'max_smr'},
    {'label':'Smr Min',
     'value':'min_smr'},
    {'label':'Aut Mean',
     'value':'mean_aut'},
    {'label':'Aut Max',
     'value':'max_aut'},
    {'label':'Aut Min',
     'value':'min_aut'}
]

_total_seasonal_stat_list = [
    {'label':'Year',
     'value':'total_year'},
    {'label':'Wtr',
     'value':'total_wtr'},
    {'label':'Spr',
     'value':'total_spr'},
    {'label':'Smr',
     'value':'total_smr'},
    {'label':'Aut',
     'value':'total_aut'}
]

def present_single_stat(data_list,
                        stat_name,
                        stat_label,
                        stat_value='mean',
                        fmt='{:.2f}',
                        none_str='-'):
    n_configs = len(data_list)

    comp_result = [x.get(stat_name, None) for x in data_list]
    vals = [x.get(stat_value, None) if x is not None else None for x in comp_result]
    
    rw = [html.Td(stat_label, colSpan=2)] \
        + [html.Td(fmt.format(x)) if x is not None else html.Td(none_str) for x in vals]

    return [html.Tr(rw)]

def present_stat_description(data_list,
                             stat_name,
                             stat_label,
                             stat_list=[
                                {'label':'Mean',
                                 'value':'mean'},
                                {'label':'Max',
                                 'value':'max'},
                                {'label':'Min',
                                 'value':'min'}
                             ],
                             fmt='{:,.2f}',
                             none_str='-'):
    n_rows = len(stat_list)
    n_configs = len(data_list)

    # Make a list of the dictionaries of computational results for this stat,
    # e.g. if stat_name is annual_production,
    # then comp_result may consist of dicts of {'mean': xxx, 'min': yyy, 'max': zzz}
    comp_result = [x.get(stat_name, None) for x in data_list]

    def get_Tr(idx):
        stat = stat_list[idx]
        if (idx == 0):
            rw = [html.Td(stat_label, rowSpan=n_rows)]
        else:
            rw = []
        rw = rw + [html.Td(stat['label'])]
        val_fmt = stat.get('fmt', None)
        if val_fmt is None:
            val_fmt = fmt
        
        val_lookup = stat.get('value')
        
        vals = [x.get(val_lookup, None) if x is not None else None for x in comp_result]
        
        rw = rw + [html.Td(val_fmt.format(x)) if x is not None else html.Td(none_str) for x in vals]
        return html.Tr(rw)

    rws = [get_Tr(i) for i in range(n_rows)]
    return rws

def _default_stat_formatter(stat_dict):
    return str(stat_dict)

_default_hours_in_range_stat_list = [
    {'label':r'0%≤x<5%',
     'value':'hrs_000_to_005'},
    {'label':r'5%≤x<25%',
     'value':'hrs_005_to_025'},
    {'label':r'25%≤x<50%',
     'value':'hrs_025_to_050'},
    {'label':r'50%≤x<75%',
     'value':'hrs_050_to_075'},
    {'label':r'75%≤x<95%',
     'value':'hrs_075_to_095'},
    {'label':r'95%≤x≤100%',
     'value':'hrs_095_to_0100'}
    ]

_default_days_in_range_stat_list = [
    {'label':r'0%≤x<5%',
     'value':'days_000_to_005'},
    {'label':r'5%≤x<25%',
     'value':'days_005_to_025'},
    {'label':r'25%≤x<50%',
     'value':'days_025_to_050'},
    {'label':r'50%≤x<75%',
     'value':'days_050_to_075'},
    {'label':r'75%≤x<95%',
     'value':'days_075_to_095'},
    {'label':r'95%≤x≤100%',
     'value':'days_095_to_0100'}
    ]

def present_stat_description_compound(data_list,
                                      stat_name,
                                      stat_label,
                                      stat_formatter=_default_stat_formatter,
                                      stat_list=_default_hours_in_range_stat_list):
    # Extension to present_stat_description to allow for complex compound formatting of table values
    n_rows = len(stat_list)
    n_configs = len(data_list)

    # Grab the computed results for the desired stat
    comp_result = [x.get(stat_name, None) for x in data_list]

    def transform_stats(config_results):
        def trans_stat(idx):
            if config_results is None:
                return None
            stat = stat_list[idx]
            formatter = stat.get('formatter', None)
            if formatter is None:
                formatter = stat_formatter

            val_lookup = stat.get('value')

            idict = config_results.get(val_lookup, None)

            if idict is None:
                return idict            
            
            return formatter(idict)

        return {stat_list[i].get('value'): trans_stat(i) for i in range(n_rows)}

    trans_stats = [{stat_name: transform_stats(x)} for x in comp_result]

    return present_stat_description(trans_stats, stat_name, stat_label, stat_list, fmt="{}")

def present_event_and_date(data_list,
                           event_name,
                           event_label,
                           event_value,
                           event_value_formatter,
                           date_label='On:',
                           event_date='datetime',
                           none_str='-',
                           nonedate_str='#/#/#'):
    n_configs = len(data_list)

    comp_result = [x.get(event_name, None) for x in data_list]

    val_row = html.Tr([html.Td(event_label,colSpan=2)] + 
        [html.Td(event_value_formatter(x.get(event_value))) if x is not None else html.Td(none_str) for x in comp_result])

    date_row = html.Tr([html.Td(date_label, colSpan=2, style={'text-align':'end'})] 
        + [html.Td(f'{x.get(event_date).strftime("%Y/%m/%d")}') if x is not None else html.Td(none_str) for x in comp_result])

    return [val_row, date_row]    

def present_event_and_daterange(data_list,
                                event_name,
                                event_label,
                                event_value,
                                event_value_formatter,
                                range_label='From - To',
                                event_start='datetime_start',
                                event_end='datetime_end',
                                none_str='-',
                                nonedate_str='#/#/# - #/#/#'):
    #n_rows = 2
    n_configs = len(data_list)

    comp_result = [x.get(event_name, None) for x in data_list]

    val_row = html.Tr([html.Td(event_label,colSpan=2)] + 
        [html.Td(event_value_formatter(x.get(event_value))) if x is not None else html.Td(none_str) for x in comp_result])

    date_row = html.Tr([html.Td(range_label, colSpan=2, style={'text-align':'end'})] 
        + [html.Td(f'{x.get(event_start)} - {x.get(event_end)}') if x is not None else html.Td(none_str) for x in comp_result])

    return [val_row, date_row]

def hours_in_range_formatter(d):
    if d is None:
        return "( -  kW) - (%)"
    return f"({d.get('min_power'):,.2f} - {d.get('max_power'):,.2f}) {d.get('hours'):,.1f} ({d.get('ann_fraction'):,.1%})"

def days_in_range_formatter(d):
    if d is None:
        return "( - kWh) - (%)"
    return f"({d.get('min_production'):,.0f} - {d.get('max_production'):,.0f}) {d.get('days'):,.0f} ({d.get('ann_fraction'):,.1%})"

def val_percent_formatter_factory(value_id, fraction_id, value_dp=0, fraction_dp=1):
    fmt = "{:,." + str(value_dp) + "f} ({:,." + str(fraction_dp) + "%})"
    def val_percent_formatter(d):
        if d is None:
            return "- (-%)"
        return fmt.format(d.get(value_id),d.get(fraction_id))
    return val_percent_formatter    

def create_tab_head(n_configs):
    return [
        html.Thead(
            html.Tr([
                html.Th(""),
                html.Th("")
            ] + [
                html.Th(get_icon(f'config-{x+1}')) for x in range(n_configs)
            ])
        )
    ]

def create_wind_results(wind_data=None, annual=True):
    if wind_data is None:
        wind_data = {}
    
    if isinstance(wind_data, Mapping):
        n_configs = 1
        wind_data = [wind_data]
    else:
        n_configs = len(wind_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        ann_gen = present_stat_description(wind_data, 'annual_production', 'Wind production (kWh/yr)', fmt='{:,.0f}')
    else:
        ann_gen = present_stat_description(wind_data, 'total_production', 'Wind production (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')

    hours_in_range = present_stat_description_compound(wind_data, 'hrs_in_range', 'Hours in range', hours_in_range_formatter)

    longest_hours_below_5 = present_event_and_daterange(wind_data, 'continuous_hours_below_5pc', r"Longest continuous hours <5%", "hours", lambda x: '{:,.1f}'.format(x))

    longest_hours_above_95 = present_event_and_daterange(wind_data, 'continuous_hours_above_95pc', r"Longest continuous hours ≥95%", "hours", lambda x: '{:,.1f}'.format(x))

    if (annual):
        direct_sc = present_stat_description_compound(wind_data,
                                                      'self-consumption',
                                                      r'Wind-only self-consumption potential (kWh/yr (% production))',
                                                      stat_formatter=val_percent_formatter_factory('self_consumption','frac_self_consumption'),
                                                      stat_list=_annual_seasonal_stat_list)
    else:
        direct_sc = present_stat_description_compound(wind_data,
                                                      'self-consumption',
                                                      r'Wind-only self-consumption potential (kWh (% production))',
                                                      stat_formatter=val_percent_formatter_factory('self_consumption','frac_self_consumption'),
                                                      stat_list=_total_seasonal_stat_list)

    tab_body = [html.Tbody(ann_gen + hours_in_range + longest_hours_below_5 + longest_hours_above_95 + direct_sc)]

    return dbc.Table(tab_head + tab_body)

def create_pv_results(pv_data=None, annual=True):
    if pv_data is None:
        pv_data = {}
    
    if isinstance(pv_data, Mapping):
        n_configs = 1
        pv_data = [pv_data]
    else:
        n_configs = len(pv_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        ann_gen = present_stat_description(pv_data, 'annual_production', 'PV production (kWh/yr)', fmt='{:,.0f}')
    else:
        ann_gen = present_stat_description(pv_data, 'total_production', 'PV production (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')

    max_day = present_event_and_date(pv_data, 'max_daily_production', r'Maximum daily production (kWh)', 'production', lambda x: '{:,.1f}'.format(x))

    min_day = present_event_and_date(pv_data, 'min_daily_production', r'Minimum daily production (kWh)', 'production', lambda x: '{:,.1f}'.format(x))

    days_in_range = present_stat_description_compound(pv_data, 
                                                      'days_in_range', 
                                                      r'Daily production distribution (% of max)', 
                                                      stat_formatter=days_in_range_formatter,
                                                      stat_list=_default_days_in_range_stat_list)

    if (annual):
        direct_sc = present_stat_description_compound(pv_data,
                                                      'self-consumption',
                                                      r'PV-only self-consumption potential (kWh/yr (% production))',
                                                      stat_formatter=val_percent_formatter_factory('self_consumption','frac_self_consumption'),
                                                      stat_list=_annual_seasonal_stat_list)
    else:
        direct_sc = present_stat_description_compound(pv_data,
                                                      'self-consumption',
                                                      r'PV-only self-consumption potential (kWh (% production))',
                                                      stat_formatter=val_percent_formatter_factory('self_consumption','frac_self_consumption'),
                                                      stat_list=_total_seasonal_stat_list)

    tab_body = [html.Tbody(ann_gen + max_day + min_day + days_in_range + direct_sc)]

    return dbc.Table(tab_head + tab_body)

def create_combined_generation_results(gen_data=None, annual=True):
    if gen_data is None:
        gen_data = {}
    if isinstance(gen_data, Mapping):
        n_configs = 1
        gen_data = [gen_data]
    else:
        n_configs = len(gen_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        ann_gen = present_stat_description(gen_data, 'annual_production', 'Production (kWh/yr)', fmt='{:,.0f}')
    else:
        ann_gen = present_stat_description(gen_data, 'total_production', 'Production (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')

    max_day = present_event_and_date(gen_data, 'max_daily_production', r'Maximum daily production (kWh)', 'production', lambda x: '{:,.1f}'.format(x))

    min_day = present_event_and_date(gen_data, 'min_daily_production', r'Minimum daily production (kWh)', 'production', lambda x: '{:,.1f}'.format(x))

    days_in_range = present_stat_description_compound(gen_data, 
                                                      'days_in_range', 
                                                      r'Daily production distribution (% of max)', 
                                                      stat_formatter=days_in_range_formatter,
                                                      stat_list=_default_days_in_range_stat_list)

    if (annual):
        direct_sc = present_stat_description_compound(gen_data,
                                                      'self-consumption',
                                                      r'Without storage self-consumption potential (kWh/yr (% production))',
                                                      stat_formatter=val_percent_formatter_factory('self_consumption','frac_self_consumption'),
                                                      stat_list=_annual_seasonal_stat_list)
    else:
        direct_sc = present_stat_description_compound(gen_data,
                                                      'self-consumption',
                                                      r'Without storage self-consumption potential (kWh (% production))',
                                                      stat_formatter=val_percent_formatter_factory('self_consumption','frac_self_consumption'),
                                                      stat_list=_total_seasonal_stat_list)

    tab_body = [html.Tbody(ann_gen + max_day + min_day + days_in_range + direct_sc)]

    return dbc.Table(tab_head + tab_body)

def create_stor_results(stor_data=None, annual=True):
    if stor_data is None:
        stor_data = {}
    
    if isinstance(stor_data, Mapping):
        n_configs = 1
        stor_data = [stor_data]
    else:
        n_configs = len(stor_data)

    tab_head = create_tab_head(n_configs)

    if (annual):
        to_stor = present_stat_description(stor_data, 'annual_tostore', 'Units to storage (kWh/yr)', fmt='{:,.0f}')
        from_stor = present_stat_description(stor_data, 'annual_fromstore', 'Units from storage (kWh/yr)', fmt='{:,.0f}')
        loss_stor = present_stat_description(stor_data, 'annual_lossstore', 'Units lost (kWh/yr)', fmt='{:,.0f}')
        charge_cycles = present_stat_description(stor_data, 'annual_chargecycles', 'Effective charge cycles (N)', fmt='{:,.0f}')
        hrs_min_soc = present_stat_description_compound(stor_data,
                                                        'hrs_min_soc',
                                                        r'Hours at min SoC (hrs, (%))',
                                                        stat_formatter=val_percent_formatter_factory('hours', 'frac_hours'),
                                                        stat_list=_annual_default_stat_list
                                                        )
        hrs_max_soc = present_stat_description_compound(stor_data,
                                                        'hrs_max_soc',
                                                        r'Hours at max SoC (hrs, (%))',
                                                        stat_formatter=val_percent_formatter_factory('hours', 'frac_hours'),
                                                        stat_list=_annual_default_stat_list
                                                        )
    else:
        to_stor = present_stat_description(stor_data, 'total_tostore', 'Units to storage (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        from_stor = present_stat_description(stor_data, 'total_fromstore', 'Units from storage (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        loss_stor = present_stat_description(stor_data, 'total_lossstore', 'Units lost (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        charge_cycles = present_stat_description(stor_data, 'total_chargecycles', 'Effective charge cycles (N)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        hrs_min_soc = present_stat_description_compound(stor_data,
                                                        'hrs_min_soc',
                                                        r'Hours at min SoC (hrs, (%))',
                                                        stat_formatter=val_percent_formatter_factory('hours', 'frac_hours'),
                                                        stat_list=_total_default_stat_list
                                                        )
        hrs_max_soc = present_stat_description_compound(stor_data,
                                                        'hrs_max_soc',
                                                        r'Hours at max SoC (hrs, (%))',
                                                        stat_formatter=val_percent_formatter_factory('hours', 'frac_hours'),
                                                        stat_list=_total_default_stat_list
                                                        )
    
    longest_hrs_min_soc = present_event_and_daterange(stor_data, 'continuous_hrs_min_soc', r'Longest continuous hours at min SoC', 'hours', lambda x: '{:,.1f}'.format(x))
    longest_hrs_max_soc = present_event_and_daterange(stor_data, 'continuous_hrs_max_soc', r'Longest continuous hours at max SoC', 'hours', lambda x: '{:,.1f}'.format(x))

    tab_body = [html.Tbody(to_stor + from_stor + loss_stor + hrs_min_soc + longest_hrs_min_soc + hrs_max_soc + longest_hrs_max_soc)]

    return dbc.Table(tab_head + tab_body)

def create_cons_results(cons_data=None, annual=True):
    if cons_data is None:
        cons_data = {}
    
    if isinstance(cons_data, Mapping):
        n_configs = 1
        cons_data = [cons_data]
    else:
        n_configs = len(cons_data)

    tab_head = create_tab_head(n_configs)
    
    if (annual):
        app_cons = present_stat_description(cons_data, 'annual_app_cons', 'Appliance consumption (kWh/yr)', fmt='{:,.0f}')
        dhw_cons = present_stat_description(cons_data, 'annual_dhw_cons', 'DHW consumption (kWh/yr)', fmt='{:,.0f}')
        spaceheat_cons = present_stat_description(cons_data, 'annual_sh_cons', 'Space heat consumption (kWh/yr)', fmt='{:,.0f}')

        residential_cons = present_stat_description(cons_data, 'annual_resid_cons', 'Total residential consumption (kWh/yr)', fmt='{:,.0f}')
        perunit_residential_cons = present_stat_description(cons_data, 'annual_resid_cons_perunit', 'Per-unit residential consumption (kWh/yr)', fmt='{:,.0f}')

        ev_cons = present_stat_description(cons_data, 'annual_ev_cons', 'EV consumption (kWh/yr)', fmt='{:,.0f}')
        site_cons = present_stat_description(cons_data, 'annual_site_cons', 'Site consumption (kWh/yr)', fmt='{:,.0f}')

    else:
        app_cons = present_stat_description(cons_data, 'total_app_cons', 'Appliance consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        dhw_cons = present_stat_description(cons_data, 'total_dhw_cons', 'DHW consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        spaceheat_cons = present_stat_description(cons_data, 'total_sh_cons', 'Space heat consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')

        residential_cons = present_stat_description(cons_data, 'total_resid_cons', 'Total residential consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        perunit_residential_cons = present_stat_description(cons_data, 'total_resid_cons_perunit', 'Per-unit residential consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')

        ev_cons = present_stat_description(cons_data, 'total_ev_cons', 'EV consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')
        site_cons = present_stat_description(cons_data, 'total_site_cons', 'Site consumption (kWh)', stat_list=_total_default_stat_list, fmt='{:,.0f}')

    admd = present_single_stat(cons_data, 'admd_computed', 'ADMD - calculated (kW)', 'value', fmt='{:,.0f}')
    max_demand = present_event_and_date(cons_data, 'max_demand', 'Maximum demand (kW)', 'value', lambda x: '{:,.0f}'.format(x))

    tab_body = [html.Tbody(app_cons + dhw_cons + spaceheat_cons + residential_cons + perunit_residential_cons + ev_cons + site_cons + admd + max_demand)]

    return dbc.Table(tab_head + tab_body)

def create_seasonal_cons_results(cons_data=None, annual=True):
    if cons_data is None:
        cons_data = {}
    
    if isinstance(cons_data, Mapping):
        n_configs = 1
        cons_data = [cons_data]
    else:
        n_configs = len(cons_data)

    tab_head = create_tab_head(n_configs)
    
    if (annual):
        weekday_sitecons = present_stat_description_compound(cons_data,
                                                             'annual_site_daily_cons_wd',
                                                             r'Weekday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=_annual_seasonal_stat_list)

        sat_sitecons = present_stat_description_compound(cons_data,
                                                             'annual_site_daily_cons_sat',
                                                             r'Saturday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=_annual_seasonal_stat_list)
        
        sun_sitecons = present_stat_description_compound(cons_data,
                                                             'annual_site_daily_cons_sun',
                                                             r'Sunday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=_annual_seasonal_stat_list)
    else:
        weekday_sitecons = present_stat_description_compound(cons_data,
                                                             'total_site_daily_cons_wd',
                                                             r'Weekday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=_total_seasonal_stat_list)

        sat_sitecons = present_stat_description_compound(cons_data,
                                                             'total_site_daily_cons_sat',
                                                             r'Saturday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=_total_seasonal_stat_list)
        
        sat_sitecons = present_stat_description_compound(cons_data,
                                                             'total_site_daily_cons_sun',
                                                             r'Sunday site demand (kWh)',
                                                             stat_formatter = lambda x: '{:,.1f}'.format(x.get('consumption')),
                                                             stat_list=_total_seasonal_stat_list)

    tab_body = [html.Tbody(weekday_sitecons + sat_sitecons + sun_sitecons)]

    return dbc.Table(tab_head + tab_body)

def create_net_results(net_data=None, annual=True):
    if net_data is None:
        net_data = {}
    
    if isinstance(net_data, Mapping):
        n_configs = 1
        net_data = [net_data]
    else:
        n_configs = len(net_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        export_stats = present_stat_description(net_data, 'annual_export', 'Export to grid (kWh/yr)', fmt='{:,.0f}')
        import_stats = present_stat_description(net_data, 'annual_import', 'Import from grid (kWh/yr)', fmt='{:,.0f}')
        loss_stats = present_stat_description(net_data, 'annual_stor_loss', 'Storage losses (kWh/yr)', fmt='{:,.0f}')

        # NB - ensure this stat compensates for daylight savings
        peak_export = present_stat_description(net_data, 'peak_export', 'Exports 5pm-8pm (kWh/yr)', fmt='{:,.0f}')
        peak_import = present_stat_description(net_data, 'peak_import', 'Imports 5pm-8pm (kWh/yr)', fmt='{:,.0f}')
    else:
        export_stats = present_stat_description(net_data, 'annual_export', 'Export to grid (kWh)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
        import_stats = present_stat_description(net_data, 'annual_import', 'Import from grid (kWh)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
        loss_stats = present_stat_description(net_data, 'annual_stor_loss', 'Storage losses (kWh)', fmt='{:,.0f}', stat_list=_total_default_stat_list)

        # NB - ensure this stat compensates for daylight savings
        peak_export = present_stat_description(net_data, 'peak_export', 'Exports 5pm-8pm (kWh)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
        peak_import = present_stat_description(net_data, 'peak_import', 'Imports 5pm-8pm (kWh)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
    
    tab_body = [html.Tbody(export_stats + import_stats + loss_stats + peak_export + peak_import)]

    return dbc.Table(tab_head + tab_body)

def create_seasonal_net_results(net_data=None, annual=True):
    if net_data is None:
        net_data = {}
    
    if isinstance(net_data, Mapping):
        n_configs = 1
        net_data = [net_data]
    else:
        n_configs = len(net_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        export_stats = present_stat_description_compound(net_data,
                                                         'annual_export',
                                                         r'Export to grid (kWh/yr (% production))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=_annual_seasonal_stat_list)

        import_stats = present_stat_description_compound(net_data,
                                                         'annual_import',
                                                         r'Import from grid (kWh/yr (% consumption))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=_annual_seasonal_stat_list)

        peak_export = present_stat_description_compound(net_data,
                                                         'peak_export',
                                                         r'Exports 5pm-8pm (kWh/yr (% production))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=_annual_seasonal_stat_list)
        
        peak_import = present_stat_description_compound(net_data,
                                                        'peak_import',
                                                        r'Imports 5pm-8pm (kWh/yr (% consumption))',
                                                        stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                        stat_list=_annual_seasonal_stat_list)
    else:
        export_stats = present_stat_description_compound(net_data,
                                                         'annual_export',
                                                         r'Export to grid (kWh (% production))',
                                                         stat_formatter = val_percent_formatter_factory('total', 'frac'),
                                                         stat_list=_total_seasonal_stat_list)

        import_stats = present_stat_description_compound(net_data,
                                                         'annual_import',
                                                         r'Import from grid (kWh (% consumption))',
                                                         stat_formatter = val_percent_formatter_factory('total', 'frac'),
                                                         stat_list=_total_seasonal_stat_list)

        peak_export = present_stat_description_compound(net_data,
                                                         'peak_export',
                                                         r'Exports 5pm-8pm (kWh (% production))',
                                                         stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                         stat_list=_total_seasonal_stat_list)
        
        peak_import = present_stat_description_compound(net_data,
                                                        'peak_import',
                                                        r'Imports 5pm-8pm (kWh (% consumption))',
                                                        stat_formatter = val_percent_formatter_factory('mean', 'frac'),
                                                        stat_list=_total_seasonal_stat_list)

    tab_body = [html.Tbody(export_stats + import_stats + peak_export + peak_import)]

    return dbc.Table(tab_head + tab_body)

def create_so_benefits_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        resid_receipts = present_stat_description(econ_data, 'annual_resident_receipts', 'Resident receipts (£/yr)', fmt='{:,.0f}')
        resid_perunit_receipts = present_stat_description(econ_data, 'annual_resident_perunit_receipts', 'Resident receipts (£/yr/household)', fmt='{:,.0f}')

        ev_receipts = present_stat_description(econ_data, 'annual_ev_receipts', 'EV receipts (£/yr)', fmt='{:,.0f}')

        export_receipts = present_stat_description(econ_data, 'annual_export_receipts', 'Export receipts (£/yr)', fmt='{:,.0f}')
    else:
        resid_receipts = present_stat_description(econ_data, 'annual_resident_receipts', 'Resident receipts (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
        resid_perunit_receipts = []

        ev_receipts = present_stat_description(econ_data, 'annual_ev_receipts', 'EV receipts (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)

        export_receipts = present_stat_description(econ_data, 'annual_export_receipts', 'Export receipts (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)

    total_benefits = present_stat_description(econ_data, 'total_benefits_undiscounted', 'Total present benefits (undiscounted) (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
    total_benefits_discounted = present_stat_description(econ_data, 'total_benefits_discounted', 'Total present benefits (discounted) (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)

    tab_body = [html.Tbody(resid_receipts + resid_perunit_receipts + ev_receipts + export_receipts + total_benefits + total_benefits_discounted)]

    return dbc.Table(tab_head + tab_body)

def create_so_costs_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    tab_head = create_tab_head(n_configs)

    if (annual):
        import_costs = present_stat_description(econ_data, 'annual_import_costs', 'Import costs (£/yr)', fmt='{:,.2f}')
        generator_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - generation (£/yr)', fmt='{:,.2f}')
        storage_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - storage (£/yr)', fmt='{:,.2f}')

        ann_costs = present_stat_description(econ_data, 'annual_recurrent_costs', 'Recurrent costs - total (£/yr)', fmt='{:,.2f}')
    else:
        import_costs = present_stat_description(econ_data, 'annual_import_costs', 'Import costs (£r)', fmt='{:,.2f}', stat_list=_total_default_stat_list)
        generator_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - generation (£/yr)', fmt='{:,.2f}', stat_list=_total_default_stat_list)
        storage_om_costs = present_stat_description(econ_data, 'annual_gen_om_costs', 'O&M costs - storage (£/yr)', fmt='{:,.2f}', stat_list=_total_default_stat_list)

        ann_costs = present_stat_description(econ_data, 'annual_recurrent_costs', 'Recurrent costs - total (£/yr)', fmt='{:,.2f}', stat_list=_total_default_stat_list)

    capex_generation = present_single_stat(econ_data, 'total_gen_capex', 'Capital costs - generation (£)', 'value', fmt='{:,.2f}')
    capex_storage = present_single_stat(econ_data, 'total_stor_capex', 'Capital costs - storage (£)', 'value', fmt='{:,.2f}')
    capex_dist = present_single_stat(econ_data, 'total_dist_capex', 'Capital costs - distribution and switching (£)', 'value', fmt='{:,.2f}')
    capex_meter = present_single_stat(econ_data, 'total_meter_capex', 'Capital costs - metering (£)', 'value', fmt='{:,.2f}')

    capex_total = present_single_stat(econ_data, 'total_capex', 'Capital costs - total (£)', 'value', fmt='{:,.2f}')

    total_costs = present_stat_description(econ_data, 'total_costs_undiscounted', 'Total present costs (undiscounted) (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)
    total_costs_discounted = present_stat_description(econ_data, 'total_costs_discounted', 'Total present costs (discounted) (£)', fmt='{:,.0f}', stat_list=_total_default_stat_list)

    tab_body = [html.Tbody(import_costs + generator_om_costs + storage_om_costs + ann_costs + capex_generation + capex_storage + capex_dist + capex_meter + capex_total + total_costs + total_costs_discounted)]

    return dbc.Table(tab_head + tab_body)

def create_so_value_results(econ_data=None, annual=True):
    if econ_data is None:
        econ_data = {}
    
    if isinstance(econ_data, Mapping):
        n_configs = 1
        econ_data = [econ_data]
    else:
        n_configs = len(econ_data)
    
    tab_head = create_tab_head(n_configs)

    b_to_c_undiscounted = present_single_stat(econ_data, 'benefits_to_costs_undiscounted', 'Benefits/Costs (undiscounted)', 'value', fmt='{:,.2f}')
    b_to_c_discounted = present_single_stat(econ_data, 'benefits_to_costs_discounted', 'Benefits/Costs (discounted)', 'value', fmt='{:,.2f}')

    simple_payback_time = present_single_stat(econ_data, 'simple_payback_time', 'Simple payback time (years)', 'value', fmt='{:,.2f}')

    npv_undiscounted = present_single_stat(econ_data, 'npv_undiscounted', 'Net Present Value (undiscounted) (£)', 'value', fmt='{:,.0f}')
    npv_discounted = present_single_stat(econ_data, 'npv_discounted', 'Net Present Value (discounted) (£)', 'value', fmt='{:,.0f}')

    tab_body = [html.Tbody(b_to_c_undiscounted + b_to_c_discounted + simple_payback_time + npv_undiscounted + npv_discounted)]

    return dbc.Table(tab_head + tab_body)

def create_map_layout(map_id='sitemap',
                      center=(53.165716, -3.728402)):
    return [
        dl.Map(
            id=map_id,
            children=[
                dl.TileLayer(),
                dl.LayerGroup(id='site-marker-container'),
                dl.LayerGroup(id='site-confirm-container'),
            ],
            center=center,
            zoom=9,
            doubleClickZoom=False,
            style={"height":"33vh"},
        ),
        dcc.Store(id='potential-site-location'),
        dcc.Store(id='site-location')
        ]

def create_latlon_input():
    return [
        html.Span(get_icon('latlon'), style={'font-size':'1.5rem'}),
        html.Span("(", style={'margin-right': '0.2rem'}),
        dcc.Input(id="site-lat-input", type="text", debounce=True, placeholder="Lat", style={'width': "7rem", 'margin-right': '0.2rem'}),
        html.Span(", "),
        dcc.Input(id="site-lon-input", type="text", debounce=True, placeholder="Lon", style={'width': "7rem", 'margin-left': '0.2rem'}),
        html.Span(")", style={'margin-left': '0.2rem'})
    ]

def create_osgb_feedback():
    return [
        html.Span(get_icon('osgb'), style={'font-size':'1.3rem'}),
        html.Span("OSGB:", style={'margin-right': '0.2rem'}),
        html.Span("(", style={'margin-right': '0.2rem'}),
        html.Span("easting", id="site-osgb-easting-text"),
        html.Span(", "),
        html.Span("northing", id="site-osgb-northing-text"),
        html.Span(")", style={'margin-left': '0.2rem'})
    ]

def create_site_selector_map(map_id='sitemap',
                             center=(53.165716, -3.728402)):
    elements = html.Div(
        [
            dbc.Row([
                dbc.Col(
                    create_map_layout(map_id, center),
                    width=12
                )
            ]),
            dbc.Row([
                dbc.Col(
                    html.H1("Site Name", 
                            contentEditable="true", 
                            id='site-name-input',
                            className='p-2 m-1'
                            ),
                    width=12,
                    lg=6
                ),
                dbc.Col([
                    dbc.Row(
                        html.Div(
                            html.H4(create_latlon_input()),
                            style={"display": "flex", 
                                   "justifyContent": "flex-end", 
                                   "alignItems": "center", 
                                   "width": "100%"}
                        ),
                        id='latlon-container',
                        align='start'
                    ),
                    dbc.Row(
                        html.Div(
                            html.H5(create_osgb_feedback()),
                            style={"display": "flex", 
                                   "justifyContent": "flex-end", 
                                   "alignItems": "center", 
                                   "width": "100%"}
                        ),
                        id='osgb-container',
                        align='start'
                    ),
                    ],
                    width=12,
                    lg=6,
                    align='start'
                ),
            ],
            justify='between')
        ]
    )
    return elements

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
                  debounce='true',
                  style={
                    'display':'inline-block',
                    'float':'right',
                    'width':'30%'
                  })
    ])

def create_configuration_selector():
    return html.Div([
        dbc.Row([
        dbc.Col(
            html.H1([
                get_icon('config-1'),
                html.Span("Configuration Name", contentEditable="true", id='config-name-input', style={"padding": "10px"}),
                dbc.Button(html.I(className="bi bi-floppy", style={'display': 'inline'}), color="primary", id='config-save-btn', outline=True)                    
            ])
        )
    ]),
    dbc.Row(
        dbc.Col([
            html.H2([
                html.I(className="bi bi-arrow-return-right text-secondary", style={"margin-left":"1.0rem", "margin-right":"1.0rem"}),
                dbc.Button(html.I(className="bi bi-plus-circle"), color="primary", id='add-comparator-btn', outline=True, disabled=True, className="rounded-circle")
            ])
            
        ],
        id='comparator-selector-container')
    )])

def create_generation_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('generation'), 'Generation'], className='card-title'),
            html.H4([
                'Total generation: ',
                get_icon('gen-wind','p-1 my-1, ml-1', 'unpadded'),
                " = ",
                html.Span("0.0", id='gen-smry-wind-cap'),
                " kW; ",
                get_icon('gen-pv','p-1 my-1, ml-1', 'unpadded'),
                " = ",
                html.Span("0.0", id='gen-smry-solar-cap'),
                " kWp"
            ],
            className='card-subtitle'),
            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('gen-wind', 'Wind Capacity (kW rated)', 'wind-capacity-input')    
                    ),
                    dbc.Row(
                        create_numeric_card_input('gen-pv', 'Solar PV Capacity (kWp)', 'solar-capacity-input')
                    )
                ])
            ])
        ])
    ])

def create_storage_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('storage'), "Storage"], 
            className='card-title'),
            
            html.H4([
                'Storage capacity: ',
                html.Span("0.0", id='stor-smry-cap'),
                " kWh"
            ],
            className='card-subtitle'),
            
            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row([
                        create_numeric_card_input('storage', 'Storage Capacity (kWh)', 'storage-capacity-input')
                    ])
                ])
            ])
        ])
    ])

def create_building_consumption_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('consumption-building'), "Building Consumption"], 
            className='card-title'),
            
            html.H4([
                'Site size: ',
                html.Span("0", id="bc-smry-n-units"),
                " units"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row([
                        create_numeric_card_input('consumption-building-nunits', 'No. of households', 'n-unit-input')
                    ]),
                    dbc.Row([
                        create_numeric_card_input('consumption-building-hlp', 'HLP (W/m²/K)', 'hlp-input')
                    ]),
                    dbc.Row([
                        create_numeric_card_input('consumption-building-gfa', 'Mean GFA (m²/household)', 'gfa-input')
                    ]),
                    # TODO: Output Fabric Energy Efficiency here
                    dbc.Row([
                        create_numeric_card_input('consumption-building-dhw-ref', 'Reference hot water demand (kWh/day)', 'ref-hotwater-input')
                    ]),
                    dbc.Row([
                        create_numeric_card_input('consumption-building-dhw-var', 'Seasonal variation (%)', 'variation-hotwater-input')
                    ])
                    # TODO: Output annual DHW demand
                ])
            ])
        ])
    ])

def create_direct_consumption_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('consumption-direct'), 'Direct Consumption'],
            className='card-title'),
            
            html.H4([
                get_icon('consumption-direct-appliance'),
                " = ",
                html.Span("0.0", id="cons-smry-app"),
                " kWh/yr; ",
                get_icon('consumption-direct-ev'),
                " = ",
                html.Span("0.0", id="cons-smry-ev"),
                " kWh/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('consumption-direct-appliance-reduction', 'High-efficiency appliances consumption reduction (%)', 'app-efficiency-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('consumption-direct-ev-anncharge', 'Residential charging per EV (kWh/yr)', 'ev-ann-charge-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('consumption-direct-ev-nperunit', 'EVs per household (n)', 'ev-per-unit-input')
                    ),
                ])
            ])
        ])
    ])

def create_gen_cost_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-generation'), 'Generation Costs'],
            className='card-title'),

            html.H4([
                "Capital cost = £",
                html.Span("0", id="cost-gen-smry-capex"),
                "; Ongoing costs = £",
                html.Span("0", id="cost-gen-smry-ongoing"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('gen-wind', 'Wind Capex (£/kW)', 'cost-gen-wind-capex-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input(['gen-wind','cost-recurrent'], 'Wind Ongoing (£/kW/yr)', 'cost-gen-wind-ongoing-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('gen-pv', 'Solar PV Capex (£/kWp)', 'cost-gen-pv-capex-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input(['gen-pv','cost-recurrent'], 'Solar PV Ongoing (£/kWp/yr)', 'cost-gen-pv-ongoing-input')
                    ),
                ])
            ])
        ]),
    ])

def create_storage_cost_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-storage'), 'Storage Costs'],
            className='card-title'),

            html.H4([
                "Capital cost = £",
                html.Span("0", id="cost-stor-smry-capex"),
                "; Ongoing costs = £",
                html.Span("0", id="cost-stor-smry-ongoing"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('storage', 'BESS Capex (£/kWh)', 'cost-stor-bess-capex-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input(['storage', 'cost-recurrent'], 'BESS Ongoing (£/kWh/yr)', 'cost-stor-bess-ongoing-input')
                    ),
                ])
            ])
        ])
    ])

def create_sales_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-sales'), 'Sales'],
            className='card-title'),

            html.H4([
                get_icon('cost-residents'),
                " = £",
                html.Span("0", id="cost-sales-smry-residents"),
                "/yr; ",
                get_icon('cost-export'),
                " = £",
                html.Span("0", id="cost-sales-smry-export"),
                "/yr"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('cost-residents-standing', 'Standing charge (£/houshold/day)', 'resident-standing-charge-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('cost-residents-perunit', 'Per unit charge (£/kWh)', 'resident-per-unit-charge-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('cost-export', '"Grid export - mean per unit charge (£/kWh)', 'export-per-unit-charge-input')
                    ),
                ])
            ])
        ])
    ])

def create_import_cost_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost-import'), 'Import Costs'],
            className='card-title'),

            html.H4([
                "Fixed costs = £",
                html.Span("0", id="cost-import-smry-fixed"),
                "/yr; Ongoing costs = £",
                html.Span("0", id="cost-import-smry-ongoing"),
                "/kWh"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('cost-import-fixed', 'Fixed costs for backup (£/site/day)', 'fixed-costs-import-input')
                    ),
                    dbc.Row(
                        create_numeric_card_input('cost-import-perunit', 'Per-unit costs for backup (£/kWh)', 'per-unit-costs-import-input')
                    ),
                ])
            ])
        ])
    ])

def create_model_settings_input_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('model-settings'), 'Model Settings'],
            className='card-title'),

            html.H4([
                get_icon('model-settings-time-horizon'),
                " = ",
                html.Span("10", id="mdl-smry-horizon"),
                " years"
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary(""),
                html.Div([
                    dbc.Row(
                        create_numeric_card_input('model-settings-time-horizon', 'Time horizon (years)', 'mdl-timehorizon-input')
                    )
                ])
            ])
        ]),
    ])

def create_results_header():
    return dbc.Row([
        html.H1([get_icon('results'), 'Results'],
        style={
            'display': 'inline-block',
            'width':'50%',
            'float': 'left'
        }),

        html.Span([
            html.H5("Per year",style={'display': 'inline-block', 'vertical-align': 'middle'}),
            daq.ToggleSwitch(style={'display': 'inline-block', 'vertical-align': 'middle','padding': "10px"}),
            html.H5('To horizon',style={'display': 'inline-block', 'vertical-align': 'middle'})
        ],
        style={
            'display': 'inline-block',
            'width':'50%',
            'float': 'right',
            "justifyContent": "flex-end",
            "alignItems": "center",
            'text-align': 'right'
        })
    ],
    style={'display': 'flex'}
    )

def create_generation_results_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('generation'), 'Generation Results'],
            className='card-title'),

            html.H4([
                'Annual generation: ',
                get_icon('gen-wind'),
                " = ",
                html.Span("0.0", id='gen-ressmry-wind-prod'),
                " kWh; ",
                get_icon('gen-pv'),
                " = ",
                html.Span("0.0", id='gen-ressmry-solar-prod'),
                " kWh"
            ],
            id='gen-ressmry-container',
            className='card-subtitle'),

            html.Details([
                html.Summary("Wind Generation"),
                html.Div([
                    create_wind_results()
                    ],
                    id="gen-res-wind-tbl")
                
            ]),
            html.Details([
                html.Summary("Solar PV Generation"),
                html.Div([
                    create_pv_results()
                    ],
                    id="gen-res-pv-tbl")
            ]),

            html.Details([
                html.Summary("Total Generation"),
                html.Div([
                    create_combined_generation_results()
                    ],
                    id="gen-res-combined-tbl")
            ])
        ])
    ])

def create_storage_results_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('storage'), 'Storage Results'],
            className='card-title'),

            html.H4([
                'Hours full = ',
                html.Span("0", id='stor-ressmry-hours-full'),
                "; Hours empty = ",
                html.Span("0", id='stor-ressmry-hours-empty'),
                "; Charge cycles = ",
                html.Span("0", id='stor-ressmry-charge-cycles')
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Storage'),
                html.Div([
                    create_stor_results()
                ],
                id='stor-res-tbl')
            ])
        ])
    ])

def create_consumption_results_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('consumption-direct'), 'Consumption Results'],
            className='card-title'),

            html.H4([
                'Annual consumption: ',
                get_icon('consumption-building'),
                ' = ',
                html.Span('0.0', id='cons-ressmry-resident'),
                ' kWh; ',
                get_icon('consumption-direct-ev'),
                ' = ',
                html.Span('0.0', id='cons-ressmry-ev'),
                ' kWh'                
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Consumption'),
                html.Div([
                    create_cons_results()
                ],
                id='cons-res-tbl')
            ]),

            html.Details([
                html.Summary('Seasonal Consumption'),
                html.Div([
                    create_seasonal_cons_results()
                ],
                id='cons-res-seasonal-tbl')
            ])
        ])
    ])

def create_net_results_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('import-export'), 'Net Energy Results'],
            className='card-title'),

            html.H4([
                'Annual export = ',
                html.Span('0.0', id = 'net-ressmry-export'),
                ' kWh; Annual import = ',
                html.Span('0.0', id = 'net-ressmry-import'),
                ' kWh; Storage losses = ',
                html.Span('0.0', id = 'net-ressmry-storloss'),
                ' kWh'
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Overall net energy'),
                html.Div([
                    create_net_results()
                ],
                id='net-res-tbl')
            ]),

            html.Details([
                html.Summary('Seasonal net energy'),
                html.Div([
                    create_seasonal_net_results()
                ],
                id='net-res-seasonal-tbl')
            ])
        ])
    ])

def create_economic_results_so_card():
    return dbc.Card([
        dbc.CardBody([
            html.H2([get_icon('cost'), 'Financial Results - System Owner'],
            className='card-title'),

            html.H4([
                'Total benefits (',
                html.Span('0%', id='econ-ressmry-dr-benefits'),
                ') = ',
                html.Span('£0.00', id='econ-ressmry-npbenefits'),
                '; Total costs (',
                html.Span('0%', id='econ-ressmry-dr-costs'),
                ') = ',
                html.Span('£0.00', id='econ-ressmry-npcosts'),
                '; NPV = ',
                html.Span('£0.00', id='econ-ressmry-npv'),
            ],
            className='card-subtitle'),

            html.Details([
                html.Summary('Benefits'),
                html.Div([
                    create_so_benefits_results()
                ],
                id='econ-res-benefits-tbl')
            ]),

            html.Details([
                html.Summary('Costs'),
                html.Div([
                    create_so_costs_results()
                ],
                id='econ-res-cost-tbl')
            ]),

            html.Details([
                html.Summary('Value'),
                html.Div([
                    create_so_value_results()
                ],
                id='econ-res-value-tbl')
            ]),
        ])
    ])

def create_layout():
    mapview = [create_site_selector_map()] \
        + [
            html.Div([

        html.Hr(),

        # Site details

        dbc.Row([
            dbc.Col([
                create_generation_input_card()
            ],
            lg = 6),
            dbc.Col([
                create_storage_input_card()
            ],
            lg = 6),
        ]),
        dbc.Row([
            dbc.Col([
                create_building_consumption_input_card()
            ],
            lg = 6
            ),
            dbc.Col([
                create_direct_consumption_input_card()
            ],
            lg = 6
            ),
        ]),

        html.Hr(),
        
        # Financial details

        dbc.Row([
            dbc.Col([
                create_gen_cost_input_card()
            ],
            lg=6),
            dbc.Col([
                create_storage_cost_input_card()
            ],
            lg=6),
        ]),
        dbc.Row([
            dbc.Col([
                create_sales_input_card()
            ],
            lg=6),
            dbc.Col([
                create_import_cost_input_card()
            ],
            lg=6),
        ]),

        html.Hr(),
        
        # Model settings

        dbc.Row([
            dbc.Col([
                create_model_settings_input_card()
            ],
            width=12)
        ]),

        html.Hr(),
        
        # Results

        create_results_header(),

        create_configuration_selector(),
        
        dbc.Row([
            dbc.Col([
                create_generation_results_card()
            ],
                width=12),
            dbc.Col([
                create_storage_results_card()
            ],
                width=12),
            dbc.Col([
                create_consumption_results_card()
            ],
                width=12),
            dbc.Col([
                create_net_results_card()
            ],
                width=12),
            dbc.Col([
                create_economic_results_so_card()
            ],
                width=12)
        ]),
    ])
    ]

    return dbc.Container(mapview, fluid=False)
    
def serve_layout():
    session_id = str(uuid.uuid4())

    return html.Div([
        create_layout(),
        dcc.Store(data=session_id, id='session-id')
    ])

def create_app(external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.BOOTSTRAP]):
    app = Dash(external_stylesheets=external_stylesheets)
    app.layout = serve_layout

    app = add_map_click_callback(app)
    app = add_latlon_sync_callbacks(app)
    app = add_potential_site_change_callback(app)
    app.config.suppress_callback_exceptions = True
    app = add_confirm_site_change_btn_callback(app)
    app.config.suppress_callback_exceptions = False

    app=add_remove_confirm_popup(app)
    app = add_site_change_callback(app)

    app.title = "Sprake Energy Model"

    return app

def add_latlon_sync_callbacks(app):
    @app.callback(
        Output('site-location', 'data', allow_duplicate=True),
        Input('site-lat-input', 'value'),
        Input('site-lon-input', 'value'),
        State('site-location', 'data'),
        prevent_initial_call=True
    )
    def sync_inputs_to_store(lat_val, lon_val, current_site):
        if lat_val is None or lon_val is None:
            return no_update
        try:
            lat = float(lat_val)
            lon = float(lon_val)
        except (TypeError, ValueError):
            return no_update
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            return no_update
        easting,northing = _trans_togb.transform(lat, lon)
        new_site = json.dumps({'lat': lat, 'lon': lon, 'easting': easting, 'northing': northing})
        if new_site == current_site:
            return no_update
        return new_site

    @app.callback(
        Output('site-lat-input', 'value'),
        Output('site-lon-input', 'value'),
        Input('site-location', 'data'),
        prevent_initial_call=True
    )
    def sync_store_to_inputs(site_loc):
        if site_loc is None:
            return no_update, no_update
        try:
            coords = json.loads(site_loc)
            lat = float(coords.get('lat', ''))
            lon = float(coords.get('lon', ''))
        except (TypeError, ValueError, json.JSONDecodeError, AttributeError):
            return no_update, no_update
        return f"{lat:.6f}", f"{lon:.6f}"

    return app

def add_map_click_callback(app):
    @app.callback(
        Output('potential-site-location', 'data'),
        Input('sitemap', 'dblclickData'),
        State('potential-site-location', 'data'),
        prevent_initial_call=True
    )
    def change_site_loc(click_data, current_val):
        if not current_val is None:
            coords = json.loads(current_val)
            pos = [float(coords['lat']), float(coords['lon'])]
            if pos[0] == 0 and pos[1] == 0:
                return []
        if not click_data is None:
            coordinates = click_data['latlng']
            lat, lon = coordinates.values()
            easting,northing = _trans_togb.transform(lat, lon)
            return json.dumps({'lat':lat,'lon':lon, 'easting': easting, 'northing': northing})
        else:
            return json.dumps({'lat':0,'lon':0})
    return app

def add_potential_site_change_callback(app):
    @app.callback(
        Output('site-confirm-container', 'children',allow_duplicate=True),
        Input('potential-site-location', 'data'),
        prevent_initial_call=True
        
    )
    def change_potential_site(json_latlon):
        coords = json.loads(json_latlon)
        pos = [float(coords['lat']), float(coords['lon'])]
        if pos[0] == 0 and pos[1] == 0:
            return []
        else:
            return [dl.Popup(id={'type': 'confirm-site-popup', 'index':0},
                             position = pos,
                             children = [
                                html.Span(
                                    children = [
                                        html.H4("Confirm site change"),
                                        html.H5(f"({pos[0]:.3f}, {pos[1]:.3f})"),
                                        html.I(className="bi bi-geo-alt-fill btn btn-primary",
                                               style={"font-size":"2rem"},
                                               id={'type': 'confirm-site-popup-btn', 'index':1})
                                    ],
                                    style = {
                                        "display": "table-cell",
                                        "text-align": "center"
                                    }
                                )
                             ]
                             )]
    return app

def add_confirm_site_change_btn_callback(app):
    @app.callback(
        Output('site-location', 'data', allow_duplicate=True),
        Input({'type': 'confirm-site-popup-btn', 'index': ALL}, 'n_clicks'),
        State('potential-site-location', 'data'),
        prevent_initial_call=True
    )
    def change_site(click_data, json_latlon):
        if click_data[0] is None:
            return no_update
        return json_latlon
    return app

def add_remove_confirm_popup(app):
    @app.callback(
        Output('site-confirm-container', 'children'),
        Input('site-location', 'data'),
        prevent_initial_call=True,
        allow_duplicate=True
    )
    def remove_confirm_popup(site_loc):
        return []
    return app

def add_site_change_callback(app):
    @app.callback(
        Output('site-marker-container', 'children'),
        Output('site-osgb-easting-text', 'children'),
        Output('site-osgb-northing-text', 'children'),
        Input('site-location', 'data'),
        prevent_initial_call=True
    )
    def add_site_marker(json_latlon):
        coords = json.loads(json_latlon)
        pos = [float(coords['lat']), float(coords['lon'])]
        return ([dl.Marker(id='site-marker',
                          position=pos,
                          children=[dl.Tooltip("Site Location")])], 
                          f"{float(coords['easting']):,.0f}",
                          f"{float(coords['northing']):,.0f}")
    return app


if __name__=="__main__":
    app = create_app()

    app.run(debug=True)