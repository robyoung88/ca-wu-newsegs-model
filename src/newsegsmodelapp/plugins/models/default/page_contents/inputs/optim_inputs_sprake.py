"""Register input container and input header container content creators for optim supersection"""
import dash

from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface

from newsegsmodelapp.components.composite_input_components import generic_create_optim_input_container_contents
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.registers import register_input_container_content_creator

MODEL_TYPE = 'sprake'
@register_input_container_content_creator('optim', None, MODEL_TYPE)
def _(
    proj_id: str,
    proj_provider: NewsegsProjectProviderInterface,
) -> list[dash.development.base_component.Component]:
    return generic_create_optim_input_container_contents(
        get_focussed_metamodel(proj_id, proj_provider)
    )
