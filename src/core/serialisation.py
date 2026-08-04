"""
Classes and mixins related to serialising and unserialising objects.

Classes inheriting the `SerialiseToDictMixin` are intended to be capable of
following this pattern:

- Instance creation and modification
- Export of instance configuration to dictionary (`.to_dict()`)
- Serialisation of dictionary (e.g. to json)
- Unserialisation of dictionary back to instance of original object (using
    constructor found by `core.find_constructor`)
- Update of instance using another configuration dictionary or another instance
    of the same class.

In order to be unserialised as a SerialiseToDictMixin, the class is required to
include an attribute `._constructor_class' which must be registered to
`core.constructors.registers.CONSTRUCTOR_CLASS_REGISTER` using the decorator function
`core.constructors.registers.register_constructor_class`

Example:
    class A(SerialiseToDictMixin):
        _constructor_class = 'MetaA'

        param: int
        def __init__(self, param: int):
            self.param = param

        def __eq__(self, other):
            return self.param == other.param
    
    from core.constructors.registers import register_constructor_class
    @register_constructor_class('MetaA')
    def meta_a_constructors():
        return {'A': A}
    
    foo = A(5)
    foo_dict = foo.to_dict()
    
    from core import find_constructor
    bar = find_constructor(foo_dict['constructor_class'], foo_dict['class'])(foodict)
    
    print (type(foo) == type(bar))
    print (foo == bar)

Exports:
    - SerialiseToDictMixin
    - timestamp_to_dict
    - datetime_to_dict
    - timedelta_to_dict
"""
from __future__ import annotations

import copy
from datetime import tzinfo, datetime
from typing import Any, Protocol, Sequence, Type, TypeAlias, TypeVar

import pandas as pd

from core import find_constructor

_TimeZoneScalar: TypeAlias = str | tzinfo

class _SerialiseToDictProtocol(Protocol):
    def to_dict(self) -> dict[str, Any]: ...
    def update(self, config: dict[str, Any]): ...

T = TypeVar('T', bound = _SerialiseToDictProtocol)

