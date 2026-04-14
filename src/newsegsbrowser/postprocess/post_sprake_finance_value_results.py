import pandas as pd

from src.newsegsmodel.sprakemodel import SprakeModel
from src.newsegsfinance.sprakefinance import SprakeFinance

from src.stats import basic_summary_stats

def finance_value_results_to_interface_sprake(
    mdl: SprakeModel, # Unused
    fnc: SprakeFinance,
) -> dict:
    """
    Extracts the financial value required for the Dash interface.
    """
    # This holds our final returned data structure
    results_to_interface = {}

    value_summaries = pd.DataFrame.from_dict(
        {
            'variable': [
                'benefit_cost_ratio_undiscounted',
                'benefit_cost_ratio_discounted',
                'simple_payback_time_yrs',
                'net_present_value_undiscounted',
                'net_present_value_discounted',
            ],
            'statistic': ['sum'] * 5,
            'value': [
                fnc.get_benefit_cost_ratio_undiscounted(),
                fnc.get_benefit_cost_ratio_discounted(),
                fnc.get_simple_payback_time_days() / 365,
                fnc.get_net_present_value_undiscounted(),
                fnc.get_net_present_value_discounted()
            ]
        },
        orient='columns'
    )

    results_to_interface['value_summaries'] = (
        value_summaries
        .pipe(basic_summary_stats.meter_annual_summary2_to_interface)
    )

    results_to_interface['benefits_discount_rate'] = fnc.benefit_discount_rate
    results_to_interface['costs_discount_rate'] = fnc.cost_discount_rate

    return results_to_interface
