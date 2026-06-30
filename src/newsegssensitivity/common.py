from collections import OrderedDict

DSA_STATISTIC_LABELS = OrderedDict(
    net_present_value_discounted = 'Net present value (discounted)',
    net_present_value_undiscounted = 'Net present value (undiscounted)',
    total_present_benefits_discounted = 'Total present benefits (discounted)',
    total_present_benefits_undiscounted = 'Total present benefits (undiscounted)',
    total_present_costs_discounted = 'Total present costs (discounted)',
    total_present_costs_undiscounted = 'Total present costs (undiscounted)',
)

DSA_STATISTIC_LABELS_RLOOKUP = {v: k for k, v in DSA_STATISTIC_LABELS.items()}
