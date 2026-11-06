"""The `LightweightNewsegsMetaModel` description of a metamodel."""
from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.core.trackeddata import TableModifyingObservableOrderedDict, revision_dataclass
from newsegsmodelframework.newsegsfinance.lightweightnewsegsfinance import LightweightNewsegsFinance
from newsegsmodelframework.newsegsmodel.lightweightnewsegsmodel import LightweightNewsegsModel


@revision_dataclass
class LightweightNewsegsMetaModel(LightweightNewsegsComponent):
    """A description of a `NewsegsMetaModel` without the machinery to run it.

    Holds the lightweight model, finance, variables and optimisation settings, and the location, which is what is
    needed to display and edit a metamodel without constructing the full model.
    """
    name: str
    table_config: LightweightNewsegsComponent
    model: LightweightNewsegsModel 
    finance: LightweightNewsegsFinance 
    variables: TableModifyingObservableOrderedDict
    location: Location
    optim_config: LightweightNewsegsComponent | None = None
    """The optimisation settings; `None` if the metamodel was saved without them."""
