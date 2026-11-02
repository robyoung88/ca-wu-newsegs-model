"""The input sections of the deterministic (site configuration) page for the Sprake model.
"""

from newsegsmodelapp.components import icons
from newsegsmodelapp.components.layouts.input_card import create_input_card

def create_generation_input_card():
    """
    A Bootstrap card holding inputs for generation config
    """
    return create_input_card(
        'deterministic', 
        'gen_input',
        [icons.get_icon('generation'), 'Generation'],
        'model-config-input-container'
    )

def create_storage_input_card():
    """
    A Bootstrap card holding inputs for storage config
    """
    return create_input_card(
        'deterministic', 
        'stor_input',
        [icons.get_icon('storage'), "Storage"],
        'model-config-input-container'
    )

def create_building_consumption_input_card():
    """
    A Bootstrap card holding inputs for building consumption config
    """
    return create_input_card(
        'deterministic', 
        'bc_input',
        [icons.get_icon('consumption-building'), "Building Consumption"],
        'model-config-input-container'
    )

def create_direct_consumption_input_card():
    """
    A Bootstrap card holding inputs for direct consumption config
    """
    return create_input_card(
        'deterministic', 
        'dc_input',
        [icons.get_icon('consumption-direct'), 'Direct Consumption'],
        'model-config-input-container'
    )

def create_model_settings_input_card():
    """
    HTML inputs for general model settings (e.g. time horizon)
    """
    return create_input_card(
        'deterministic', 
        'mc_input',
        [icons.get_icon('model-settings'), 'Model Settings'],
        'model-config-input-container'
    )

def create_gen_cost_input_card():
    """
    HTML inputs for generation costs (Sprake model)
    """
    return create_input_card(
        'deterministic', 
        'gen_costs',
        [icons.get_icon('cost-generation'), 'Generation Costs'],
        'model-config-input-container'
    )

def create_storage_cost_input_card():
    """
    HTML inputs for storage costs (Sprake model)
    """
    return create_input_card(
        'deterministic', 
        'stor_costs',
        [icons.get_icon('cost-storage'), 'Storage Costs'],
        'model-config-input-container'
    )

def create_sales_input_card():
    """
    HTML inputs for sales value (Sprake model)
    """
    return create_input_card(
        'deterministic', 
        'sales_costs',
        [icons.get_icon('cost-sales'), 'Sales'],
        'model-config-input-container'
    )


def create_import_cost_input_card():
    """
    HTML inputs for import costs (Sprake model)
    """
    return create_input_card(
        'deterministic', 
        'import_costs',
        [icons.get_icon('cost-import'), 'Import Costs'],
        'model-config-input-container'
    )

def create_finance_settings_input_card():
    """
    HTML inputs for general finance settings (e.g. discount rates)
    """
    return create_input_card(
        'deterministic', 
        'finance_settings',
        [icons.get_icon('finance-settings'), 'Finance Settings'],
        'model-config-input-container'
    )