class SerialiseToDictMixin:
    """
    Mixin to provide a JSON-friendly dictionary representation for objects.

    Classes that inherit this mixin gain a `to_dict()` method which returns a
    dictionary containing the object's class name and constructor class
    (under keys 'class' and 'constructor_class') plus a representation of
    the instance attributes found in ``self.__dict__``.

    Attributes listed in ``_excluded_attributes`` are omitted from the
    dictionary. Subclasses should set ``_constructor_class`` to a string
    identifier used by the reconstruction mechanism (e.g. find_constructor).

    The mixin attempts to convert common Python and pandas types into
    serialisable forms via the ``_represent`` helper.

    Classes inheriting the `SerialiseToDictMixin` are intended to be capable of
    following this pattern:

    - Instance creation and modification
    - Export of instance configuration to dictionary (`.to_dict()`)
    - Serialisation of dictionary (e.g. `json.dumps`)
    - Unserialisation of dictionary back to instance of original object (using
        constructor found by [`core.find_constructor`][core.find_constructor])
    - Update of instance using another configuration dictionary or another instance
        of the same class.

    In order to be unserialised as a SerialiseToDictMixin, the class is required to
    include an attribute `._constructor_class` which must be registered to
    core.constructors.registers.CONSTRUCTOR_CLASS_REGISTER using the decorator function
    [register_constructor_class][core.register_constructor_class]

    Examples:
        ```python
        class A(SerialiseToDictMixin):
            _constructor_class = 'MetaA'

            param: int
            def __init__(self, param: int):
                self.param = param

            def __eq__(self, other):
                return self.param == other.param

        from core import register_constructor_class
        @register_constructor_class('MetaA')
        def meta_a_constructors():
            return {'A': A}

        foo = A(5)
        foo_dict = foo.to_dict()

        from core import find_constructor
        bar = find_constructor(foo_dict['constructor_class'], foo_dict['class'])(foo_dict)

        print (type(foo) == type(bar))
        print (foo == bar)
        ```
    """
    
    _constructor_class: str
    """
    Key for unserialise_dict
    """
    _excluded_attributes: tuple[str, ...] = ()
    """
    Attributes within self.__dict__ to exclude from dictionary representation
    """

    def to_dict(self) -> dict[str, Any]:
        """
        A dictionary representation of object.

        Includes keys `'class'` and `'constructor_class'` to identify and
        reconstruct object; be careful not to name attributes that clash.

        Will not include any attributes named in `self._excluded_attributes`.
        
        An attempt is made to represent values in json-friendly form.

        Attributes are found only in the ``__dict__`` attribute of the object; 
        slots are not inspected.

        Returns:
            dict[str, Any]: Dictionary representation of this object.
        """
        odict : dict[str, Any] =  {
            'class': self.__class__.__name__,
            'constructor_class': self._constructor_class,
        }
        ex_att = self._excluded_attributes
        odict.update(
            {
                prop: self._represent(value)
                for prop, value in self.__dict__.items() if not prop in ex_att
            }
        )
        return odict
    
    def _represent(self, value):
        if isinstance(value, object):
            if hasattr(value, 'to_dict'):
                return value.to_dict() # pyright: ignore[reportAttributeAccessIssue]
            elif isinstance(value, tuple):
                return tuple(self._represent(x) for x in value)
            elif isinstance(value, list):
                return [self._represent(x) for x in value]
            elif isinstance(value, dict):
                return {self._represent(k): self._represent(v) for k, v in value.items()}
            elif isinstance(value, set):
                return [self._represent(x) for x in value]
            elif isinstance(value, pd.Timestamp):
                return timestamp_to_dict(value)
            elif isinstance(value, pd.Timedelta):
                return timedelta_to_dict(value)
            elif isinstance(value, _TimeZoneScalar):
                return str(value)
            elif isinstance(value, datetime):
                return datetime_to_dict(value)
            else:
                return value
        else:
            return value
        
    def update(self, config: dict[str, Any] | Type[T]):
        """
        Update instance with attributes from dictionary or another instance.

        If `config` does not include a key "`'class'`", then no type checking
        will occur and the method will update the ``.__dict__`` attribute
        of the instance without guardrails.

        Args:
            config (dict[str, Any] | Type[T]): 
                Dictionary generated by ``.to_dict()`` or another instance of the present class.

        Raises:
            ValueError: If the class named in `config` dictionary does not
                match that of this object.
        """
        type_ = type(self)
        if not isinstance(config, dict):
            vars(self).update(copy.copy(vars(config)))
            return
        config = config.copy()
        classname = config.pop('class', None)
        if not classname is None:
            if self.__class__.__name__ != classname:
                raise ValueError(f'Configuration for class {classname} cannot be applied to an instance of class {self.__class__.__name__}')
        
        # Get rid of constructor class string for this instance
        config.pop('constructor_class', None)

        config = type_.unserialise_dict(config)
        
        conf_keys = config.keys()
        has_update = {}
        for k, v in vars(self).items():
            if k in conf_keys:
                if hasattr(v, 'update'):
                    has_update[k] = config[k]
        
        for k in has_update.keys():
            config.pop(k)

        vars(self).update(config)

        for k, v in has_update.items():
            getattr(self, k).update(v)
                    
    @classmethod
    def from_dict(
        cls: Type[T], 
        config: dict[str, Any]
    ) -> T:
        """
        Create a new instance of class configured per a dictionary.

        Args:
            config (dict[str, Any]): Dictionary generated by `.to_dict()`

        Returns:
            T: Instance of the class inheriting SerialiseToDictMixin
        """
        inst = cls.__new__(cls)
        inst.update(config)
        return inst
    
    @classmethod
    def unserialise_dict(
        cls,
        config: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Unserialise all values in a dictionary recursively.

        Uses core.find_constructor to perform unserialisation where values are
        dictionaries with keys `'constructor_class'` and `'class'`.
        Args:
            config (dict[str, Any]): Dictionary generated by `.to_dict`

        Returns:
            dict[str, Any]: Dictionary with the same keys as `config` but with
                all values replaced by their unserialised versions, recursively.
        """
        update_items = {}
        for k, v in config.items():
            if isinstance(v, dict):
                child_cc = v.get('constructor_class', None)
                child_classname = v.get('class', None)
                if child_cc is not None and child_classname is not None:
                    update_items[k] = find_constructor(child_cc, child_classname)(v)
                else:
                    # Recurse in case the dict contains a SerialiseToDictMixin within a child dictionary
                    update_items[k] = cls.unserialise_dict(v)
            elif not isinstance(v, str) and isinstance(v, Sequence):
                requiresupdate = False
                for childv in v:
                    if isinstance(childv, dict):
                        requiresupdate = True
                        break
                if requiresupdate:
                    templist = list(v)
                    for i, childv in enumerate(v):
                        if isinstance(childv, dict):
                            child_cc = childv.get('constructor_class', None)
                            child_classname = childv.get('class', None)
                            if child_cc is not None and child_classname is not None:
                                templist[i] = find_constructor(child_cc, child_classname)(childv)
                            else:
                                templist[i] = cls.unserialise_dict(childv)
                    update_items[k] = type(v)(templist) # pyright: ignore[reportCallIssue]

        config.update(update_items)
        return config

def timestamp_to_dict(ts: pd.Timestamp) -> dict[str, str]:
    return {
        'class': 'Timestamp',
        'constructor_class': 'Timestamp',
        'ts_input' : str(ts),
        'tz': str(ts.tz)
    }

def datetime_to_dict(ts: datetime) -> dict[str, Any]:
    return {
        'class': 'datetime',
        'constructor_class': 'datetime',
        'value' : ts.isoformat()
    }

def timedelta_to_dict(td: pd.Timedelta) -> dict[str, str]:
    return{
        'class': 'Timedelta',
        'constructor_class': 'Timedelta',
        'value': str(td)
    }
