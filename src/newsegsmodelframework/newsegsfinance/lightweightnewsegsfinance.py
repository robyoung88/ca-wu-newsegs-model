"""Lightweightnewsegsfinance module.

TODO: Describe the purpose of the module.
"""
from typing import Optional

from newsegsmodelframework.core.lightweightnewsegscomponent import LightweightNewsegsComponent
from newsegsmodelframework.core.trackeddata import revision_dataclass
from newsegsmodelframework.newsegsmodel.lightweightnewsegsmodel import LightweightNewsegsModel


@revision_dataclass
class LightweightNewsegsFinance(LightweightNewsegsComponent):
    """Lightweight Newsegs Finance.

    TODO: Add a description.
    """
    finance_data: LightweightNewsegsComponent
    table_config: LightweightNewsegsComponent

    model: Optional[LightweightNewsegsModel] = None
    