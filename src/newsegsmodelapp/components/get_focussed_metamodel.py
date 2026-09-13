from typing import cast

from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsproject import NewsegsProjectProviderInterface
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel

# TODO: make a memoised helper function - but possibly this could go on the project provider.

def get_focussed_metamodel(proj_id: str, proj_provider: NewsegsProjectProviderInterface) -> NewsegsMetaModel:
    proj = proj_provider.get_project(proj_id)
    return proj.get_focussed_metamodel()
