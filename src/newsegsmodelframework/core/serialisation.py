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
import json
from typing import Any, Protocol, Sequence, Type, TypeAlias, TypeVar, override, runtime_checkable

import pandas as pd

from newsegsmodelframework.util import jsonfuncs

_TimeZoneScalar: TypeAlias = str | tzinfo

@runtime_checkable
class SerialiseToDictProtocol(Protocol):
    def to_dict(self) -> dict[str, Any]: ...
    def update(self, config: dict[str, Any]): ...

    @classmethod
    def unserialise_dict(cls, config: dict[str, Any]) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls: Type[T], config: dict[str, Any]) -> T: ...

T = TypeVar('T', bound = SerialiseToDictProtocol)
V = TypeVar('V', bound = 'SerialiseToDictMixin')


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
    _excluded_attributes: set[str] = set()
    """
    Attributes within self.__dict__ to exclude from dictionary representation
    """

    @classmethod
    def _get_all_slots(cls) -> set[str]:
        """Traverse the Class Method Resolution Order (MRO) to collect all slot names,

        including slots inherited from base classes.
        """
        slots = set()
        for base in cls.__mro__:
            if hasattr(base, "__slots__"):
                b_slots = getattr(base, "__slots__")
                # __slots__ can be a string, tuple, or list
                if isinstance(b_slots, str):
                    slots.add(b_slots)
                else:
                    slots.update(b_slots)
        # '__dict__' and '__weakref__' are internal slot markers; exclude them
        slots.discard("__dict__")
        slots.discard("__weakref__")
        return slots

    def get_excluded_attributes(self) -> set[str]:
        """A set of the names of the attributes to be excluded from the state representation of the object
        
        Use for attributes that should be reconstructed or reattached on unserialisation of the object
        """
        return self._excluded_attributes

    def _prepare_object_state(self):
        """Any preprocessing necessary before object state is captured"""

    def _get_state_class_values(self):
        return {
            'class': self.__class__.__name__,
            'constructor_class': self._constructor_class,
        }

    def _to_dict_generic(self, exclusions: set[str] = set()):
        odict = {}

        odict.update(self._get_state_class_values())

        # __dict__ entries
        odict.update(
            {
                prop: self._represent(value)
                for prop, value in self.__dict__.items() if not prop in exclusions
            }
        )

        # Slots
        valid_slots = self._get_all_slots() - exclusions
        for slot in valid_slots:
            try:
                odict[slot] = self._represent(getattr(self, slot))
            except AttributeError:
                # Unassigned slots raise AttributeError when accessed
                pass

        return odict

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
        self._prepare_object_state()

        exclusions = self.get_excluded_attributes()

        odict = self._to_dict_generic(exclusions)

        return odict

    def json_dumps(self) -> str:
        """
        A json representation of the object dictionary

        Returns:
            str: String which may be converted to a dictionary representation of the object with json.loads
        """
        return json.dumps(self.to_dict(), cls = jsonfuncs.NumpyEncoder)
    
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

    def _preupdate_from_dict(self, config):
        """Actions prior to the main __dict__ update step"""

    def _main_update_from_dict(self, config):
        """Logic for updating the __dict__ and slots from an unserialised dict"""
        #conf_keys = config.keys()
        
        # If existing attributes have an update method, want to use that
        # rather than direct assignment.
        has_update = {}
        for k in config.keys():
            try:
                att = getattr(self, k)
                if hasattr(att, 'update'):
                    has_update[k] = config[k]
            except AttributeError:
                continue

        # for k, v in vars(self).items():
        #     if k in conf_keys:
        #         if hasattr(v, 'update'):
        #             has_update[k] = config[k]
        
        for k in has_update.keys():
            config.pop(k)

        # Don't just update the dict, as this will prevent revision notifiers firing
        for k, v in config.items():
            setattr(self, k, v)

        for k, v in has_update.items():
            getattr(self, k).update(v)


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
            for k, v in vars(config).items():
                setattr(self, k, copy.copy(v))
            return
        
        config = config.copy()
        classname = config.pop('class', None)
        if not classname is None:
            if self.__class__.__name__ != classname:
                raise ValueError(f'Configuration for class {classname} cannot be applied to an instance of class {self.__class__.__name__}')
        
        # Get rid of constructor class string for this instance
        config.pop('constructor_class', None)

        config = type_.unserialise_dict(config)

        self._preupdate_from_dict(config)

        self._main_update_from_dict(config)

    @classmethod
    def _unserialise_single_element(cls, x: Any) -> Any:
        from newsegsmodelframework.core.constructors.constructors import find_constructor
        if isinstance(x, dict):
            child_cc = x.get('constructor_class', None)
            child_classname = x.get('class', None)
            if child_cc is not None and child_classname is not None:
                return find_constructor(child_cc, child_classname)(x)
            else:
                return cls.unserialise_dict(x)
        elif not isinstance(x, str) and isinstance(x, Sequence):
            return [cls._unserialise_single_element(y) for y in x]
        else:
            return x

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
        return_dict = {}

        for k, v in config.items():
            return_dict[k] = cls._unserialise_single_element(v)
            
        return return_dict
                    
    @classmethod
    def from_dict(
        cls: Type[V], 
        config: dict[str, Any]
    ) -> V:
        """
        Create a new instance of class configured per a dictionary.

        Args:
            config (dict[str, Any]): Dictionary generated by `.to_dict()`

        Returns:
            T: Instance of the class inheriting SerialiseToDictMixin
        """
        inst = cls.__new__(cls)
        config = cls.unserialise_dict(config)
        inst.update(config)
        return inst

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


