"""
Abstract base class defining the minimal interface for a NewsegsFinance
"""
from __future__ import annotations

from newsegsmodelframework.core import newsegscomponent

class NewsegsFinanceInterface(
    newsegscomponent.RunnableNewsegsComponent,
):
    ...