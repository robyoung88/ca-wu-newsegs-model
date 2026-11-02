"""Grid modules of a NewSEGS Energy Model.

A grid module models the exchange of electricity with the wider grid. The base class is
exposed here; the implementation used by the Sprake model is in `sprakegrid`.

Modules:
    newsegsgrid: `NewsegsGrid`, the base class.
    sprakegrid: `SprakeGrid`, the Sprake grid module.
    constructors: Construction of a grid module from a dictionary.
"""
from .newsegsgrid import NewsegsGrid
__all__ = ['NewsegsGrid']
