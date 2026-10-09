from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass


@revision_dataclass
class LightweightNewsegsComponent(DataWithRevision):
    id: str
    