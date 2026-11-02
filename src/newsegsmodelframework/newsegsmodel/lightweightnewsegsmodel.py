"""The `LightweightNewsegsModel` description of a NewSEGS Energy Model.
"""
from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.trackeddata import revision_dataclass


@revision_dataclass
class LightweightNewsegsModel(LightweightNewsegsComponent):
    """Description of a NewSEGS Energy Model without the machinery to run it: the lightweight descriptions of its modules, data and table configuration.
    """
    name: str
    model_type: str
    model_data: LightweightNewsegsComponent
    table_config: LightweightNewsegsComponent
    grid: LightweightNewsegsComponent
    generation: LightweightNewsegsComponent
    consumption_storage: LightweightNewsegsComponent
    