"""Labels, formatting and the statistics shared by the DSA and PSA."""
from collections import OrderedDict

import pandas as pd

from newsegsmodelframework.newsegsfinance.common import sum_all_to_horizon

COST_FRAME_STATISTICS = (
    'all_capex_costs_undiscounted',
    'all_capex_costs_discounted',
    'all_recurrent_costs_undiscounted',
    'all_recurrent_costs_discounted',
)
"""Statistics which are the total of a frame of costs of the finance model, read from the property of the same name."""

def total_of_cost_frame(costs: pd.DataFrame) -> float:
    """The total of a frame of costs of the finance model.

    Args:
        costs: Frame of timeseries of costs, with columns divided into a multi-index by `system` and `cost`, each
            system having a totals column `costs`.

    Returns:
        The sum of the totals columns over the whole timeseries; 0 if the frame is empty.
    """
    if len(costs) == 0:
        return 0.0
    return sum_all_to_horizon(costs.loc[:, (slice(None), 'costs')])

DSA_STATISTIC_LABELS = OrderedDict(
    net_present_value_discounted = 'Net present value (discounted)',
    net_present_value_undiscounted = 'Net present value (undiscounted)',
    total_present_benefits_discounted = 'Total present benefits (discounted)',
    total_present_benefits_undiscounted = 'Total present benefits (undiscounted)',
    total_present_costs_discounted = 'Total present costs (discounted)',
    total_present_costs_undiscounted = 'Total present costs (undiscounted)',
    all_capex_costs_discounted = 'Total present capex (discounted)',
    all_capex_costs_undiscounted = 'Total present capex (undiscounted)',
    all_recurrent_costs_discounted = 'Total present opex (discounted)',
    all_recurrent_costs_undiscounted = 'Total present opex (undiscounted)',
)
"""Labels of the statistics of a DSA, in the order that they are shown, by statistic."""

DSA_STATISTIC_LABELS_RLOOKUP = {v: k for k, v in DSA_STATISTIC_LABELS.items()}
"""Statistics of a DSA by their labels: the reverse of `DSA_STATISTIC_LABELS`."""

DSA_PAIRWISE_STATISTIC_LABELS = OrderedDict(
    incremental_net_monetary_value_discounted = 'Incremental net monetary value (discounted)',
    incremental_net_monetary_value_undiscounted = 'Incremental net monetary value (undiscounted)',
    incremental_benefit_cost_ratio_discounted = 'Incremental benefit to cost ratio (discounted)',
    incremental_benefit_cost_ratio_undiscounted = 'Incremental benefit to cost ratio (undiscounted)',
    incremental_total_costs_discounted = 'Incremental total costs (discounted)',
    incremental_total_costs_undiscounted = 'Incremental total costs (undiscounted)',
    incremental_total_benefits_discounted = 'Incremental total benefits (discounted)',
    incremental_total_benefits_undiscounted = 'Incremental total benefits (undiscounted)',
    incremental_all_capex_costs_discounted = 'Incremental capex (discounted)',
    incremental_all_capex_costs_undiscounted = 'Incremental capex (undiscounted)',
    incremental_all_recurrent_costs_discounted = 'Incremental opex (discounted)',
    incremental_all_recurrent_costs_undiscounted = 'Incremental opex (undiscounted)',
)
"""Labels of the pairwise (comparator against reference) statistics of a whole-project DSA, in the order that they are shown, by statistic."""

PSA_STATISTIC_LABELS = OrderedDict(
    net_present_value_discounted = 'Net present value (discounted)',
    net_present_value_undiscounted = 'Net present value (undiscounted)',
    total_present_benefits_discounted = 'Total present benefits (discounted)',
    total_present_benefits_undiscounted = 'Total present benefits (undiscounted)',
    total_present_costs_discounted = 'Total present costs (discounted)',
    total_present_costs_undiscounted = 'Total present costs (undiscounted)',
    all_capex_costs_discounted = 'Total present capex (discounted)',
    all_capex_costs_undiscounted = 'Total present capex (undiscounted)',
    all_recurrent_costs_discounted = 'Total present opex (discounted)',
    all_recurrent_costs_undiscounted = 'Total present opex (undiscounted)',
)
"""Labels of the statistics of a PSA, in the order that they are shown, by statistic."""
