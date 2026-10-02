"""
Classes and functions to enable automatic tracking of changes in members
"""
from abc import ABCMeta
from collections import OrderedDict
import copy
from dataclasses import dataclass, fields, asdict
import re
from typing import Any, Callable, Collection, Iterable, Mapping, Optional, SupportsIndex, Type, TypeVar, dataclass_transform, override
from typing_extensions import Self
import warnings
import uuid as mod_uuid

import numpy as np

from newsegsmodelframework.core import serialisation

IMMUTABLE_TYPES = (
    int, float, str, bool, bytes, complex,
    tuple, frozenset, type(None)
)

__all__ = [
    'NoConfig',
]

class RevisionNotifierMixin():
    """Handles part-child notifications and revision counts"""
    
    def __init__(
        self, 
        children: Optional[Collection['RevisionNotifierMixin']] = None
    ):
        self._last_syncronised = 0
        self._revision = 0
        self._children = []
        if children is not None:
            for x in children:
                self._add_child(x)

    def _add_child(self, child: 'RevisionNotifierMixin', subscribe: bool = True):
        
        if child is self:
            raise ValueError('Circular reference - cannot add self as child.')

        # Can hold multiple copies of a child - Removals MUST be performed.
        self._children.append(child)

        if subscribe and isinstance(child, SubscriptionRevisionNotifierMixin):
            child._subscribers.append(self)

    def _remove_child(self, child: 'RevisionNotifierMixin'):
        # Don't use remove, need to check for instance equality
        for idx, inlist in enumerate(self._children):
            if inlist is child:
                # Pop the first, then stop. If multiple entries for child, that's OK.
                self._children.pop(idx)

                # Don't like testing against an inheriting class, but it gets the job done
                if isinstance(child, SubscriptionRevisionNotifierMixin):
                    child.unsubscribe(self)
                
                return

    @property
    def revision(self) -> int:
        return self._revision

    @revision.setter
    def revision(self, revision: int):
        self._revision = revision

    def _notify_change(self):
        if not hasattr(self, '_revision'):
            self._revision = 0
        self._revision += 1

    def _syncronise(self):
        """Use after saving status (to database)"""
        self._last_syncronised = self.revision

    def _chain_syncronise(self):
        self._syncronise()
        for child in self._children:
            child._chain_syncronise()

    @property
    def modified(self) -> bool:
        return self._last_syncronised != self.revision

    @property
    def chain_modified(self) -> bool:
        return (
            self.modified 
            or any((child.chain_modified for child in self._children))
        )

    def __setstate__(self, state):
        
        r0 = state.pop("_revision", [])
        object.__setattr__(self, "_revision", r0)
        object.__setattr__(self, "_children", state.pop("_children", []))


        # Restore remaining state (invokes __setattr__ for each remaining key)
        for key, value in state.items():
            setattr(self, key, value)

        # Reset revision
        setattr(self, "_revision", r0)

    def __getstate__(self) -> dict:
        odict = copy.copy(vars(self))
        del odict['_children']

        return odict
    

T = TypeVar('T')

@dataclass_transform()
def revision_dataclass(cls: Type[T]) -> Type[T]:
    """Class decorator applying dataclass setup and intercepting attribute changes."""
    
    # 1. Transform into a dataclass first
    cls = dataclass(cls)

    # Flag that decorator was applied
    cls._is_revision_dataclass = True # pyright: ignore[reportAttributeAccessIssue]

    # Capture the dataclass-generated __init__
    orig_init = cls.__init__

    def new_init(self, *args, **kwargs):
        # Initialize internal revision tracking before dataclass assigns fields
        SubscriptionRevisionNotifierMixin.__init__(self)

        # Run standard dataclass initializer
        orig_init(self, *args, **kwargs)

        # Reset revision to 0
        self._revision = 0

    def new_setattr(self, name: str, value: Any):
        # Allow internal variables or setup prior to _revision existence

        if name.startswith("_") or "_revision" not in self.__dict__:
            object.__setattr__(self, name, value)
            return

        has_old = hasattr(self, name)
        old_val = getattr(self, name, None)
        new_val = wrap_value(value, self)
        
        
        try:
            equal = np.all(old_val == new_val)
        except ValueError:
            equal = False
        
        if not has_old or not equal:
            if has_old:
                recursive_remove_children(self, old_val)

            object.__setattr__(self, name, new_val)
            self._notify_change()

    # Override methods on class
    cls.__init__ = new_init
    cls.__setattr__ = new_setattr

    return cls


