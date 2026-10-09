from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.core.trackeddata import TableModifyingObservableOrderedDict, revision_dataclass
from newsegsmodelframework.newsegsfinance.lightweightnewsegsfinance import LightweightNewsegsFinance
from newsegsmodelframework.newsegsmodel.lightweightnewsegsmodel import LightweightNewsegsModel


@revision_dataclass
class LightweightNewsegsMetaModel(LightweightNewsegsComponent):
    table_config: LightweightNewsegsComponent
    model: LightweightNewsegsModel 
    finance: LightweightNewsegsFinance 
    variables: TableModifyingObservableOrderedDict
    location: Location
    