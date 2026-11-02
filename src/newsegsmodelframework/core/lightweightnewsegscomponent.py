from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass


@revision_dataclass
class LightweightNewsegsComponent(DataWithRevision):
    id: str


@revision_dataclass
class LightweightDataHoldingNewsegsComponent(LightweightNewsegsComponent):
    """Representation of a component that might be used to hold results data against"""
    component_type: str
    component_class: str
    component_version: str