class RevisionDataMeta(type):
    """Metaclass to enforce `@revision_dataclass` decoration."""
    def __call__(cls, *args, **kwargs):
        # Enforce check on first instantiation/usage of the class
        if not getattr(cls, "_is_revision_dataclass", False):
            raise TypeError(
                f"Class '{cls.__name__}' inherits from DataWithRevision "
                f"but is missing the @revision_dataclass decorator."
            )
        return super().__call__(*args, **kwargs)


def wrap_value(val: Any, parent: RevisionNotifierMixin) -> Any:
    """Wraps mutable structures or assigns children to parent objects."""
    if isinstance(val, RevisionNotifierMixin):
        parent._add_child(val)
        return val
    elif isinstance(val, ConfigurationMixin):
        val.subscribe(parent)
        return val
    elif isinstance(val, list):
        if isinstance(val, ObservableList):
            val.subscribe(parent)
            return val
        else:
            return ObservableList(val, subscribers = parent)
    elif isinstance(val, dict):
        if isinstance(val, ObservableDict):
            val.subscribe(parent)
            return val
        else:
            return ObservableDict(val, subscribers = parent)
    elif isinstance(val, str):
        return val        
    elif isinstance(val, Iterable) and not isinstance(val, RevisionNotifierMixin):
        for x in val:
            if isinstance(x, RevisionNotifierMixin):
                parent._add_child(x)
    return val


class SubscriptionRevisionNotifierMixin(RevisionNotifierMixin):
    """Extends RevisionNotifierMixin to increment subscriber revisions when change occurs"""

    @classmethod
    def _wrap_value(cls, val: Any, subscribers: Iterable[RevisionNotifierMixin]) -> Any:
        for subscriber in subscribers:
            val = wrap_value(val, subscriber)
        return val

    def __init__(
        self, 
        *args,
        subscribers: Optional[RevisionNotifierMixin | Iterable[RevisionNotifierMixin]] = None,
        **kwargs
        ):
        if subscribers is not None:
            if isinstance(subscribers, RevisionNotifierMixin):
                self._subscribers = [subscribers,]
            else:
                self._subscribers = list(subscribers)
        else:
            self._subscribers = []
        super().__init__(*args, **kwargs)

    @override
    def _notify_change(self, broadcast: bool = True):
        super()._notify_change()
        if broadcast:
            for subscriber in self._subscribers:
                subscriber._notify_change()

    def subscribe(self, subscriber: 'RevisionNotifierMixin | ConfigurationMixin'):
        # Addition to subscriber list occurs in _add_child
        if isinstance(subscriber, ConfigurationMixin):
            subscriber._config._add_child(self, subscribe = True)
        else:
            subscriber._add_child(self, subscribe = True)

    def unsubscribe(self, subscriber: 'RevisionNotifierMixin | ConfigurationMixin'):
        if isinstance(subscriber, ConfigurationMixin):
            search_subscriber = subscriber._config
        else:
            search_subscriber = subscriber
        for idx, x in enumerate(self._subscribers):
            if x is search_subscriber:
                # Pop the first, then stop. If multiple entries for subscriber, that's OK.
                self._subscribers.pop(idx)
                return

    def __setstate__(self, state):
        
        object.__setattr__(self, "_subscribers", state.pop("_subscribers", []))
        super().__setstate__(state)

    def __getstate__(self) -> dict:
        odict =  super().__getstate__()
        del odict['_subscribers']
        return odict


