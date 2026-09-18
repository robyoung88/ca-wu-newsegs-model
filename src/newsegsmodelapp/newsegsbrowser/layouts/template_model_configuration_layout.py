"""
Functions for creating a model configuration layout for an app.

Many of these functions require configured sub-functions to actually perform
the bespoke layout creation.
"""
from typing import Any

from dash import dcc, html
import dash_bootstrap_components as dbc

from newsegsmodelapp.components.post_page_load import create_post_page_load_components
from newsegsmodelapp.newsegsbrowser.background_callback_errors import background_callback_error_handler_components
from newsegsmodelapp.components import result_group_containers
from newsegsmodelapp.components import project_selector_v2 as project_selector
from newsegsmodelapp.components import navigation
from newsegsmodelapp.newsegsbrowser.layouts.inputs import input_sections_sprake, maps
from newsegsmodelapp.components.feedback import indicative_net_energy
from newsegsmodelapp.newsegsbrowser.layouts.common import NULL_LAYOUT
from newsegsmodelapp.newsegsbrowser.layouts import common as clayouts, layout_registry

from newsegsmodelapp.components import results_header
from newsegsmodelapp.components import configuration_selector
from newsegsmodelapp.newsegsbrowser.layouts.results import results_sections_sprake
from newsegsmodelapp.newsegsbrowser.postprocess.tables import results_tables_map
from newsegsmodelapp.registers import register_page_layout

dbc_Container: Any = dbc.Container
dbc_Button: Any = dbc.Button
dbc_Card: Any = dbc.Card
dbc_CardBody: Any = dbc.CardBody
dbc_Row: Any = dbc.Row
dbc_Col: Any = dbc.Col

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
    
    header = [dbc.Row([
        dbc.Col(
            config_dict['layout_top'](**kwargs),
            width = config_dict['width_top'],
            class_name = 'page-top',
        ), # pyright: ignore[reportCallIssue]
        dbc.Col(
            html.Div(
                config_dict['layout_navigation'](config_dict.get('selected_model')),
            ),
            class_name = 'newsegs-navbar-vertical collapsed',
            width = config_dict['width_navigation'],
            
        ), # pyright: ignore[reportCallIssue]
        dbc.Col(
            config_dict['layout_map'](),
            width = config_dict['width_map']
        ) # pyright: ignore[reportCallIssue]
    ])] # pyright: ignore[reportCallIssue]

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
            ) # pyright: ignore[reportCallIssue]
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
            ) # pyright: ignore[reportCallIssue]
        )

    site_details = [
        dbc.Row(
            dbc.Col(
                config_dict['layout_top_feedback'](),
                width = config_dict['width_top_feedback']
            ) # pyright: ignore[reportCallIssue]
        ), # pyright: ignore[reportCallIssue]

        dbc.Row(model_input_sections), # pyright: ignore[reportCallIssue]
        
        html.Hr(),

        dbc.Row(finance_input_sections), # pyright: ignore[reportCallIssue]
    ]

    #results_table_functions = config_dict['results_table_functions']

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
            ) # pyright: ignore[reportCallIssue]
        )

    results_section = [
        result_group_containers.create_results_container(
            [
                config_dict['layout_results_header'](**kwargs),
                html.Div([
                    config_dict['layout_configuration_selector'](),

                    dbc.Row(
                        results_subsections
                    ) # pyright: ignore[reportCallIssue]
                ],

                id = 'drawer-content',
                className = 'drawer-content',
                ),        
            ] + clayouts.user_action_components(),
            section = 'deterministic-results',
            supersection = 'deterministic',
            className = 'drawer-container'
        ),

        html.Div(
            id = {'type':'post-drawer-attach', 'page': kwargs.get('page-type', 'None')},
            style = {'display': 'none'}
        ),
    ]

    a1_contents = [
        dbc_Row([
            dbc_Col(
                config_dict['layout_navigation'](config_dict.get('selected_model')),
                width = 'auto',
            ),
            dbc_Col(
                config_dict['layout_top'](**kwargs),
                #width = config_dict['width_top'],
                class_name = 'page-top',
            ),
        ],
        class_name = 'align-items-start'
        ),
        
    ]

    a2_contents = [
        dbc_Row(
            config_dict['layout_map']()
        )
    ] + site_details

    b1_contents = [
         config_dict['layout_results_header'](**kwargs),
    #     config_dict['layout_configuration_selector'](),
    ]

    b2_contents = [dbc_Container(dbc_Row(results_subsections))]
    

    return dbc_Container(
        [
            # Block A1: Left Pane Header
            html.Div(
                a1_contents,
                className="pane-header header-a1 bg-light px-3 pt-0 pb-1 border-bottom d-flex justify-content-between align-items-start",
            ),
            # Block B1: Right Pane Header
            html.Div(
                b1_contents,
                className="pane-header header-b1 bg-light px-3 pt-0 pb-1 border-bottom d-flex justify-content-between align-items-start",
            ),
            # Block A2: Left Pane Content (Scrollable)
            html.Div(
                a2_contents,
                className="pane-content content-a2 p-3 bg-white",
            ),
            # Block B2: Right Pane Content (Scrollable)
            html.Div(
                result_group_containers.create_results_container(
                    b2_contents,
                    section = 'deterministic-results',
                    supersection = 'deterministic',
                ),
                className="pane-content content-b2 p-3 bg-white",
            ),
        ],
        fluid=True,
        className="dash-container p-0",
    )
    
    return dbc.Container(
        html.Div(
            (
                header
                + [html.Hr()]
                + site_details
                + [html.Hr()]
                + results_section
                + background_callback_error_handler_components()
                + create_post_page_load_components(
                    kwargs.get('selected_model'),
                    kwargs.get('page_type')
                )
            ),
            className = 'main-content-pane',
        ),
        fluid = False,
        class_name = 'app-layout-wrapper',
    ) # pyright: ignore[reportCallIssue]

@register_page_layout('site-config')
def _create_model_configuration_layout(app_state: dict):
    selected_model = app_state.get('selected_model', 'default')
    return create_model_configuration_layout(
        **layout_registry.get_model_configuration_layout_config(
            selected_model
        )
    )
