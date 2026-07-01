def get_landing_layout_config(model_type):
    return {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'landing',
    }

def get_model_configuration_layout_config(model_type):
    return {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'model_configuration',
    }

def get_dsa_layout_config(model_type):
    return {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'dsa'
    }

def get_psa_layout_config(model_type):
    return {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'psa'
    }
