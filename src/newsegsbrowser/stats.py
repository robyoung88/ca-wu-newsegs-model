from dash import html

ANNUAL_DEFAULT_STATS = [
                                {'label':'Mean',
                                 'value':'mean'},
                                {'label':'Max',
                                 'value':'max'},
                                {'label':'Min',
                                 'value':'min'}
                             ]

TOTAL_DEFAULT_STATS = [
                            {'label':'Total',
                             'value':'sum'}
                            ]

ANNUAL_SEASONAL_STATS = [
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

TOTAL_SEASONAL_STATS = [
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

DEFAULT_HOURS_IN_RANGE_STATS = [
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
     'value':'hrs_095_to_999'}
    ]

DEFAULT_DAYS_IN_RANGE_STATS = [
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

def DEFAULT_STAT_FORMATTER(stat_dict):
    return str(stat_dict)

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

def present_stat_description_compound(data_list,
                                      stat_name,
                                      stat_label,
                                      stat_formatter=DEFAULT_STAT_FORMATTER,
                                      stat_list=DEFAULT_HOURS_IN_RANGE_STATS):
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
    