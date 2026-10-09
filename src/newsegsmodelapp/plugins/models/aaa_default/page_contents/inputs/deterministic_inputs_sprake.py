"""Register input container and input header container content creators for deterministic supersection"""

import json
from typing import cast

import dash
from dash import html
from dash.exceptions import PreventUpdate
from cachetools import LRUCache

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelapp.components import energy_balance_estimation
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_lightweight_metamodel, get_focussed_metamodel
from newsegsmodelapp.components.composite_input_components import generic_create_deterministic_input_container_contents
from newsegsmodelapp.components import icons
from newsegsmodelapp.registers import register_input_container_content_creator, register_input_section_header_content_creator
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsvariable import variable

from ...utils.update_energy_balance_sprake import update_estimated_energy_balance

from newsegsmodelapp import APP_ROOT
_CONST_FILE = APP_ROOT / 'newsegsmodelframework' / 'constants' / 'model_constants.json'
with open(_CONST_FILE, 'r') as f:
    MODEL_CONSTANTS = json.load(f)

MODEL_TYPE = 'sprake'

sections_by_supersection = {
    'deterministic': (
        'gen_input',
        'stor_input',
        'bc_input',
        'dc_input',
        'mc_input',
        'gen_costs',
        'stor_costs',
        'sales_costs',
        'import_costs',
        'finance_settings',
    )
}

# Removing cache, as the variable badge status doesn't update on project / metamodel switch otherwise
#_cache = LRUCache(maxsize = 50)

for supersection, section_tuple in sections_by_supersection.items():
    for section in section_tuple:
        @register_input_container_content_creator(supersection, section, MODEL_TYPE)
        def _(
            proj_id: str, 
            project_provider: NewsegsProjectProviderInterface, 
            _section: str = section # Using default argument trick to force evaluation of section
        ) -> list[dash.development.base_component.Component]:
            provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
            lproj = provider.get_lightweight_project(proj_id)
            lmm = lproj.metamodels[[x.id for x in lproj.metamodels].index(lproj.focussed_metamodel_id)]
            
            #proj = proj_provider.get_project(proj_id)
            #mm = proj.get_focussed_metamodel()
            #key = (_section, proj.id, mm.id)
            #if key in _cache:
            #    return _cache[key]

            component = generic_create_deterministic_input_container_contents(
                _section, lproj, lmm, provider.variable_provider
            )
            #_cache[key] = component

            return component


#################################################
# HEADER FUNCTIONS
#################################################
def _get_val(lmm, key, variableprovider: FromDatabaseVariableProvider) -> int | float:
    var = variableprovider.get_lightweight_variable(lmm.variables.get(key))
    return var.last_deterministic_value

def _create_generation_header_summary(mm, provider):
    wind_cap = _get_val(mm, 'gen_input.wind_capacity.0', provider)
    pv_cap = _get_val(mm, 'gen_input.pv_capacity.0', provider)
    return [
        'Total generation: ',
        icons.get_icon('gen-wind','p-1 my-1 ms-1', 'unpadded'),
        " = ",
        html.Span(f"{wind_cap:,.1f}"),
        " kW; ",
        icons.get_icon('gen-pv','p-1 my-1 ms-1', 'unpadded'),
        " = ",
        html.Span(f"{pv_cap:,.1f}",),
        " kWp"
    ]

def _create_storage_header_summary(mm, provider):
    stor_cap = _get_val(mm, 'stor_input.storage_capacity.0', provider)
    return [
        'Storage capacity: ',
        html.Span(f"{stor_cap:,.0f}"),
        " kWh"
    ]

def _create_bc_header_summary(mm, provider):
    site_size = _get_val(mm, 'bc_input.n_units.0', provider)
    return [
        'Site size: ',
        html.Span(f"{site_size:,.0f}"),
        " units"
    ]

