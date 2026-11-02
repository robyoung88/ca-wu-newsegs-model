"""Finance models: valuation of the output of a NewSEGS Energy Model.

A finance model takes the results of a NewSEGS Energy Model and values them over a finance
horizon. The base class and the discounting functions used by the finance and statistics
code are exposed here; the implementation used by the Sprake model is in `sprakefinance`.

Modules:
    common: Discounting and aggregation functions shared by the finance models.
    newsegsfinance: `NewsegsFinance`, the base class, and its data and configuration.
    sprakefinance: `SprakeFinance`, the Sprake finance model.
    lightweightnewsegsfinance: `LightweightNewsegsFinance`, a description of a finance model without the machinery to run it.
"""
from .common import apply_discount_factor, sum_all_to_horizon # Need to ensure imported first
from .newsegsfinance import NewsegsFinance
__all__ = ['NewsegsFinance', 'apply_discount_factor', 'sum_all_to_horizon']
