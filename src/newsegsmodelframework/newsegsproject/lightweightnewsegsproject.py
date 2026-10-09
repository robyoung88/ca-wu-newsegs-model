from dataclasses import field

from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.trackeddata import ObservableList, revision_dataclass


@revision_dataclass
class LightweightNewsegsProject(LightweightNewsegsComponent):
    table_config: LightweightNewsegsComponent
    dsa_config: LightweightNewsegsComponent
    psa_config: LightweightNewsegsComponent
    
    metamodels: ObservableList = field(default_factory = lambda: ObservableList([]))
    focussed_metamodel_id: str = ''
    focussed_metamodel_index: int = 0
