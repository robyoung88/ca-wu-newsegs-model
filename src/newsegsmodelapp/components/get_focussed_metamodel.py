"""Getting the focussed metamodel of a project.
"""
from typing import cast

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel

# TODO: make a memoised helper function - but possibly this could go on the project provider.

def get_focussed_metamodel(proj_id: str, proj_provider: NewsegsProjectProviderInterface) -> NewsegsMetaModel:
    """Get the focussed metamodel of a project.

    Args:
        proj_id: Id of the project.
        proj_provider: Provider of projects.

    Returns:
        The metamodel.
    """
    proj = proj_provider.get_project(proj_id)
    return proj.get_focussed_metamodel()

def get_focussed_lightweight_metamodel(proj_id, project_provider):
    """Get the lightweight description of the focussed metamodel of a project.

    Cheaper than `get_focussed_metamodel`, for when only display information is needed.

    Args:
        proj_id: Id of the project.
        project_provider: Provider of projects, metamodels and variables.

    Returns:
        The lightweight metamodel.
    """
    provider = cast(FromDatabaseNewsegsProjectProvider, project_provider)
    lproj = provider.get_lightweight_project(proj_id)
    return lproj.metamodels[lproj.focussed_metamodel_index]
