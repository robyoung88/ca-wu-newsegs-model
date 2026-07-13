"""
Lookups for creating class instances from dictionaries (e.g. from JSON)
"""
import functools
from typing import Any, Callable

from core.constructors import registers

def _deferred_constructor_update_from_dict(
    constructor_func: functools.partial
) -> Callable[[dict[str, Any]], object]:
    """
    NB
    """
    def from_dict(config: dict[str, Any]):
        var = constructor_func('Placeholder')
        var.update(config)
        return var
    return from_dict

def find_constructor(
    constructor_class: registers.CONSTRUCTOR_CLASS,
    classname: str
) -> Callable[[dict[str, Any]], object]:
    reg = registers.get_register(constructor_class)

    constr = reg.get(classname, None)
    if constr is None:
        raise ValueError(f'classname not found in constructor register: {classname}')

    if isinstance(constr, functools.partial):
        constr = _deferred_constructor_update_from_dict(constr)
        return constr

    if not hasattr(constr, 'from_dict'):
        if not hasattr(constr, '__name__'):
            raise AttributeError(f'class {type(constr)} does not implement SerialiseToDictMixin (no from_dict classmethod)')
        else:
            raise AttributeError(f'class {constr.__name__} does not implement SerialiseToDictMixin (no from_dict classmethod)') # pyright: ignore[reportAttributeAccessIssue]

    return constr.from_dict # pyright: ignore[reportAttributeAccessIssue]