def _create_dc_header_summary(mm, provider):
    efficiency_reduction = _get_val(mm, 'dc_input.efficiency_reduction.0', provider)
    n_evs_per_household = _get_val(mm, 'dc_input.n_evs_per_household.0', provider)
    ev_consumption_per_year = _get_val(mm, 'dc_input.annual_residential_consumption_per_ev.0', provider)
    ann_appliance = (
        (1.0 - float(efficiency_reduction))  # pyright: ignore[reportArgumentType]
        * MODEL_CONSTANTS['sprake_model']['sprake_ref_appliance_consumption_annual']
    )
    ann_ev = (
        n_evs_per_household * ev_consumption_per_year
    ) # pyright: ignore[reportOperatorIssue]

    return [
        icons.get_icon('consumption-direct-appliance'),
        " = ",
        html.Span('{:,.0f}'.format(ann_appliance)),
        " kWh/yr/household; ",
        icons.get_icon('consumption-direct-ev'),
        " = ",
        html.Span('{:,.0f}'.format(ann_ev)),
        " kWh/yr/household"
    ]

def _create_model_config_header_summary(mm, provider):
    time_horizon = _get_val(mm, 'mc_input.horizon.0', provider)
    return [
        icons.get_icon('model-settings-time-horizon'),
        " = ",
        html.Span(f"{time_horizon:.0f}"),
        " years"
    ]

def _create_cost_generation_header_summary(mm, provider):
    wind_cap = _get_val(mm, 'gen_input.wind_capacity.0', provider)
    pv_cap = _get_val(mm, 'gen_input.pv_capacity.0', provider)
    capex_rate_wind = _get_val(mm, 'gen_costs.wind_capex_per_kw.0', provider)
    capex_rate_pv = _get_val(mm, 'gen_costs.pv_capex_per_kw.0', provider)
    om_rate_wind = _get_val(mm, 'gen_costs.wind_om_per_kw_year.0', provider)
    om_rate_pv = _get_val(mm, 'gen_costs.pv_om_per_kw_year.0', provider)

    tot_capex = (
        capex_rate_wind * wind_cap
        + capex_rate_pv * pv_cap
    )

    tot_ongoing = (
        om_rate_wind * wind_cap
        + om_rate_pv * pv_cap
    )
    return [
        "Capital cost = £",
        html.Span('{:,.0f}'.format(tot_capex)),
        "; Ongoing costs = £",
        html.Span('{:,.0f}'.format(tot_ongoing)),
        "/yr"
    ]

def _create_cost_storage_header_summary(mm, provider):
    stor_cap = _get_val(mm, 'stor_input.storage_capacity.0', provider)
    capex_rate_bess = _get_val(mm, 'stor_costs.bess_capex_per_kwh.0', provider)
    om_rate_bess = _get_val(mm, 'stor_costs.bess_om_per_kwh_year.0', provider)

    tot_capex = capex_rate_bess * stor_cap
    tot_ongoing = om_rate_bess * stor_cap

    return [
        "Capital cost = £",
        html.Span('{:,.0f}'.format(tot_capex)),
        "; Ongoing costs = £",
        html.Span('{:,.0f}'.format(tot_ongoing)),
        "/yr"
    ]

def _create_cost_sales_header_summary(
        mm,
        provider,
        eb: energy_balance_estimation.EstimatedEnergyBalance | None = None
    ):
    if eb is None:
        eb = energy_balance_estimation.EstimatedEnergyBalance()
        eb = update_estimated_energy_balance(mm, provider, eb)
    
    n_units = _get_val(mm, 'bc_input.n_units.0', provider)

    standing_charge = _get_val(mm, 'sales_costs.resident_sc_per_unit_day.0', provider)
    per_unit_resident = _get_val(mm, 'sales_costs.resident_var_per_unit.0', provider)
    per_unit_ev = per_unit_resident

    per_unit_export = _get_val(mm, 'sales_costs.grid_export_var_per_unit.0', provider)

    aeb = eb.estimated_annual_energy_balance

    resident_consumption = (
        aeb
        .query('type == "Consumption"')
        .query('label != "EV charging"')
        .loc[:, 'value']
        .sum()
    )

    ev_consumption = (
        aeb
        .query('label == "EV charging"')
        .loc[:, 'value']
        .sum()
    )

    generation = (
        aeb
        .query('label == "Generation"')
        .loc[:, 'value']
        .sum()
    )

    overproduction = generation - (resident_consumption + ev_consumption)
    if overproduction < 0:
        overproduction = 0

    res_receipts = 365 * standing_charge * n_units + resident_consumption * per_unit_resident
    ev_receipts = ev_consumption * per_unit_ev

    estimated_export_receipts = overproduction * per_unit_export

    tot_receipts = res_receipts + ev_receipts + estimated_export_receipts

    return [
        icons.get_icon('cost-residents'),
        " ≈ £",
        html.Span(f'{float(f'{res_receipts:.2g}'):,.0f}'),
        "/yr; ",
        icons.get_icon('cost-ev'),
        " ≈ £",
        html.Span(f'{float(f'{ev_receipts:.2g}'):,.0f}'),
        "/yr; ",
        icons.get_icon('cost-export'),
        " >≈ £",
        html.Span(f'{float(f'{estimated_export_receipts:.2g}'):,.0f}'),
        "/yr; ",
        html.H3("Σ ", style={'display': 'inline'}),
        " ≈ £",
        html.Span(f'{float(f'{tot_receipts:.2g}'):,.0f}'),
        "/yr"
    ]

