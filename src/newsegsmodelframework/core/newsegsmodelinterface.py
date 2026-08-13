"""
Abstract base class defining the minimal interface for a NewsegsModel
"""
from __future__ import annotations

from newsegsmodelframework.core import environmentserverinterface
from newsegsmodelframework.core import resultsserverinterface
from newsegsmodelframework.core import newsegscomponent
from newsegsmodelframework.core import newsegsmodeltimeinterface

class NewsegsModelInterface(
    environmentserverinterface.EnvironmentServerInterface,
    resultsserverinterface.ResultServerInterface,
    newsegsmodeltimeinterface.NewsegsModelTimeInterface,
    newsegscomponent.RunnableNewsegsComponent,
    
):
    ...
