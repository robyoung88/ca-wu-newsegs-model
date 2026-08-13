"""Provides base class and implementations of NewsegsFinance."""
from newsegsmodelframework.newsegsfinance.common import * # Need to ensure imported first
from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsfinance.sprakefinance import SprakeFinance
__all__ = ['NewsegsFinance', 'SprakeFinance']
