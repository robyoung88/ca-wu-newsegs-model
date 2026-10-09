from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.trackeddata import revision_dataclass


@revision_dataclass
class LightweightNewsegsModel(LightweightNewsegsComponent):
    model_data: LightweightNewsegsComponent
    table_config: LightweightNewsegsComponent
    grid: LightweightNewsegsComponent
    generation: LightweightNewsegsComponent
    consumption_storage: LightweightNewsegsComponent
    