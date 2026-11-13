"""Layout configurations of the pages for the `sprake` model type.

Copies the default configuration of each page and sets the text, navigation, and the input and result cards for the Sprake model.
"""
import os
import copy
from typing import cast

import dash
import pandas as pd

from newsegsmodelapp import registers
from newsegsmodelapp import STATICDATA
from newsegsmodelapp.components import navigation
from newsegsmodelapp.components.layouts.configurations import InputCardConfig, ResultCardConfig

from .inputs import input_sections_sprake
from .results import results_sections_sprake
from ....pages import (
    p010_landing_layout, p100_model_configuration_layout, 
    p200_dsa_configuration_layout, p300_psa_configuration_layout
)

TEXT_DIR = STATICDATA / 'model_text'

_NAVIGATION_PAGES = [
    'landing',
    'site-config',
    'dsa',
    'psa',
]

_MODEL_TYPE = 'sprake'
_NAV_COMPONENT_FUNCTION = lambda model_type: navigation.create_navigation_component(
    model_type,
    pages = _NAVIGATION_PAGES
)

#################################################
# LANDING
#################################################

_PAGE_TYPE = 'landing'
config = cast(
    p010_landing_layout.LandingLayoutConfiguration,
    copy.copy(
        registers.get_page_layout_configuration(_PAGE_TYPE, 'default')
    )
)

config.model_type = _MODEL_TYPE
config.head_text = 'Sprake Model'
config.layout_navigation = _NAV_COMPONENT_FUNCTION
with open(os.path.join(TEXT_DIR, 'sprake', 'sprake_landing_body.md'), encoding='utf-8') as f:
    config.body_text = f.readlines()
with open(os.path.join(TEXT_DIR, 'sprake', 'sprake_landing_assumptions.md'), encoding='utf-8') as f:
    config.assumptions_text = f.readlines()

config.model_diagram = lambda: dash.get_asset_url('fig/metamodel-block-diagram-sprake-bw.svg')
config.default_values_table = pd.read_csv(os.path.join(TEXT_DIR, 'sprake','sprake_model_input_assumptions.csv'), encoding='utf-8-sig')

registers.add_page_layout_configuration(config, _PAGE_TYPE, _MODEL_TYPE)

#################################################
# SITE-CONFIG
#################################################

_PAGE_TYPE = 'site-config'
config = cast(
    p100_model_configuration_layout.ModelConfigurationLayoutConfiguration,
    copy.copy(
        registers.get_page_layout_configuration(_PAGE_TYPE, 'default')
    )
)

config.model_type = _MODEL_TYPE
config.layout_navigation = _NAV_COMPONENT_FUNCTION
config.model_input_sections = [
    InputCardConfig(input_sections_sprake.create_generation_input_card, 6),
    InputCardConfig(input_sections_sprake.create_storage_input_card, 6),
    InputCardConfig(input_sections_sprake.create_building_consumption_input_card, 6),
    InputCardConfig(input_sections_sprake.create_direct_consumption_input_card, 6),
    InputCardConfig(input_sections_sprake.create_model_settings_input_card, 12),
]

config.finance_input_sections = [
    InputCardConfig(input_sections_sprake.create_gen_cost_input_card, 6),
    InputCardConfig(input_sections_sprake.create_storage_cost_input_card, 6),
    InputCardConfig(input_sections_sprake.create_sales_input_card, 6),
    InputCardConfig(input_sections_sprake.create_import_cost_input_card, 6),
    InputCardConfig(input_sections_sprake.create_finance_settings_input_card, 12),
]

config.results_sections = [
    ResultCardConfig(results_sections_sprake.create_generation_results_card, 12),
    ResultCardConfig(results_sections_sprake.create_storage_results_card, 12),
    ResultCardConfig(results_sections_sprake.create_consumption_results_card, 12),
    ResultCardConfig(results_sections_sprake.create_net_results_card, 12),
    ResultCardConfig(results_sections_sprake.create_finance_results_so_card, 12),
]

registers.add_page_layout_configuration(config, _PAGE_TYPE, _MODEL_TYPE)

#################################################
# DSA
#################################################

# Update navigation
_PAGE_TYPE = 'dsa'
config = cast(
    p200_dsa_configuration_layout.DSAConfigurationLayoutConfiguration,
    copy.copy(
        registers.get_page_layout_configuration(_PAGE_TYPE, 'default')
    )
)

config.model_type = _MODEL_TYPE
config.layout_navigation = _NAV_COMPONENT_FUNCTION
registers.add_page_layout_configuration(config, _PAGE_TYPE, _MODEL_TYPE)

#################################################
# PSA
#################################################

# Update navigation
_PAGE_TYPE = 'psa'
config = cast(
    p300_psa_configuration_layout.PSAConfigurationLayoutConfiguration,
    copy.copy(
        registers.get_page_layout_configuration(_PAGE_TYPE, 'default')
    )
)

config.model_type = _MODEL_TYPE
config.layout_navigation = _NAV_COMPONENT_FUNCTION
registers.add_page_layout_configuration(config, _PAGE_TYPE, _MODEL_TYPE)
