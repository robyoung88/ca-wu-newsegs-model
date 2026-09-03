"""
Classes and functions to enable automatic tracking of changes in members
"""
from dataclasses import dataclass, fields, asdict
from typing import Any, Collection, Iterable, Optional, SupportsIndex, Type, TypeVar, dataclass_transform, override

import numpy as np

from newsegsmodelframework.core import serialisation

__all__ = [
    'NoConfig',
]

class RevisionNotifierMixin:
    """Handles part-child notifications and revision counts"""
    def __init__(
        self, 
        children: Optional[Collection['RevisionNotifierMixin']] = None
    ):
        self._last_syncronised = 0
        self._revision = 0
        if children:
            self._children = [x for x in children]
        else:
            self._children = []

    def _add_child(self, child: 'RevisionNotifierMixin'):
        if child is self:
            raise ValueError('Circular reference - cannot add self as child.')
        self._children.append(child)

    def _remove_child(self, child: 'RevisionNotifierMixin'):
        # Don't use remove, need to check for instance equality
        for idx, inlist in enumerate(self._children):
            if inlist is child:
                self._children.pop(idx)
                return

    def _notify_change(self):
        self._revision += 1

    def _syncronise(self):
        """Use after saving status (to database)"""
        self._last_syncronised = self._revision

    def _chain_syncronise(self):
        self._syncronise()
        for child in self._children:
            child._chain_syncronise()

    @property
    def modified(self) -> bool:
        return self._last_syncronised != self._revision

    @property
    def chain_modified(self) -> bool:
        return (
            self.modified 
            or any((child.chain_modified for child in self._children))
        )

    @property
    def revision(self) -> int:
        return self._revision


def wrap_value(val: Any, parent: RevisionNotifierMixin) -> Any:
    """Wraps mutable structures or assigns children to parent objects."""
    if isinstance(val, RevisionNotifierMixin):
        parent._add_child(val)
        return val
    elif isinstance(val, list) and not isinstance(val, ObservableList):
        return ObservableList(val, parent = parent)
    elif isinstance(val, dict) and not isinstance(val, ObservableDict):
        return ObservableDict(val, parent = parent)
    elif isinstance(val, Iterable) and not isinstance(val, RevisionNotifierMixin):
        for x in val:
            if isinstance(x, RevisionNotifierMixin):
                parent._add_child(x)
    return val


class ObservableList(list, RevisionNotifierMixin):
    """List wrapper that triggers revision increment on mutation."""

    @classmethod
    def _wrap_value(cls, val: Any, parent: RevisionNotifierMixin) -> Any:
        return wrap_value(val, parent)

    def __init__(self, iterable = (), parent: Optional[RevisionNotifierMixin] = None):
        RevisionNotifierMixin.__init__(self)
        wrapped = [self._wrap_value(item, self) for item in iterable]
        super().__init__(wrapped)
        if parent:
            parent._add_child(self)

    def __setitem__(self, index, value):
        old_val = super().__getitem__(index)
        new_val = self._wrap_value(value, self)
        if old_val != new_val:
            if isinstance(old_val, RevisionNotifierMixin):
                self._remove_child(old_val)
            elif isinstance(old_val, Iterable):
                for x in old_val:
                    if isinstance(x, RevisionNotifierMixin):
                        self._remove_child(x)
            super().__setitem__(index, new_val)
            self._notify_change()

    def append(self, item):
        super().append(self._wrap_value(item, self))
        self._notify_change()

    def extend(self, iterable: Iterable) -> None:
        wrapped = [self._wrap_value(item, self) for item in iterable]
        if wrapped:
            super().extend(wrapped)
            self._notify_change()

    def insert(self, index, item):
        super().insert(index, self._wrap_value(item, self))
        self._notify_change()

    def pop(self, index: SupportsIndex = -1):
        item = super().pop(index)
        self._notify_change()
        if isinstance(item, RevisionNotifierMixin):
            self._remove_child(item)
        return item

    def remove(self, value):
        try:
            idx = self.index(value)
            item = self[idx]
        except ValueError:
            # Let the standard error be raised
            super().remove(value)
            return

        if isinstance(item, RevisionNotifierMixin):
            self._remove_child(item)
        
        super().remove(value)
        self._notify_change()

    def clear(self):
        if len(self) > 0:
            super().clear()
            self._children = []
            self._notify_change()


