from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.trackeddata import revision_dataclass


@revision_dataclass
class LightweightNewsegsModel(LightweightNewsegsComponent):
    name: str
    model_type: str
    model_data: LightweightNewsegsComponent
    table_config: LightweightNewsegsComponent
    grid: LightweightNewsegsComponent
    generation: LightweightNewsegsComponent
    consumption_storage: LightweightNewsegsComponent
    