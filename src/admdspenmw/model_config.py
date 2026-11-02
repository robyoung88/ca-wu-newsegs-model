"""Default configuration for running the ADMD calculation (`admd`) with a Hamilton driver.

Attributes:
    default_model_config: Hamilton configuration (empty - no configuration is needed).
    default_model_inputs: Default values of the inputs of the calculation: 50 customers with no
        EV chargers, heat pumps or storage heating, and smart charging.
    default_model_outputs: The values requested from the calculation.
"""
default_model_config = {}

default_model_inputs = {
    'N_customers': 50,

    'N_EV_chargers': 0.0,
    'N_EV_and_HP': 0.0,
    'smart_charging': True,

    'N_ASHP_5kW': 0.0,
    'N_ASHP_8kW': 0.0,
    'N_ASHP_16kW': 0.0,

    'N_GSHP_5kW': 0.0,
    'N_GSHP_8kW': 0.0,
    'N_GSHP_16kW': 0.0,

    'N_HyHP_5kW': 0.0,
    'N_HyHP_8kW': 0.0,
    'N_HyHP_16kW': 0.0,

    'N_storage_5kW': 0.0,
    'N_storage_8kW': 0.0,
    'N_storage_16kW': 0.0
}

default_model_outputs = ['ADMD_standard', 'ADMD_coldload']