def _create_cost_import_header_summary(
        mm, provider,
        eb: energy_balance_estimation.EstimatedEnergyBalance | None = None
    ):
    if not eb:
        eb = energy_balance_estimation.EstimatedEnergyBalance()
        eb = update_estimated_energy_balance(mm, provider, eb)

    aeb = eb.estimated_annual_energy_balance
    total_consumption = (
        aeb
        .query('type == "Consumption"')
        .loc[:, 'value']
        .sum()
    )
    total_generation = (
        aeb
        .query('label == "Generation"')
        .loc[:, 'value']
        .sum()
    )

    underproduction = total_consumption - total_generation
    if underproduction < 0:
        underproduction = 0
    
    standing_charge = _get_val(mm, 'import_costs.grid_import_sc_per_day.0', provider)
    per_unit_import = _get_val(mm, 'import_costs.grid_import_var_per_unit.0', provider)

    import_costs = underproduction * per_unit_import
    import_standing_costs = standing_charge * 365

    return [
        "Fixed costs",
        " ≈ £",
        html.Span(f'{float(f'{import_standing_costs:.2g}'):,.0f}'),
        "/yr; ",
        "Variable costs",
        " ≈ £",
        html.Span(f'{float(f'{import_costs:.2g}'):,.0f}'),
        "/yr"
    ]

def _create_finance_header_summary(mm, provider):
    benefit_dr = _get_val(mm, 'finance_settings.benefit_discount_rate.0', provider)
    cost_dr = _get_val(mm, 'finance_settings.cost_discount_rate.0', provider)
    return [
        icons.get_icon('finance-settings-benefit-discount'),
        " = ",
        html.Span(f"{benefit_dr:,.1%}"),
        "; ",
        icons.get_icon('finance-settings-cost-discount'),
        " = ",
        html.Span(f"{cost_dr:,.1%}"),
    ]

header_creation_functions = {
    'gen_input': _create_generation_header_summary,
    'stor_input': _create_storage_header_summary,
    'bc_input': _create_bc_header_summary,
    'dc_input': _create_dc_header_summary,
    'mc_input': _create_model_config_header_summary,
    'gen_costs': _create_cost_generation_header_summary,
    'stor_costs': _create_cost_storage_header_summary,
    'sales_costs': _create_cost_sales_header_summary,
    'import_costs': _create_cost_import_header_summary,
    'finance_settings': _create_finance_header_summary,
}

def _generic_create_deterministic_input_header_contents(
    section: str,
    mm: NewsegsMetaModel,
    provider: NewsegsProjectProviderInterface,
) -> list[dash.development.base_component.Component]:
    return header_creation_functions[section](mm, provider)

for supersection, section_tuple in sections_by_supersection.items():
    for section in section_tuple:
        if section in header_creation_functions:
            @register_input_section_header_content_creator(supersection, section, MODEL_TYPE)
            def _(
                proj_id: str, 
                proj_provider: NewsegsProjectProviderInterface, 
                _section: str = section # Using default argument trick to force evaluation of section
            ) -> list[dash.development.base_component.Component]:
                if not proj_id:
                    raise PreventUpdate
                return _generic_create_deterministic_input_header_contents(
                    _section, get_focussed_lightweight_metamodel(proj_id, proj_provider), proj_provider.variable_provider
                )