class StateSerialiseToDictMixin(SerialiseToDictMixin):
    """Extends SerialiseToDictMixin with __getstate__ and __setstate__"""

    def _prepare_object_state(self):
        """Any preprocessing necessary before object state is captured"""

    def _getstate_generic(self, exclusions: set[str] = set()):
        state: dict[str, Any] = {}

        # 1. Capture __dict__ entries if present
        if hasattr(self, "__dict__"):
            if len(exclusions) == 0:
                state.update(self.__dict__)
            else:
                state.update(
                    {
                        prop: value
                        for prop, value in self.__dict__.items() if not prop in exclusions
                    }
                )

        # 2. Capture __slots__ entries (checking slot availability safely)
        valid_slots = self._get_all_slots() - exclusions
        for slot in valid_slots:
            try:
                state[slot] = getattr(self, slot)
            except AttributeError:
                # Unassigned slots raise AttributeError when accessed
                pass

        return state

    def _postprocess_state_dictionary(self, state: dict[str, Any]):
        """Any postprocessing necessary on the object state dictionary."""

    def __getstate__(self) -> dict[str, Any]:

        self._prepare_object_state()
        excludes = self.get_excluded_attributes()
        state = self._getstate_generic(excludes)
        self._postprocess_state_dictionary(state)

        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restores instance state.

        Uses setattr() to route assignments through custom __setattr__ hooks,
        property setters, or mixin delegations.
        """
        # If your __setattr__ requires specific base attributes to exist first
        # (e.g., _children, _subscribers, _config), extract and set them prior
        # to iterating over remaining state key-value pairs.

        self._preupdate_from_dict(state)

        for key, value in state.items():
            # Trigger custom __setattr__ logic
            setattr(self, key, value)


class GenericStateMixin:
    """Mixin providing robust __getstate__ and __setstate__ supporting __dict__,
    __slots__, inheritance hierarchies, and custom __setattr__ routing.
    """

    @classmethod
    def _get_all_slots(cls) -> set[str]:
        """Traverse the Class Resolution Order (MRO) to collect all slot names,

        including slots inherited from base classes.
        """
        slots = set()
        for base in cls.__mro__:
            if hasattr(base, "__slots__"):
                b_slots = getattr(base, "__slots__")
                # __slots__ can be a string, tuple, or list
                if isinstance(b_slots, str):
                    slots.add(b_slots)
                else:
                    slots.update(b_slots)
        # '__dict__' and '__weakref__' are internal slot markers; exclude them
        slots.discard("__dict__")
        slots.discard("__weakref__")
        return slots

    def __getstate__(self) -> dict[str, Any]:
        state: dict[str, Any] = {}

        # 1. Capture __dict__ entries if present
        if hasattr(self, "__dict__"):
            state.update(self.__dict__)

        # 2. Capture __slots__ entries (checking slot availability safely)
        for slot in self._get_all_slots():
            try:
                state[slot] = getattr(self, slot)
            except AttributeError:
                # Unassigned slots raise AttributeError when accessed
                pass

        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Restores instance state.

        Uses setattr() to route assignments through custom __setattr__ hooks,
        property setters, or mixin delegations.
        """
        # If your __setattr__ requires specific base attributes to exist first
        # (e.g., _children, _subscribers, _config), extract and set them prior
        # to iterating over remaining state key-value pairs.

        for key, value in state.items():
            # Trigger custom __setattr__ logic
            setattr(self, key, value)