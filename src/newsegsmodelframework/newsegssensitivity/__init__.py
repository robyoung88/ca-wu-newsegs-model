"""Sensitivity analysis and optimisation of metamodels.

Modules:
    dsa: Deterministic (one-way) sensitivity analysis, `DSAComponent`, and `run_dsa`.
    psa: Probabilistic sensitivity analysis, `PSAComponent`, its configuration and the analysis of its results.
    optim: Optimisation of the variables of a metamodel.
    common: Functions shared by the analyses.
"""
from .dsa import run_dsa
__all__ = ['run_dsa']
