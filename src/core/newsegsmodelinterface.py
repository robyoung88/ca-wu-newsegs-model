"""
Abstract base class defining the minimal interface for a NewsegsModel
"""
from __future__ import annotations

from core import environmentserverinterface
from core import resultsserverinterface
from core import newsegscomponent
from core import newsegsmodeltimeinterface

class NewsegsModelInterface(
    environmentserverinterface.EnvironmentServerInterface,
    resultsserverinterface.ResultServerInterface,
    newsegsmodeltimeinterface.NewsegsModelTimeInterface,
    newsegscomponent.RunnableNewsegsComponent,
    
):
    ...
