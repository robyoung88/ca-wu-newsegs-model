"""Labels and formatting."""
from collections import OrderedDict

DSA_STATISTIC_LABELS = OrderedDict(
    net_present_value_discounted = 'Net present value (discounted)',
    net_present_value_undiscounted = 'Net present value (undiscounted)',
    total_present_benefits_discounted = 'Total present benefits (discounted)',
    total_present_benefits_undiscounted = 'Total present benefits (undiscounted)',
    total_present_costs_discounted = 'Total present costs (discounted)',
    total_present_costs_undiscounted = 'Total present costs (undiscounted)',
)
"""Labels of the statistics of a DSA, in the order that they are shown, by statistic."""

DSA_STATISTIC_LABELS_RLOOKUP = {v: k for k, v in DSA_STATISTIC_LABELS.items()}
"""Statistics of a DSA by their labels: the reverse of `DSA_STATISTIC_LABELS`."""

PSA_STATISTIC_LABELS = OrderedDict(
    net_present_value_discounted = 'Net present value (discounted)',
    net_present_value_undiscounted = 'Net present value (undiscounted)',
    total_present_benefits_discounted = 'Total present benefits (discounted)',
    total_present_benefits_undiscounted = 'Total present benefits (undiscounted)',
    total_present_costs_discounted = 'Total present costs (discounted)',
    total_present_costs_undiscounted = 'Total present costs (undiscounted)',
)
"""Labels of the statistics of a PSA, in the order that they are shown, by statistic."""
