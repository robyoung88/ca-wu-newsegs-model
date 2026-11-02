"""Lightweight descriptions of components: the identifying information of a component without the component.
"""
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass


@revision_dataclass
class LightweightNewsegsComponent(DataWithRevision):
    """Description of a component, for display and storage, without the machinery to run it.

    Holds the id and the label. The lightweight classes of models, finance, metamodels, projects and
    variables extend it.
    """
    id: str


@revision_dataclass
class LightweightDataHoldingNewsegsComponent(LightweightNewsegsComponent):
    """Representation of a component that might be used to hold results data against"""
    component_type: str
    component_class: str
    component_version: str
