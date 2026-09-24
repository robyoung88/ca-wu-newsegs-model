"""
Functions for creating a model configuration layout for an app.

Many of these functions require configured sub-functions to actually perform
the bespoke layout creation.
"""
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Sequence, cast

from dash import html

from newsegsmodelapp import registers
from newsegsmodelapp.components.layouts.configurations import InputCardConfig, ResultCardConfig
from newsegsmodelapp.components.page_layouts import fourpane_layout
from newsegsmodelapp.components import result_group_containers
from newsegsmodelapp.components import project_selector as project_selector
from newsegsmodelapp.components import map
from newsegsmodelapp.components import navigation
from newsegsmodelapp.components.feedback import indicative_net_energy

from newsegsmodelapp.components import results_header
from newsegsmodelapp.components import configuration_selector
from newsegsmodelapp.newsegsbrowser import icons
import newsegsmodelapp.components.typed_dash_bootstrap_components as dbc
from newsegsmodelapp.types import ComponentType, LayoutConfiguration, Page

PAGE_TYPE = 'site-config'

@dataclass
class ModelConfigurationLayoutConfiguration(LayoutConfiguration):
    page_type: str = PAGE_TYPE

    layout_navigation: Callable[[str], Any] = navigation.create_navigation_component
    layout_top: Callable[[], Any] = project_selector.create_project_selector_block

    layout_map: Callable[[], Any] = map.create_site_selector_map
    width_map = 11

    layout_top_feedback: Callable[[], Any] = indicative_net_energy.create_indicative_net_energy_card
    width_top_feedback = 12

    model_input_sections: Sequence[InputCardConfig] = field(default_factory=list)
    finance_input_sections: Sequence[InputCardConfig] = field(default_factory=list)

    layout_results_header: Callable[[], Any] = lambda: results_header.create_results_header(PAGE_TYPE)
    layout_configuration_selector: Callable[[], Any] = configuration_selector.create_configuration_selector

    results_sections: Sequence[ResultCardConfig] = field(default_factory=list)

def create_model_configuration_layout(config: ModelConfigurationLayoutConfiguration) -> ComponentType:

    model_input_sections = []
    for sec in config.model_input_sections:
        model_input_sections.append(
            dbc.Col(
                sec.creation_function(),
                width = sec.block_width
            )
        )
    
    finance_input_sections = []
    for sec in config.finance_input_sections:
        finance_input_sections.append(
            dbc.Col(
                sec.creation_function(),
                width = sec.block_width
            )
        )

    site_details = [
        dbc.Row(
            dbc.Col(
                config.layout_top_feedback(),
                width = config.width_top_feedback
            )
        ),

        dbc.Row(model_input_sections), 
        
        html.Hr(),

        dbc.Row(finance_input_sections),
    ]

    results_subsections = []
    for sec in config.results_sections:
        results_subsections.append(
            dbc.Col(
                sec.creation_function(),
                width = sec.block_width
            )
        )

    a1_contents = [
        dbc.Row([
            dbc.Col(
                config.layout_navigation(config.model_type),
                width = 'auto',
            ),
            dbc.Col(
                config.layout_top(),
                class_name = 'page-top',
            ),
        ],
        class_name = 'align-items-start'
        ),
        
    ]

    a2_contents = [
        dbc.Row(
            config.layout_map()
        )
    ] + site_details

    b1_contents = [
        config.layout_results_header()
    ]

    b2_contents = [
        config.layout_configuration_selector(),
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

model_configuration_page = Page(
    id = PAGE_TYPE,
    nav_label = 'Site configuration',
    nav_icon = html.I(
        className = icons.get_icon('nav-system-config', style_name = 'raw'),
        style = {'display': 'inline'}
    ),
    layout = create_model_configuration_layout,
    default_configuration = ModelConfigurationLayoutConfiguration()
)
registers.add_page(model_configuration_page)
