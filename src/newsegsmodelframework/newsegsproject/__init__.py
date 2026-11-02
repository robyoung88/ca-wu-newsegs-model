"""Projects: collections of metamodels with shared variables and sensitivity analysis settings.

Modules:
    newsegsproject: `NewsegsProject`, and its configuration.
    newsegsprojectprovider: `NewsegsProjectProviderInterface`, the interface of a store of projects.
    lightweightnewsegsproject: `LightweightNewsegsProject`, a description of a project without the machinery to run it.
"""
from .newsegsproject import NewsegsProject
from .newsegsprojectprovider import NewsegsProjectProviderInterface

__all__ = [
    'NewsegsProject',
    'NewsegsProjectProviderInterface',
]
