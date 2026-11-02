"""Post sprake finance costs results module.

TODO: Describe the purpose of the module.
"""
import numpy as np
import pandas as pd

from newsegsmodelframework.newsegsmodel.sprakemodel import SprakeModel
from newsegsmodelframework.newsegsfinance.sprakefinance import SprakeFinance

from newsegsmodelframework.newsegsstats.core import assign_year_index
from newsegsmodelframework.newsegsstats import basic_summary_stats

def finance_costs_results_to_interface_sprake(
    mdl: SprakeModel, # Unused
    fnc: SprakeFinance
) -> dict:
    """
    Extracts the financial costs results required for the Dash interface
    """
    # This holds our final returned data structure
    results_to_interface = {}

    import_costs = fnc.import_costs_undiscounted
    om_costs_gen = fnc.om_costs_generation_undiscounted
    om_costs_stor = fnc.om_costs_storage_undiscounted

    variable_costs = (
        import_costs
        .loc[:, ['costs']]
        .rename(columns = {'costs': 'import_costs'})
        .join(
            om_costs_gen
            .loc[:, ['costs']]
            .rename(columns = {'costs': 'om_costs_gen'})
        )
        .join(
            om_costs_stor
            .loc[:, ['costs']]
            .rename(columns = {'costs': 'om_costs_stor'})
        )
        .assign(
            variable_costs = lambda df: df.sum(axis=1)
        )
    )

    undiscounted_variable_costs_summaries = (
        variable_costs
        .pipe(assign_year_index)
        .query('year_index >= 0')
        .pipe(basic_summary_stats.meter_annual_summary2)
    )

    results_to_interface['undiscounted_variable_costs_summaries'] = (
        undiscounted_variable_costs_summaries
        .pipe(basic_summary_stats.meter_annual_summary2_to_interface)
    )

    capex_costs = [
        fnc.capex_costs_generation_undiscounted.loc[:,'costs'].sum(),
        fnc.capex_costs_storage_undiscounted.loc[:,'costs'].sum(),
        fnc.capex_costs_distribution_undiscounted.loc[:,'costs'].sum(),
        fnc.capex_costs_metering_undiscounted.loc[:,'costs'].sum(),
    ]
    capex_costs.append(np.sum(capex_costs))

    capex_summaries = pd.DataFrame.from_dict(
        {
            'variable': [
                'capex_costs_gen',
                'capex_costs_stor',
                'capex_costs_dist',
                'capex_costs_metering',
                'capex_costs_total'
            ],
            'statistic' : ['sum'] * len(capex_costs),
            'value': capex_costs
        },
        orient='columns'
    )

    results_to_interface['undiscounted_capex_summaries'] = (
        capex_summaries
        .pipe(basic_summary_stats.meter_annual_summary2_to_interface)
    )

    results_to_interface['present_costs_undiscounted'] = fnc.get_total_present_costs_undiscounted()
    results_to_interface['present_costs_discounted'] = fnc.get_total_present_costs_discounted()
    results_to_interface['costs_discount_rate'] = fnc.cost_discount_rate

    # Results used by the summary headers
    import_costs = (
        fnc.import_costs_undiscounted
        .drop(columns='costs')
        .pipe(assign_year_index)
        .query('year_index >= 0')
        .pipe(basic_summary_stats.meter_annual_summary2)
        .set_index(['variable','statistic'])
    )

    results_to_interface['smry_import_fixed_cost_peryear'] = import_costs.loc[('fixed_costs','mean'),'value']
    results_to_interface['smry_import_variable_cost_peryear'] = import_costs.loc[('var_costs','mean'),'value']

    return results_to_interface
