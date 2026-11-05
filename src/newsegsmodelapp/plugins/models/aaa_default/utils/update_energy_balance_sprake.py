"""Updating the estimated energy balance of the Sprake model from the inputs of a metamodel, for the feedback graphs.
"""
import logging
logger = logging.getLogger(__name__)

from functools import partial
import json

import plotly.express as px

from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelapp.components import colours
from newsegsmodelapp.components import energy_balance_estimation
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_lightweight_metamodel
from newsegsmodelframework.newsegsmetamodel.lightweightnewsegsmetamodel import LightweightNewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface
from newsegsmodelapp import registers

from newsegsmodelapp import APP_ROOT
_CONST_FILE = APP_ROOT / 'newsegsmodelframework' / 'constants' / 'model_constants.json'
with open(_CONST_FILE, 'r') as f:
    MODEL_CONSTANTS = json.load(f)

def _get_val(lmm, key, variableprovider: FromDatabaseVariableProvider) -> int | float:
    var = variableprovider.get_lightweight_variable(lmm.variables.get(key))
    return var.last_deterministic_value
# def _get_val(mm, key) -> int | float:
#     return cast(variable.NumericScalarVariable, mm.variables.get(key)).deterministic_value

def update_estimated_energy_balance(
    mm: LightweightNewsegsMetaModel,
    variableprovider: FromDatabaseVariableProvider,
    energy_balance: energy_balance_estimation.EstimatedEnergyBalance
) -> energy_balance_estimation.EstimatedEnergyBalance:
    """Update an estimate of the energy balance from the inputs of a metamodel of the Sprake model.

    Reads the last deterministic values of the capacities, households, heat loss parameter, floor area, hot water, appliance, EV and storage variables.

    Args:
        mm: The lightweight metamodel.
        variableprovider: Provider of variables.
        energy_balance: The estimate to update.

    Returns:
        The updated estimate.
    """
    vars_required = (
        'gen_input.wind_capacity.0',
        'gen_input.pv_capacity.0',
        'bc_input.n_units.0',
        'bc_input.hlp.0',
        'bc_input.gfa.0',
        'bc_input.ref_daily_consumption.0',
        'dc_input.efficiency_reduction.0',
        'dc_input.n_evs_per_household.0',
        'dc_input.annual_residential_consumption_per_ev.0',
        'stor_input.storage_capacity.0',
    )

    variable_uids = [mm.variables.get(x) for x in vars_required]

    vvs = variableprovider.get_variable_metadata(variable_uids, 'last_deterministic_value')
    variable_demap = {
        varname: json.loads(vvs[id]['last_deterministic_value']) for id, varname in zip(variable_uids, vars_required)
    }
    
    # Generation
    wind_capacity = variable_demap['gen_input.wind_capacity.0']
    pv_capacity = variable_demap['gen_input.pv_capacity.0']
    energy_balance.set_wind_generation(wind_capacity)
    energy_balance.set_pv_generation(pv_capacity)

    # Consumption
    n_units = variable_demap['bc_input.n_units.0']
    
    hlp = variable_demap['bc_input.hlp.0']
    gfa = variable_demap['bc_input.gfa.0']
    # Could use this, but default is more than ok
    energy_balance.set_spaceheat_consumption(n_units, hlp, gfa)

    ref_daily_consumption = variable_demap['bc_input.ref_daily_consumption.0']
    # Assume conversion efficiency of 1
    energy_balance.set_dhw_consumption(n_units, ref_daily_consumption)

    efficiency_reduction = variable_demap['dc_input.efficiency_reduction.0']
    energy_balance.set_direct_consumption(
        n_units,
        (1 - efficiency_reduction) * MODEL_CONSTANTS['sprake_model']['sprake_ref_appliance_consumption_annual']
    )

    n_evs_per_household = variable_demap['dc_input.n_evs_per_household.0']
    ev_consumption_per_year = variable_demap['dc_input.annual_residential_consumption_per_ev.0']
    energy_balance.set_ev_consumption(n_units, ev_consumption_per_year, n_evs_per_household)

    stor_cap = variable_demap['stor_input.storage_capacity.0']
    energy_balance.set_storage_capacity(stor_cap)

    return energy_balance

_feedback_graph_bar = partial(
    px.bar,
    x = 'value',
    color = 'label',
    template = colours.PLOT_TEMPLATES,
    orientation = 'h'
)

_feedback_graph_layout = dict(
    height=120,
    margin={'l': 0, 'r': 0, 't': 28, 'b': 0},
    title={
        'x': 0.5,
        'xanchor': 'center',
        'yanchor': 'top',
        'font': {'size': 12, 'family': 'Arial', 'color': colours.TEXT, 'weight': 'bold'}
    },
    showlegend=False,
    template=colours.PLOT_TEMPLATES,
    paper_bgcolor='rgba(0,0,0,0)',
    plot_bgcolor='rgba(0,0,0,0)',
    bargap=0.75
)

@registers.register_feedback_graph_artist('estimated-annual-energy', 'sprake')
def _(
    project_id: str, 
    project_provider: NewsegsProjectProviderInterface,
    eb: energy_balance_estimation.EstimatedEnergyBalance | None = None
):
    logger.debug('Getting lightweight project - Updating estimated annual energy')
    lmm = get_focussed_lightweight_metamodel(project_id, project_provider)
    if not eb:
        eb = energy_balance_estimation.EstimatedEnergyBalance()

    eb = update_estimated_energy_balance(lmm, project_provider.variable_provider, eb)

    df = eb.estimated_annual_energy_balance

    fig_ann = _feedback_graph_bar(df, y = 'type')
    fig_ann.update_layout(**_feedback_graph_layout) # pyright: ignore[reportArgumentType]
    fig_ann.update_layout(title = {'text': 'Annual'})
    fig_ann.update_traces(width=0.35, marker_line_width=0)
    fig_ann.update_xaxes(showticklabels=False, title_text=None, showgrid=False, zeroline=False)
    fig_ann.update_yaxes(showticklabels=True, title_text=None, showgrid=False, zeroline=False)

    return fig_ann

@registers.register_feedback_graph_artist('estimated-maximum-daily-energy', 'sprake')
def _(
    project_id: str, 
    project_provider: NewsegsProjectProviderInterface,
    eb: energy_balance_estimation.EstimatedEnergyBalance | None = None
):
    logger.debug('Getting lightweight project - Updating estimated maximum daily energy')
    lmm = get_focussed_lightweight_metamodel(project_id, project_provider)
    if not eb:
        eb = energy_balance_estimation.EstimatedEnergyBalance()

    eb = update_estimated_energy_balance(lmm, project_provider.variable_provider, eb)

    df = eb.estimated_maximum_daily_balance
    fig_max = _feedback_graph_bar(df, y = 'label')
    fig_max.update_layout(**_feedback_graph_layout) # pyright: ignore[reportArgumentType]
    fig_max.update_layout(title = {'text': '(Max) Daily'})
    fig_max.update_traces(width=0.35, marker_line_width=0)
    fig_max.update_xaxes(showticklabels=False, title_text=None, showgrid=False, zeroline=False)
    fig_max.update_yaxes(showticklabels=True, title_text=None, showgrid=False, zeroline=False)

    return fig_max
