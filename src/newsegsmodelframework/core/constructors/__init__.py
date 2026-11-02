"""Creating class instances from dictionaries (e.g. from JSON).

Modules:
    constructors: `find_constructor`, which looks up the constructor for a stored class name.
    registers: The registries of classes that can be constructed, and the means to add to them.
"""
from .registers import get_subclasses_in_module

__all__ = ['get_subclasses_in_module']