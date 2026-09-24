"""Register restult container and result header container content creators"""

import dash
from dash import html
import pandas as pd

from newsegsmodelapp.components import icons
from newsegsmodelapp.registers import register_result_container_content_creator, register_result_section_header_content_creator, register_table_subindex_map
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

# -----------------------------------------------
# Contents
# -----------------------------------------------

def _create_results_details(
    title: str | dash.development.base_component.Component | list[str | dash.development.base_component.Component],
    triggering_action_type: str,
    triggering_action_class: str,
    supersection: str = 'deterministic',
    subindex: int = 0
):
    """
    A html.Details holding the (blank) results table defined by the function.

    Use this to ensure that the created container is given an id that matches
    the function key.
    """
    return html.Details([
        html.Summary(title),
        html.Div(
            id = {
                'type': 'result-table', 'purpose': 'container',
                'supersection': supersection, 'section': triggering_action_class,
                'key': triggering_action_type, 'subindex': subindex
            })
    ])

MODEL_TYPE = 'sprake'
SECTION = 'tabledraw'

KEY = 'table_generation'

# Mapping between subindex and the table name to take from the provider
TABLE_GENERATION_SUBINDEX_MAPPING = register_table_subindex_map(
    {
        1: 'table_generation_wind',
        2: 'table_generation_pv',
        3: 'table_generation_combined',
    },
    KEY, MODEL_TYPE
)

@register_result_container_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface, 
    key_: str = KEY, # Using default argument trick to force evaluation of section
    section_: str = SECTION,
) -> list[dash.development.base_component.Component]:
    return [
        _create_results_details(
            'Wind Generation',
            key_,
            section_,
            subindex = 1
        ),

        _create_results_details(
            'Solar PV Generation',
            key_,
            section_,
            subindex = 2
        ),

        _create_results_details(
            'Total Generation',
            key_,
            section_,
            subindex = 3
        ),
    ]

KEY = 'table_storage'
@register_result_container_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface, 
    key_: str = KEY, # Using default argument trick to force evaluation of section
    section_: str = SECTION,
) -> list[dash.development.base_component.Component]:
    return [
        _create_results_details(
            'Storage',
            key_,
            section_,
        ),
    ]

KEY = 'table_consumption'

# Mapping between subindex and the table name to take from the provider
TABLE_STORAGE_SUBINDEX_MAPPING = register_table_subindex_map(
    {
        1: 'table_consumption',
        2: 'table_consumption_seasonal',
    },
    KEY, MODEL_TYPE
)

@register_result_container_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface, 
    key_: str = KEY, # Using default argument trick to force evaluation of section
    section_: str = SECTION,
) -> list[dash.development.base_component.Component]:
    return [
        _create_results_details(
            'Consumption',
            key_,
            section_,
            subindex = 1,
        ),

        _create_results_details(
            'Seasonal Consumption',
            key_,
            section_,
            subindex = 2
        ),
    ]

KEY = 'table_net'

TABLE_NET_SUBINDEX_MAPPING = register_table_subindex_map(
    {
        1: 'table_net',
        2: 'table_net_seasonal'
    },
    KEY, MODEL_TYPE
)

@register_result_container_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface, 
    key_: str = KEY, # Using default argument trick to force evaluation of section
    section_: str = SECTION,
) -> list[dash.development.base_component.Component]:
    return [
        _create_results_details(
            'Overall net energy',
            key_,
            section_,
            subindex = 1
        ),

        _create_results_details(
            'Seasonal net energy',
            key_,
            section_,
            subindex = 2
        ),
    ]

KEY = 'table_finance'

TABLE_FINANCE_SUBINDEX_MAPPING =register_table_subindex_map(
    {
        1: 'table_finance_so_benefits',
        2: 'table_finance_so_costs',
        3: 'table_finance_so_value',
    },
    KEY, MODEL_TYPE
)

@register_result_container_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface, 
    key_: str = KEY, # Using default argument trick to force evaluation of section
    section_: str = SECTION,
) -> list[dash.development.base_component.Component]:
    return [
        _create_results_details(
            'Benefits',
            key_,
            section_,
            subindex = 1,
        ),

        _create_results_details(
            'Costs',
            key_,
            section_,
            subindex = 2,
        ),

        _create_results_details(
            'Value',
            key_,
            section_,
            subindex = 3
        ),
    ]

# -----------------------------------------------
# Header content
# -----------------------------------------------

