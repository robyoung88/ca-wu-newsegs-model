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
        'autorun_model': True,
    }

def get_dsa_layout_config(model_type):
    return {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'dsa',
        'autorun_model': False,
    }

def get_psa_layout_config(model_type):
    return {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'psa',
        'autorun_model': False,
    }
