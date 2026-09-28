"""
Lookups for creating class instances from dictionaries (e.g. from JSON).
"""
import functools
from typing import Any, Callable

from newsegsmodelframework.core.constructors import registers

def _deferred_constructor_update_from_dict(
    constructor_func: functools.partial
) -> Callable[[dict[str, Any]], object]:
    """Wrap a deferred constructor so it can be invoked with a dictionary.

    The wrapped constructor is expected to accept a placeholder argument
    and return an object with an `update` method. The returned callable
    creates the object and applies the configuration dictionary to it.

    Args:
        constructor_func: A partially applied constructor function.

    Returns:
        A callable that accepts a dictionary and returns an instantiated object.
    """
    def from_dict(config: dict[str, Any]):
        var = constructor_func('Placeholder')
        var.update(config)

        # The update will have messed with the revision number, so reset that
        revis = config.get('_config', {}).get('_revision')
        if revis is not None:
            var.revision = revis
            
        return var
    return from_dict

def find_constructor(
    constructor_class: str,
    classname: str
) -> Callable[[dict[str, Any]], object]:
    """
    Retrieve a constructor callable from the registry.

    Looks up the registry associated with `constructor_class` and then the
    registered constructor for `classname`. If the constructor is a
    functools.partial, a deferred dictionary-based constructor is returned.
    Otherwise, the registered class must implement a `from_dict` classmethod.

    Args:
        constructor_class: Name of the constructor registry.
        classname: Name of the registered constructor.

    Returns:
        A callable that accepts a dictionary and returns an instantiated object.

    Raises:
        ValueError: If the classname is not found in the constructor register.
        AttributeError: If the registered constructor does not implement `from_dict`.
    """
    reg = registers.get_register(constructor_class)

    constr = reg.get(classname, None)
    if constr is None:
        raise ValueError(f'classname not found in constructor register: {classname} in {constructor_class}; available keys are: {list(reg.keys())}')

    if isinstance(constr, functools.partial):
        constr = _deferred_constructor_update_from_dict(constr)
        return constr

    if not hasattr(constr, 'from_dict'):
        if not hasattr(constr, '__name__'):
            raise AttributeError(f'class {type(constr)} does not implement SerialiseToDictMixin (no from_dict classmethod)')
        else:
            raise AttributeError(f'class {constr.__name__} does not implement SerialiseToDictMixin (no from_dict classmethod)') # pyright: ignore[reportAttributeAccessIssue]

    return constr.from_dict # pyright: ignore[reportAttributeAccessIssue]
