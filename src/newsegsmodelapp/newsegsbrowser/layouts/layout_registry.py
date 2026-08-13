import os

import dash

from newsegsmodelapp.newsegsbrowser import STATICDATA

TEXT_DIR = os.path.join(STATICDATA, 'model_text')

def get_landing_layout_config(model_type):
    page_args = {
        'model_type': model_type,
        'selected_model': model_type,
        'page_type': 'landing',
    }
    match model_type:
        case 'sprake':
            page_args['head_text'] = 'Sprake Model'
            with open(os.path.join(TEXT_DIR, 'sprake', 'sprake_landing_body.md'), encoding='utf-8') as f:
                page_args['body_text'] = f.readlines()
            with open(os.path.join(TEXT_DIR, 'sprake', 'sprake_landing_assumptions.md'), encoding='utf-8') as f:
                page_args['assumptions_text'] = f.readlines()

            page_args['model_diagram'] = dash.get_asset_url('fig/metamodel-block-diagram-sprake-bw.svg')
            
        case _:
            ...
    return page_args

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
