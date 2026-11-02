"""NewSEGS Energy Models.

A NewSEGS Energy Model is composed of grid, generation and consumption and storage modules, and
the environment servers that supply them with weather data. It is run over a time span and
holds the results of the modules. The base class and the Sprake implementation are exposed here.

Modules:
    newsegsmodel: `NewsegsModel`, the base class of NewSEGS Energy Models, and its data and configuration.
    sprakemodel: `SprakeModel`, the Sprake NewSEGS Energy Model.
    lightweightnewsegsmodel: `LightweightNewsegsModel`, a description of a NewSEGS Energy Model without the machinery to run it.
"""
from .newsegsmodel import NewsegsModel
from .sprakemodel import SprakeModel
__all__ = ['NewsegsModel', 'SprakeModel']
