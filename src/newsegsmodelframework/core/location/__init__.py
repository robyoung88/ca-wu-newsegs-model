"""Locations of NewSEGS sites.

The classes are defined in the `location` module: `Location`, `RaisedLocation` (with a height)
and `AspectLocation` (with a height, slope and aspect), and the wrappers of the pvlib classes
`PVLibLocation` and `PVLibPVSystem`.
"""
from .location import Location, RaisedLocation, AspectLocation, PVLibLocation, PVLibPVSystem
__all__ = ['Location', 'RaisedLocation', 'AspectLocation', 'PVLibLocation', 'PVLibPVSystem']