class DataWithRevision(SubscriptionRevisionNotifierMixin, serialisation.SerialiseToDictMixin, metaclass = RevisionDataMeta):
    """Base class for all revision-tracked dataclasses."""
    _constructor_class = 'DataWithRevision'
    _excluded_attributes = ('_children', '_subscribers' )

    @override
    def update(self, config: dict[str, Any] | type[T]):
        if not isinstance(config, dict):
            return super().update(config) # pyright: ignore[reportArgumentType]

        type_ = type(self)
        config = config.copy()
        classname = config.pop('class', None)
        if not classname is None:
            if self.__class__.__name__ != classname:
                raise ValueError(f'Configuration for class {classname} cannot be applied to an instance of class {self.__class__.__name__}')
        
        # Get rid of constructor class string for this instance
        config.pop('constructor_class', None)

        config = type_.unserialise_dict(config)

        # Store revision so it can be reset after property set
        r0 = config.get('_revision', None)

        # Check existing attributes to see if they can be updated
        conf_keys = config.keys()
        has_update = {}
        for k, v in vars(self).items():
            if k in conf_keys:
                if hasattr(v, 'update'):
                    has_update[k] = config[k]

        # Attributes that can be updated should not be set
        for k in has_update.keys():
            config.pop(k)

        # Attributes that can be updated should be set using setattr, for custom logic
        for v, k in config.items():
            setattr(self, v, k)

        # Updatable attributes are now set
        for k, v in has_update.items():
            getattr(self, k).update(v)

        # Set revision to as recorded
        if r0 is not None:
            self._revision = r0


    @classmethod
    @override
    def from_dict(cls, config):
        inst = cls.__new__(cls)
        inst._children = []
        inst._subscribers = []
        inst.update(config)
        return inst


