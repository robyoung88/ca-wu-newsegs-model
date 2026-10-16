
"""Register input container and input header container content creators for dsa supersection"""
import logging
logger = logging.getLogger(__name__)

from typing import cast

import dash

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface

from newsegsmodelapp.components.composite_input_components import generic_create_dsa_input_container_contents
from newsegsmodelapp.components.get_focussed_metamodel import get_focussed_metamodel
from newsegsmodelapp.components.variable_dash_component import vdc as var_dc
from newsegsmodelapp.registers import register_input_container_content_creator, register_single_input_header_content_creator
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

MODEL_TYPE = 'sprake'
@register_input_container_content_creator('dsa', None, MODEL_TYPE)
def _(
    proj_id: str,
    proj_provider: NewsegsProjectProviderInterface,
) -> list[dash.development.base_component.Component]:
    provider = cast(FromDatabaseNewsegsProjectProvider, proj_provider)
    logger.debug('Getting lightweight project - Creating DSA Input Container contents')
    lproj = provider.get_lightweight_project(proj_id)
    lmm = lproj.metamodels[lproj.focussed_metamodel_index]
    return generic_create_dsa_input_container_contents(
        lmm, provider.variable_provider
    )

@register_single_input_header_content_creator('dsa', None, MODEL_TYPE)
def _(
    varid: str,
    var: variable.Variable | FullLightweightVariable,
) -> list[dash.development.base_component.Component]:
    
    if not var or not isinstance(var, (variable.Variable, FullLightweightVariable)):
        return []
    return var_dc.create_dsa_header(var) # pyright: ignore[reportArgumentType]
