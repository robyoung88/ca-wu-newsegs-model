"""
Functions for creating a model configuration layout for an app.

Many of these functions require configured sub-functions to actually perform
the bespoke layout creation.
"""
from typing import Any

from dash import html

from newsegsmodelapp.components.page_layouts import fourpane_layout
from newsegsmodelapp.components import result_group_containers
from newsegsmodelapp.components import project_selector as project_selector
from newsegsmodelapp.components import navigation
from newsegsmodelapp.newsegsbrowser.layouts import layout_registry
from newsegsmodelapp.newsegsbrowser.layouts.inputs import input_sections_sprake, maps
from newsegsmodelapp.components.feedback import indicative_net_energy

from newsegsmodelapp.components import results_header
from newsegsmodelapp.components import configuration_selector
from newsegsmodelapp.newsegsbrowser.layouts.results import results_sections_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.tables import results_tables_map
from newsegsmodelapp.registers import register_page_layout
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc

from .common import NULL_LAYOUT

DEFAULT_LAYOUT_CONFIGURATION = {
    'layout_top': project_selector.create_project_selector_block,
    'width_top': 11,
    'layout_navigation': navigation.create_navigation_component,
    'width_navigation': 1,
    'layout_map': maps.create_site_selector_map,
    'width_map': 11,
    'layout_top_feedback': indicative_net_energy.create_indicative_net_energy_card,
    'width_top_feedback': 12,
    'layout_generation_input': input_sections_sprake.create_generation_input_card,
    'width_generation_input': 6,
    'layout_storage_input': input_sections_sprake.create_storage_input_card,
    'width_storage_input': 6,
    'layout_building_consumption_input': input_sections_sprake.create_building_consumption_input_card,
    'width_building_consumption_input': 6,
    'layout_direct_consumption_input': input_sections_sprake.create_direct_consumption_input_card,
    'width_direct_consumption_input': 6,
    'layout_grid_input': NULL_LAYOUT,
    'width_grid_input': 12,
    'layout_environment_input': NULL_LAYOUT,
    'width_environment_input': 12,
    'layout_model_settings_input': input_sections_sprake.create_model_settings_input_card,
    'width_model_settings_input': 12,
    'layout_generation_cost_input': input_sections_sprake.create_gen_cost_input_card,
    'width_generation_cost_input': 6,
    'layout_storage_cost_input': input_sections_sprake.create_storage_cost_input_card,
    'width_storage_cost_input': 6,
    'layout_sales_input': input_sections_sprake.create_sales_input_card,
    'width_sales_input': 6,
    'layout_import_cost_input': input_sections_sprake.create_import_cost_input_card,
    'width_import_cost_input': 6,
    'layout_finance_settings_input': input_sections_sprake.create_finance_settings_input_card,
    'width_finance_settings_input': 12,

    'layout_results_header': results_header.create_results_header,
    'layout_configuration_selector': configuration_selector.create_configuration_selector,
    'results_table_functions': results_tables_map.SPRAKE_RESULT_TABLES,
    'layout_generation_results': results_sections_sprake.create_generation_results_card,
    'width_generation_results': 12,
    'layout_grid_results': NULL_LAYOUT,
    'width_grid_results': 12,
    'layout_storage_results': results_sections_sprake.create_storage_results_card,
    'width_storage_results': 12,
    'layout_consumption_results': results_sections_sprake.create_consumption_results_card,
    'width_consumption_results': 12,
    'layout_net_results': results_sections_sprake.create_net_results_card,
    'width_net_results': 12,
    'layout_economic_so_results': results_sections_sprake.create_finance_results_so_card,
    'width_economic_so_results': 12,
}

def create_model_configuration_layout(*args, **kwargs):

    config_dict = DEFAULT_LAYOUT_CONFIGURATION.copy()
    config_dict.update(kwargs)

    model_input_sections = []
    for sec in [
        'generation_input',
        'storage_input',
        'building_consumption_input',
        'direct_consumption_input',
        'grid_input',
        'environment_input',
        'model_settings_input',
    ]:
        model_input_sections.append(
            dbc.Col(
                config_dict[f'layout_{sec}'](),
                width = config_dict[f'width_{sec}']
            )
        )

    finance_input_sections = []
    for sec in [
        'generation_cost_input',
        'storage_cost_input',
        'sales_input',
        'import_cost_input',
        'finance_settings_input',
    ]:
        finance_input_sections.append(
            dbc.Col(
                config_dict[f'layout_{sec}'](),
                width = config_dict[f'width_{sec}']
            )
        )

    site_details = [
        dbc.Row(
            dbc.Col(
                config_dict['layout_top_feedback'](),
                width = config_dict['width_top_feedback']
            )
        ),

        dbc.Row(model_input_sections), 
        
        html.Hr(),

        dbc.Row(finance_input_sections),
    ]

    results_subsections = []
    for sec in [
        'generation_results',
        'grid_results',
        'storage_results',
        'consumption_results',
        'net_results',
        'economic_so_results'
    ]:
        results_subsections.append(
            dbc.Col(
                config_dict[f'layout_{sec}'](),
                width = config_dict[f'width_{sec}']
            )
        )

    a1_contents = [
        dbc.Row([
            dbc.Col(
                config_dict['layout_navigation'](config_dict.get('selected_model')),
                width = 'auto',
            ),
            dbc.Col(
                config_dict['layout_top'](**kwargs),
                class_name = 'page-top',
            ),
        ],
        class_name = 'align-items-start'
        ),
        
    ]

    a2_contents = [
        dbc.Row(
            config_dict['layout_map']()
        )
    ] + site_details

    b1_contents = [
         config_dict['layout_results_header'](**kwargs),
    ]

    b2_contents = [
        config_dict['layout_configuration_selector'](),
        result_group_containers.create_results_container(
            dbc.Container(dbc.Row(results_subsections)),
            section = 'deterministic-results',
            supersection = 'deterministic',
        )
    ]

    return fourpane_layout(
        a1_contents,
        b1_contents,
        a2_contents,
        b2_contents,
    )

@register_page_layout('site-config')
def _create_model_configuration_layout(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_model_configuration_layout(
        **layout_registry.get_model_configuration_layout_config(
            selected_model
        )
    )
