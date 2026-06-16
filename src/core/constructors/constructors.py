"""
Lookups for creating class instances from dictionaries (e.g. from JSON)
"""
from typing import Any, Callable

from core.constructors import registers

def find_constructor(
    constructor_class: registers.CONSTRUCTOR_CLASS,
    classname: str
) -> Callable[[dict[str, Any]], object]:
    reg = registers.get_register(constructor_class)

    constr = reg.get(classname, None)
    if constr is None:
        raise ValueError(f'classname not found in constructor register: {classname}')        
    
    if not hasattr(constr, 'from_dict'):
        raise AttributeError(f'class {constr.__name__} does not implement SerialiseToDictMixin (no from_dict classmethod)')

    return constr.from_dict
