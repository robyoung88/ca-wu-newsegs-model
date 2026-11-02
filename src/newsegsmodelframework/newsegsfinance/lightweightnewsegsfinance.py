"""The `LightweightNewsegsFinance` description of a finance model.
"""
from typing import Optional

from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.trackeddata import revision_dataclass
from newsegsmodelframework.newsegsmodel.lightweightnewsegsmodel import LightweightNewsegsModel


@revision_dataclass
class LightweightNewsegsFinance(LightweightNewsegsComponent):
    """Description of a finance model without the machinery to run it: its data, table configuration and, optionally, its NewSEGS Energy Model.
    """
    finance_data: LightweightNewsegsComponent
    table_config: LightweightNewsegsComponent

    model: Optional[LightweightNewsegsModel] = None
    