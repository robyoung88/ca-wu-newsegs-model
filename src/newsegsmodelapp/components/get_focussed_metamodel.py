"""Get focussed metamodel module.

TODO: Describe the purpose of the module.
"""
from typing import cast

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel

# TODO: make a memoised helper function - but possibly this could go on the project provider.

def get_focussed_metamodel(proj_id: str, proj_provider: NewsegsProjectProviderInterface) -> NewsegsMetaModel:
    """Get focussed metamodel.

    TODO: Add a description.

    Args:
        proj_id: TODO.
        proj_provider: TODO.

    Returns:
        TODO.
    """
    proj = proj_provider.get_project(proj_id)
    return proj.get_focussed_metamodel()

def get_focussed_lightweight_metamodel(proj_id, project_provider):
    """Get focussed lightweight metamodel.

    TODO: Add a description.

    Args:
        proj_id: TODO.
        project_provider: TODO.

    Returns:
        TODO.
    """
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(proj_id)
    return lproj.metamodels[lproj.focussed_metamodel_index]