SECTION = 'postprocess'
KEY = 'postproc_generation'

def _make_generation_result_header(
    res,
    ann_hori_toggle: bool,
):
    def _content_function(
        total = 0.0,
        wind = 0.0,
        pv = 0.0,
        intro_string = 'Total generation:' if ann_hori_toggle else 'Annual generation'
    ):
        return [
            intro_string,
            icons.get_icon('generation'),
            " = ",
            html.Span(f'{total:,.1f}'),
            " kWh; ",
            icons.get_icon('gen-wind'),
            " = ",
            html.Span(f'{wind:,.1f}'),
            " kWh; ",
            icons.get_icon('gen-pv'),
            " = ",
            html.Span(f'{pv:,.1f}'),
            " kWh"
        ]

    if res is None:
        return _content_function()
        
    gm = res.get('generator_meter_summary')
    if gm is None:
        return _content_function()
    
    if ann_hori_toggle:
        wind = gm.get('wind_export').get('sum')
        pv = gm.get('solar_export').get('sum')
    else:
        wind = gm.get('wind_export').get('mean')
        pv = gm.get('solar_export').get('mean')

    total = wind + pv

    return _content_function(total, wind, pv)

@register_result_section_header_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    ann_hori_toggle: bool = True,
    key_: str = KEY # Using default argument trick to force evaluation of section
) -> list[dash.development.base_component.Component]:
    proj = proj_provider.get_project(proj_id)
    mm = proj.get_focussed_metamodel()
    mod = mm.model.table_config

    res, rev = result_provider.get_result(key_, mod)
    return _make_generation_result_header(res, ann_hori_toggle)

SECTION = 'postprocess'
KEY = 'postproc_storage'
def _make_storage_result_header(
    res,
    ann_hori_toggle: bool,
):
    def _content_function(
        hrs_full = 0.0,
        hrs_empty = 0.0,
        cc = 0.0,
    ):
        return [
            'Hours full = ',
            html.Span(f'{hrs_full:,.0f}'),
            "; Hours empty = ",
            html.Span(f'{hrs_empty:,.0f}'),
            "; Charge cycles = ",
            html.Span(f'{cc:,.0f}')
        ]

    if res is None:
        return _content_function()
        
    hrs_full = res.get('stor_hours_at_max').get('hrs_at_max_soc')
    hrs_empty = res.get('stor_hours_at_min').get('hrs_at_min_soc')
    cc = res.get('no_charge_cycles').get('charge_cycles')

    if ann_hori_toggle:
        stat='sum'
    else:
        stat='mean'
    
    hrs_full = hrs_full.get(stat)
    hrs_empty = hrs_empty.get(stat)
    cc = cc.get(stat)

    return _content_function(hrs_full, hrs_empty, cc)

@register_result_section_header_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    ann_hori_toggle: bool = True,
    key_: str = KEY # Using default argument trick to force evaluation of section
) -> list[dash.development.base_component.Component]:
    proj = proj_provider.get_project(proj_id)
    mm = proj.get_focussed_metamodel()
    mod = mm.model.table_config

    res, rev = result_provider.get_result(key_, mod)
    return _make_storage_result_header(res, ann_hori_toggle)

SECTION = 'postprocess'
KEY = 'postproc_consumption'
def _make_consumption_result_header(
    res,
    ann_hori_toggle: bool,
):
    def _content_function(
        residential_cons = 0.0,
        ev_cons = 0.0,
        intro_string = 'Total consumption: ' if ann_hori_toggle else 'Annual consumption: '
    ):
        return [
            intro_string,
            icons.get_icon('consumption-building'),
            ' = ',
            html.Span(f'{residential_cons:,.1f}'),
            ' kWh; ',
            icons.get_icon('consumption-direct-ev'),
            ' = ',
            html.Span(f'{ev_cons:,.1f}'),
            ' kWh'                
        ]

    if res is None:
        return _content_function()
        
    if ann_hori_toggle:
        stat='sum'
    else:
        stat='mean'
    
    residential_cons = res.get('consumption_meter_summaries').get('residential').get(stat)
    ev_cons = res.get('consumption_meter_summaries').get('evcharge_import').get(stat)

    return _content_function(residential_cons, ev_cons)

