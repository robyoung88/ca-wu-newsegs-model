"""Metamodels: the unit that is configured, run and analysed.

A metamodel binds an energy model, a finance model and the variables that characterise
their parameters, and runs them together. See `NewsegsMetaModel` for the details of what
it holds and the states it can be put in.

Modules:
    newsegsmetamodel: The full `NewsegsMetaModel` and its configuration.
    lightweightnewsegsmetamodel: `LightweightNewsegsMetaModel`, a description of a metamodel
        without the machinery to run it.
"""
from .newsegsmetamodel import NewsegsMetaModel, NewsegsMetaModelConfig
__all__ = ['NewsegsMetaModel', 'NewsegsMetaModelConfig']