class ObservableDict(dict, RevisionNotifierMixin):
    """Dictionary wrapper that triggers revision increment on mutation."""

    def __init__(
        self,
        mapping = (),
        parent: Optional[RevisionNotifierMixin] = None,
        **kwargs
    ):
        RevisionNotifierMixin.__init__(self)
        initial = dict(mapping, **kwargs)
        wrapped = {k: wrap_value(v, self) for k, v in initial.items()}
        super().__init__(wrapped)
        if parent:
            parent._add_child(self)

    def __setitem__(self, key: Any, value: Any) -> None:
        exists = key in self
        old_val = self.get(key) if exists else None
        new_val = wrap_value(value, self)

        if not exists or old_val != new_val:
            super().__setitem__(key, new_val)
            self._notify_change()
            if (
                old_val is not None
                and isinstance(old_val, RevisionNotifierMixin)
            ):
                self._remove_child(old_val)
            
    def __delitem__(self, key):
        old_val = self.get(key)
        if (
            old_val is not None
            and isinstance(old_val, RevisionNotifierMixin)
        ):
            self._remove_child(old_val)
        super().__delitem__(key)
        self._notify_change()

    def update(self, *args, **kwargs):
        other = dict(*args, **kwargs)
        changed = False
        for k, v in other.items():
            wrapped_v = wrap_value(v, self)
            if k not in self or self[k] != wrapped_v:
                old_val = self.get(k)
                if (
                    old_val is not None
                    and isinstance(old_val, RevisionNotifierMixin)
                ):
                    self._remove_child(old_val)
                super().__setitem__(k, wrapped_v)
                changed = True
        if changed:
            self._notify_change()
    
    def pop(self, key, *args):
        if key in self:
            item = super().pop(key)
            self._notify_change()
            if isinstance(item, RevisionNotifierMixin):
                self._remove_child(item)
            return item
        return super().pop(key, *args)

    def clear(self):
        if len(self) > 0:
            super().clear()
            self._children = []
            self._notify_change()


class DataWithRevision(RevisionNotifierMixin, serialisation.SerialiseToDictMixin):
    """Base class for all revision-tracked dataclasses."""
    _constructor_class = 'DataWithRevision'
    _excluded_attributes = ('_children', )

    @classmethod
    @override
    def from_dict(cls, config):
        inst = super().from_dict(config)
        inst._children = []
        return inst


T = TypeVar('T')

@dataclass_transform()
def revision_dataclass(cls: Type[T]) -> Type[T]:
    """Class decorator applying dataclass setup and intercepting attribute changes."""
    
    # 1. Transform into a dataclass first
    cls = dataclass(cls)

    # Capture the dataclass-generated __init__
    orig_init = cls.__init__

    def new_init(self, *args, **kwargs):
        # Initialize internal revision tracking before dataclass assigns fields
        RevisionNotifierMixin.__init__(self)

        # Run standard dataclass initializer
        orig_init(self, *args, **kwargs)

        # Wrap lists, dicts, and children initially assigned
        for f in fields(self):
            val = getattr(self, f.name)
            object.__setattr__(self, f.name, wrap_value(val, self))

        # Reset revision to 0
        self._revision = 0

    def new_setattr(self, name: str, value: Any):
        # Allow internal variables or setup prior to _revision existence
        #print(f'set {name} to {value}')
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
            if isinstance(old_val, RevisionNotifierMixin):
                self._remove_child(old_val)

            object.__setattr__(self, name, new_val)
            self._notify_change()

    # Override methods on class
    cls.__init__ = new_init
    cls.__setattr__ = new_setattr

    return cls

@revision_dataclass
class NoConfig(DataWithRevision):
    """A placeholder configuration object"""
    pass

class ConfigurationMixin:
    _config: DataWithRevision

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

    @property 
    def revision(self) -> int:
        return self._config.revision

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