@register_result_section_header_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    ann_hori_toggle: bool = True,
    key_: str = KEY # Using default argument trick to force evaluation of section
) -> list[dash.development.base_component.Component]:
    proj = proj_provider.get_project(proj_id)
    mm = proj.get_focussed_metamodel()
    mod = mm.model.table_config

    res, rev = result_provider.get_result(key_, mod)
    return _make_consumption_result_header(res, ann_hori_toggle)

SECTION = 'postprocess'
KEY = 'postproc_net'
def _make_net_result_header(
    res,
    ann_hori_toggle: bool,
):
    def _content_function(
        energy_export = 0.0,
        energy_import = 0.0,
        storage_loss = 0.0,
        str_1 = 'Total export = ' if ann_hori_toggle else 'Annual export = ',
        str_2 = 'Total import = ' if ann_hori_toggle else 'Annual import = ',
    ):
        return [
            str_1,
            html.Span(f'{energy_export:,.1f}'),
            ' kWh; ',
            str_2,
            html.Span(f'{energy_import:,.1f}'),
            ' kWh; Storage losses = ',
            html.Span(f'{storage_loss:,.1f}'),
            ' kWh'
        ]

    if res is None:
        return _content_function()
        
    if ann_hori_toggle:
        stat='sum'
    else:
        stat='mean'
        
    ms = (
        pd.DataFrame
        .from_dict(res['meter_summaries'], orient='columns')
        .set_index(['variable', 'statistic'])
    )
    energy_export = ms.loc[('grid_export',stat),'value']
    energy_import = ms.loc[('grid_import',stat),'value']
    storage_loss = ms.loc[('storage_loss',stat),'value']

    return _content_function(energy_export, energy_import, storage_loss) # pyright: ignore[reportArgumentType]

@register_result_section_header_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    ann_hori_toggle: bool = True,
    key_: str = KEY # Using default argument trick to force evaluation of section
) -> list[dash.development.base_component.Component]:
    proj = proj_provider.get_project(proj_id)
    mm = proj.get_focussed_metamodel()
    mod = mm.model.table_config

    res, rev = result_provider.get_result(key_, mod)
    return _make_net_result_header(res, ann_hori_toggle)

SECTION = 'tabledraw'
KEY = 'table_finance'
def _make_finance_result_header(
    res_benefits,
    res_costs,
    res_value,
    ann_hori_toggle: bool,
):
    def _content_function(
        dr_benefits = 0.0,
        prval_benefits = 0.0,
        dr_costs = 0.0,
        prval_costs = 0.0,
        npv= 0.0,
    ):
        return [
            'Total benefits (',
            html.Span(f'{dr_benefits:,.1%}'),
            ') = ',
            html.Span(f'£{prval_benefits:,.2f}'),
            '; Total costs (',
            html.Span(f'{dr_costs:,.1%}'),
            ') = ',
            html.Span(f'£{prval_costs:,.2f}'),
            '; NPV = ',
            html.Span(f'£{npv:,.2f}'),
        ]
    if res_benefits is None or res_costs is None or res_value is None:
        return _content_function()
    dr_benefits = res_benefits.get('benefits_discount_rate')
    prval_benefits = res_benefits.get('present_benefits_discounted')
    dr_costs = res_costs.get('costs_discount_rate')
    prval_costs = res_costs.get('present_costs_discounted')
    value = (
        pd.DataFrame
        .from_dict(res_value.get('value_summaries'), orient='columns')
        .set_index(['variable', 'statistic'])
    )
    npv = value.loc[('net_present_value_discounted','sum'),'value']
    
    return _content_function(dr_benefits, prval_benefits, dr_costs, prval_costs, npv) # pyright: ignore[reportArgumentType]

@register_result_section_header_content_creator(KEY, SECTION, MODEL_TYPE)
def _(
    proj_id: str, 
    proj_provider: NewsegsProjectProviderInterface,
    result_provider: NewsegsResultProviderInterface,
    ann_hori_toggle: bool = True,
) -> list[dash.development.base_component.Component]:
    proj = proj_provider.get_project(proj_id)
    mm = proj.get_focussed_metamodel()
    mod = mm.finance.table_config

    res_benefits, rev_benefits = result_provider.get_result('postproc_finance_benefits', mod)
    res_costs, rev_costs = result_provider.get_result('postproc_finance_costs', mod)
    res_value, rev_value = result_provider.get_result('postproc_finance_value', mod)
    return _make_finance_result_header(res_benefits, res_costs, res_value, ann_hori_toggle)