class ConfigurationMixin:
    _config: DataWithRevision

    _id_prefix: str = 'cmp'
    
    uuid: str = '1'
    component_type = 'abstract'

    @classmethod
    def _make_id_regex(cls):
        return re.compile(rf'^{re.escape(cls._id_prefix)}' + r'-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$')
    
    @classmethod
    def generate_new_id(cls) -> str:
        return cls._id_prefix + '-' + str(mod_uuid.uuid4())

    @property
    def id(self) -> str:
        return self._id_prefix + '-' + self.uuid
    
    @id.setter
    def id(self, id: str) -> None:
        uid = self._make_id_regex().search(id)
        if uid is None:
            raise ValueError(f'id: {id} is not a valid {type(self)} identifier')
        uid = uid.group(1)
        self.uuid = uid

    def anonymise_ids(self):
        self.id = self.generate_new_id()

    def __init__(self, *args, **kwargs):
        self._config = self._generate_config(*args, **kwargs)

    def _generate_config(self, *args, **kwargs) -> DataWithRevision:
        """Return an implementation of DataWithRevision in order to set _config"""
        return NoConfig(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        # Called ONLY when 'name' is not found on the Component instance or class
        # ... in theory, anyway

        config = self.__dict__.get('_config')
        if config is not None and hasattr(config, name):
            return getattr(config, name)

        raise AttributeError(f'"{type(self).__name__}" object has no attribute "{name}"')

    def __setattr__(self, name: str, value: Any):
        # We end up here even if a setter has been created on the main component, so need to check
        # for that.
        if hasattr(self.__class__, name):
            att = getattr(self.__class__, name)
            if hasattr(att, 'fset'):
                return getattr(att, 'fset')(self, value)

        # Bypass custom logic for internal private attributes or initial _config setup
        if name == '_config' or name.startswith('_'):
            super().__setattr__(name, value)
            return

        config = getattr(self, '_config', None)
        # If attribute belongs to _config dataclass, set it on _config
        if config is not None and hasattr(config, name):
            setattr(config, name, value)
            return

        # Default to setting attribute directly on Component instance
        super().__setattr__(name, value)

    def __copy__(self):
        # Create a new instance without triggering __init__
        cls = self.__class__
        new_obj = cls.__new__(cls)

        # Shallow copy the instance dict to preserve attributes
        new_dict = self.__dict__.copy()

        # Create a shallow copy of _config instead of sharing the reference
        if '_config' in new_dict and new_dict['_config'] is not None:
            new_dict['_config'] = copy.copy(new_dict['_config'])

        # Update the new instance dict using object.__setattr__ / dict.update
        # to avoid triggering custom __setattr__ logic
        new_obj.__dict__.update(new_dict)

        return new_obj

    @property 
    def revision(self) -> int:
        return self._config.revision

    @revision.setter
    def revision(self, revision: int):
        """Use with caution - direct setting of the revision number"""
        self._config._revision = revision

    @property
    def modified(self) -> bool:
        return self._config.modified

    @property
    def chain_modified(self) -> bool:
        return self._config.chain_modified

    def syncronise(self):
        self._config._syncronise()

    def chain_syncronise(self):
        self._config._chain_syncronise()
    

class ObservableList(list, SubscriptionRevisionNotifierMixin):
    """List wrapper that triggers revision increment on mutation."""

    def __init__(
        self, 
        iterable = (), 
        subscribers: Optional[
            RevisionNotifierMixin 
            | ConfigurationMixin 
            | Iterable[RevisionNotifierMixin | ConfigurationMixin]
        ] = None,
        **kwargs
    ):
        if subscribers is None:
            subscribers = []
        elif isinstance(subscribers, RevisionNotifierMixin) or isinstance(subscribers, ConfigurationMixin):
            subscribers = [subscribers]

        subscribers = [
            subscriber._config if isinstance(subscriber, ConfigurationMixin) else subscriber 
            for subscriber in subscribers
        ]
        
        SubscriptionRevisionNotifierMixin.__init__(self, subscribers = subscribers)

        # Wrap to all subscribers, not just self
        wrapped = [self._wrap_value(item, [self,]) for item in iterable]
        super().__init__(wrapped)

        # Also add self as a child to all subscribers
        for subscriber in self._subscribers:
            subscriber._add_child(self, subscribe = False)

    def __setitem__(self, index, value):
        old_val = super().__getitem__(index)
        new_val = self._wrap_value(value, [self] + self._subscribers)
        if old_val != new_val:
            recursive_remove_children(self, old_val)
            super().__setitem__(index, new_val)
            self._notify_change()

    def append(self, item):
        super().append(self._wrap_value(item, [self]))
        self._notify_change()

    def extend(self, iterable: Iterable) -> None:
        wrapped = [self._wrap_value(item, [self]) for item in iterable]
        if wrapped:
            super().extend(wrapped)
            self._notify_change()

    def insert(self, index, item):
        super().insert(index, self._wrap_value(item, [self]))
        self._notify_change()

    def pop(self, index: SupportsIndex = -1):
        item = super().pop(index)
        self._notify_change()

        recursive_remove_children(self, item)
        return item

    def remove(self, value):
        try:
            idx = self.index(value)
            item = self[idx]
        except ValueError:
            # Let the standard error be raised
            super().remove(value)
            return
        recursive_remove_children(self, item)
        
        super().remove(value)
        self._notify_change()

    def clear(self):
        if len(self) > 0:
            super().clear()
            self._children = []
            self._notify_change()

    def __reduce_ex__(self, protocol):
        items = list(self)
        
        # Return constructor, positional args, state dict, and list iterator
        # Pickle will reconstruct instance -> set state -> extend items
        state = self.__getstate__()

        return (self.__class__, (), state, iter(items))


def recursive_remove_children(obj, child_item):
    if child_item is None:
        return
    if isinstance(child_item, RevisionNotifierMixin):
        obj._remove_child(child_item)
    elif isinstance(child_item, ConfigurationMixin):
        obj._remove_child(child_item._config)
    elif isinstance(child_item, str):
        return
    elif isinstance(child_item, Iterable):
        for x in child_item:
            recursive_remove_children(obj, x)


class ObservableDict(dict, SubscriptionRevisionNotifierMixin):
    """Dictionary wrapper that triggers revision increment on mutation."""

    def __init__(
        self,
        mapping = (),
        subscribers: Optional[
            RevisionNotifierMixin 
            | ConfigurationMixin 
            | Iterable[RevisionNotifierMixin | ConfigurationMixin]
        ] = None,
        **kwargs
    ):
        if subscribers is None:
            subscribers = []
        elif isinstance(subscribers, RevisionNotifierMixin) or isinstance(subscribers, ConfigurationMixin):
            subscribers = [subscribers]

        subscribers = [
            subscriber._config if isinstance(subscriber, ConfigurationMixin) else subscriber 
            for subscriber in subscribers
        ]
        
        SubscriptionRevisionNotifierMixin.__init__(self, subscribers = subscribers)
        initial = dict(mapping, **kwargs)
        
        wrapped = {k: self._wrap_value(v, [self,]) for k, v in initial.items()}
        super().__init__(wrapped)

        # Also add self as a child to all subscribers
        for subscriber in self._subscribers:
            subscriber._add_child(self, subscribe = False)

    def _safe_remove_child_value(self, val):
        """Call after deleting a value from the dict to delete the child if not referenced by another key"""
        if not isinstance(val, IMMUTABLE_TYPES):
            # NB - if old val is an immutable, it won't have been added as a child
            recursive_remove_children(self, val)
        
    def __setitem__(self, key: Any, value: Any) -> None:
        exists = key in self
        old_val = self.get(key) if exists else None
        new_val = self._wrap_value(value, [self])

        if isinstance(old_val, IMMUTABLE_TYPES):
            equal = old_val == new_val
        else:
            equal = old_val is new_val

        if not exists or not equal:
            super().__setitem__(key, new_val)
            self._notify_change()
            self._safe_remove_child_value(old_val)
            
    def __delitem__(self, key):
        old_val = self.get(key)
        
        super().__delitem__(key)
        self._safe_remove_child_value(old_val)
        
        self._notify_change()

    def update(self, *args, **kwargs):
        other = dict(*args, **kwargs)
        changed = False
        for k, v in other.items():
            wrapped_v = self._wrap_value(v, [self])
            if k not in self or self[k] != wrapped_v:
                old_val = self.get(k)
                super().__setitem__(k, wrapped_v)
                self._safe_remove_child_value(old_val)
                changed = True
        if changed:
            self._notify_change()
    
    def pop(self, key, *args):
        if key in self:
            item = super().pop(key)
            self._notify_change()
            self._safe_remove_child_value(item)
            return item
        return super().pop(key, *args)

    def clear(self):
        if len(self) > 0:
            for item in self.values():
                self._safe_remove_child_value(item)
            super().clear()
            self._children = []
            self._notify_change()

    def __reduce_ex__(self, protocol):
        dict_items = dict(self)
        
        # Return constructor, positional args, state dict, and list iterator
        # Pickle will reconstruct instance -> set state -> extend items
        state = self.__getstate__()

        # Return (cls, positional_args, state, key_value_iterator)
        return (self.__class__, (), state, None, iter(dict_items.items()))


class ObservableOrderedDict(ObservableDict, OrderedDict):
    """An ObservableDict that maintains key insertion order using OrderedDict."""

    def __init__(
        self,
        mapping = (),
        subscribers: Optional[
            RevisionNotifierMixin 
            | ConfigurationMixin 
            | Iterable[RevisionNotifierMixin | ConfigurationMixin]
        ] = None,
        **kwargs
    ):
        if subscribers is None:
            subscribers = []
        elif isinstance(subscribers, RevisionNotifierMixin) or isinstance(subscribers, ConfigurationMixin):
            subscribers = [subscribers]

        subscribers = [
            subscriber._config if isinstance(subscriber, ConfigurationMixin) else subscriber 
            for subscriber in subscribers
        ]
        
        SubscriptionRevisionNotifierMixin.__init__(self, subscribers = subscribers)
        initial = dict(mapping, **kwargs)

        OrderedDict.__init__(self)
        initial = OrderedDict(mapping, **kwargs)
        for k, v in initial.items():
            self[k] = v  # Trigger __setitem__ wrapping and subscriber setup

        self.revision = 0

        # Also add self as a child to all subscribers
        for subscriber in self._subscribers:
            subscriber._add_child(self, subscribe = False)

    def pop(self, key, *args, **kwargs):
        if key in self:
            item = super().pop(key)
            self._notify_change()
            self._safe_remove_child_value(item)
            return item
        return super().pop(key, *args, **kwargs)

class ComponentPropertyInterface(metaclass = ABCMeta):
    """All component properties should inherit this"""


class ComponentProperty(ComponentPropertyInterface):
    """Descriptor for attributes which are Components (i.e. inherit ConfigurationMixin)"""

    def __init__(self, default: Any = None, oftype: Optional[type | tuple[type, ...]] = None):
        self.default = default
        self.name = ""
        self.id = ""
        self.oftype = oftype

    def __set_name__(self, owner: type, name: str):
        self.name = f'_{name}' # Name as stored on object instance
        self.id = f'_{name}_id'

    def __get__(self, instance: Optional['ConfigurationMixin'], owner: type) -> Any:
        if instance is None:
            return self
        att = getattr(instance, self.name, None)
        if att is not None:
            return att
        if isinstance(self.default, Callable):
            default_val = self.default()
        else:
            default_val = self.default
        return getattr(instance, self.name, default_val)

    def __set__(self, instance: 'ConfigurationMixin', value: 'ConfigurationMixin'):
        if self.oftype:
            if not isinstance(value, self.oftype):
                raise TypeError(f'"{self.name}" is expected as one of {self.oftype}, is {type(value)}')
        old_val = getattr(instance, self.name, None)

        if old_val is not None and old_val._config is not value._config:
            instance._config._remove_child(old_val._config)
            setattr(instance, self.id, None)
        
        instance._config._add_child(value._config)
        instance._config._notify_change()

        setattr(instance, self.name, value)
        if isinstance(value, ConfigurationMixin):
            setattr(instance, self.id, value.id)


class ComponentListProperty(ComponentPropertyInterface):
    """Descriptor for attributes which are lists of Components (i.e. inherit ConfigurationMixin)"""
    def __init__(self, oftype: Optional[type | tuple[type, ...]] = None):
        self.name = ""
        self.oftype = oftype

    def __set_name__(self, owner: type, name: str):
        self.name = f'_{name}' # Name as stored on object instance

    def __get__(self, instance: Optional[ConfigurationMixin], owner: type) -> Any:
        if instance is None:
            return self
        att = getattr(instance, self.name, None)
        if att is None:
            att = ObservableList(subscribers = instance)
            setattr(instance, self.name, att)
        return att

    def __set__(self, instance: ConfigurationMixin, value: Iterable):
        if not isinstance(instance, ConfigurationMixin):
            raise TypeError(f'ComponentList properties should only be applied to inheritors of SerialisedConfigurationMixin (e.g. NewsegsComponents), is applied to {type(instance)}')
        
        old_val = getattr(instance, self.name, None)
        is_wrapped = False
        if not isinstance(value, ObservableList):    
            value = ObservableList(value, instance)
            is_wrapped = True
            
        if old_val and not old_val == value:
            recursive_remove_children(instance._config, old_val)
            if not is_wrapped:
                if isinstance(value, ObservableList):
                    subscribers = [instance._config]
                    value._wrap_value(value, subscribers)
                else:
                    value = ObservableList(value, instance)

            instance._config._notify_change()

        setattr(instance, self.name, value)


class ComponentOrderedDictProperty(ComponentPropertyInterface):
    """Descriptor for attributes which are ordered dictionaries of Components (i.e. inherit ConfigurationMixin, e.g. Variables)"""
    def __init__(self, oftype: Optional[type | tuple[type, ...]] = None):
        self.name = ""
        self.oftype = oftype

    def __set_name__(self, owner: type, name: str):
        self.name = f'_{name}' # Name as stored on object instance

    def __get__(self, instance: Optional['ConfigurationMixin'], owner: type) -> Any:
        if instance is None:
            return self
        att = getattr(instance, self.name, None)
        if att is None:
            att = ObservableOrderedDict(subscribers = [instance])
            setattr(instance, self.name, att)
        return att

    def __set__(self, instance: ConfigurationMixin, value: Mapping):
        if not isinstance(instance, ConfigurationMixin):
            raise TypeError(f'ComponentOrderedDict properties should only be applied to inheritors of SerialisedConfigurationMixin (e.g. NewsegsComponents), is applied to {type(instance)}')

        old_val = getattr(instance, self.name, None)
        is_wrapped = False
        if not isinstance(value, ObservableOrderedDict):
            value = ObservableOrderedDict(value, instance)
            is_wrapped = True

        if old_val and not old_val == value:
            instance._config._remove_child(old_val)
            if not is_wrapped:
                value = ObservableOrderedDict(value, instance)
            instance._config._notify_change()

        setattr(instance, self.name, value)


@revision_dataclass
class NoConfig(DataWithRevision):
    """A placeholder configuration object"""
    ...

