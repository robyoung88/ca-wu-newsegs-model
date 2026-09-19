from typing import cast

import dash
from dash.exceptions import PreventUpdate

from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.components.composite_input_components import generic_create_deterministic_input_container_contents
from newsegsmodelapp.newsegsbrowser.callbacks import model_configuration_callbacks_sprake
from newsegsmodelapp.registers import register_input_container_content_creator, register_input_section_header_content_creator
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

MODEL_TYPE = 'sprake'

sections_by_supersection = {
    'deterministic': (
        'gen_input',
        'stor_input',
        'bc_input',
        'dc_input',
        'mc_input',
        'gen_costs',
        'stor_costs',
        'sales_costs',
        'import_costs',
        'finance_settings',
    )
}

for supersection, section_tuple in sections_by_supersection.items():
    for section in section_tuple:
        @register_input_container_content_creator(supersection, section, MODEL_TYPE)
        def _(
            proj_id: str, 
            proj_provider: NewsegsProjectProviderInterface, 
            _section: str = section # Using default argument trick to force evaluation of section
        ) -> list[dash.development.base_component.Component]:
            proj = proj_provider.get_project(proj_id)
            mm = proj.get_focussed_metamodel()
            return generic_create_deterministic_input_container_contents(
                _section, proj, mm
            )


header_creation_functions = {
    'gen_input': model_configuration_callbacks_sprake._create_generation_header_summary,
    'stor_input': model_configuration_callbacks_sprake._create_storage_header_summary,
    'bc_input': model_configuration_callbacks_sprake._create_bc_header_summary,
    'dc_input': model_configuration_callbacks_sprake._create_dc_header_summary,
    'mc_input': model_configuration_callbacks_sprake._create_model_config_header_summary,
    'gen_costs': model_configuration_callbacks_sprake._create_cost_generation_header_summary,
    'stor_costs': model_configuration_callbacks_sprake._create_cost_storage_header_summary,
    'sales_costs': model_configuration_callbacks_sprake._create_cost_sales_header_summary,
    'import_costs': model_configuration_callbacks_sprake._create_cost_import_header_summary,
    'finance_settings': model_configuration_callbacks_sprake._create_finance_header_summary,
}

def _generic_create_deterministic_input_header_contents(
    section: str,
    mm: NewsegsMetaModel,
) -> list[dash.development.base_component.Component]:
    return header_creation_functions[section](mm)

for supersection, section_tuple in sections_by_supersection.items():
    for section in section_tuple:
        if section in header_creation_functions:
            @register_input_section_header_content_creator(supersection, section, MODEL_TYPE)
            def _(
                proj_id: str, 
                proj_provider: NewsegsProjectProviderInterface, 
                _section: str = section # Using default argument trick to force evaluation of section
            ) -> list[dash.development.base_component.Component]:
                if not proj_id:
                    raise PreventUpdate
                return _generic_create_deterministic_input_header_contents(
                    _section, get_focussed_metamodel(proj_id, proj_provider)
                )
