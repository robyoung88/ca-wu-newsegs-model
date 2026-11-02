"""Locations of NewSEGS sites.

The classes (`Location`, `RaisedLocation`, `AspectLocation`) are defined in the `location`
module, with the pvlib wrappers `PVLibLocation` and `PVLibPVSystem`.
"""
from .location import *
__all__ = ['Location', 'RaisedLocation', 'AspectLocation', 'PVLibLocation', 'PVLibPVSystem']
