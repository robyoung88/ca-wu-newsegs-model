"""
Classes and functions to enable automatic tracking of changes in members
"""
from dataclasses import dataclass, fields
from typing import Any, Iterable, Optional, SupportsIndex, Type, TypeVar, dataclass_transform

class RevisionNotifierMixin:
    """Handles part-child notifications and revision counts"""
    def __init__(self, parent: Optional['RevisionNotifierMixin'] = None):
        self._parent = parent
        self._revision = 0

    def _set_parent(self, parent: Optional['RevisionNotifierMixin']):
        self._parent = parent

    def _notify_change(self):
        self._revision += 1
        if self._parent is not None:
            self._parent._notify_change()

    @property
    def revision(self) -> int:
        return self._revision


def _wrap_value(val: Any, parent: RevisionNotifierMixin) -> Any:
    """Wraps mutable structures or assigns parents to child objects."""
    if isinstance(val, RevisionNotifierMixin):
        val._set_parent(parent)
        return val
    elif isinstance(val, list) and not isinstance(val, ObservableList):
        return ObservableList(val, parent = parent)
    elif isinstance(val, dict) and not isinstance(val, ObservableDict):
        return ObservableDict(val, parent = parent)
    return val


class ObservableList(list, RevisionNotifierMixin):
    """List wrapper that triggers revision increment on mutation."""

    def __init__(self, iterable = (), parent: Optional[RevisionNotifierMixin] = None):
        RevisionNotifierMixin.__init__(self, parent)
        wrapped = [_wrap_value(item, self) for item in iterable]
        super().__init__(wrapped)

    def __setitem__(self, index, value):
        old_val = super().__getitem__(index)
        new_val = _wrap_value(value, self)
        if old_val != new_val:
            super().__setitem__(index, new_val)
            self._notify_change()

    def append(self, item):
        super().append(_wrap_value(item, self))
        self._notify_change()

    def extend(self, iterable: Iterable) -> None:
        wrapped = [_wrap_value(item, self) for item in iterable]
        if wrapped:
            super().extend(wrapped)
            self._notify_change()

    def insert(self, index, item):
        super().insert(index, _wrap_value(item, self))
        self._notify_change()

    def pop(self, index: SupportsIndex = -1):
        item = super().pop(index)
        self._notify_change()
        return item

    def remove(self, value):
        super().remove(value)
        self._notify_change()

    def clear(self):
        if len(self) > 0:
            super().clear()
            self._notify_change()


class ObservableDict(dict, RevisionNotifierMixin):
    """Dictionary wrapper that triggers revision increment on mutation."""

    def __init__(
        self,
        mapping = (),
        parent: Optional[RevisionNotifierMixin] = None,
        **kwargs
    ):
        RevisionNotifierMixin.__init__(self, parent)
        initial = dict(mapping, **kwargs)
        wrapped = {k: _wrap_value(v, self) for k, v in initial.items()}
        super().__init__(wrapped)

    def __setitem__(self, key: Any, value: Any) -> None:
        exists = key in self
        old_val = self.get(key) if exists else None
        new_val = _wrap_value(value, self)

        if not exists or old_val != new_val:
            super().__setitem__(key, new_val)
            self._notify_change()

    def __delitem__(self, key):
        super().__delitem__(key)
        self._notify_change()

    def update(self, *args, **kwargs):
        other = dict(*args, **kwargs)
        changed = False
        for k, v in other.items():
            wrapped_v = _wrap_value(v, self)
            if k not in self or self[k] != wrapped_v:
                super().__setitem__(k, wrapped_v)
                changed = True
        if changed:
            self._notify_change()

    def pop(self, key, *args):
        if key in self:
            item = super().pop(key)
            self._notify_change()
            return item
        return super().pop(key, *args)

    def clear(self):
        if len(self) > 0:
            super().clear()
            self._notify_change()


# class DataWithRevision(RevisionNotifierMixin):
#     """Base class/decorator target for reactive dataclasses."""
#     def __init_subclass__(cls, **kwargs) -> None:
#         super().__init_subclass__(**kwargs)

#         # Intercept original generated __init__
#         orig_init = cls.__init__
#         def __init__(self, *args, **kwargs):
#             # Initialise revision state BEFORE dataclass assigns attributes
#             RevisionNotifierMixin.__init__(self)
#             # Run standard dataclass field assignments
#             orig_init(self, *args, **kwargs)
#             # Wrap initial fields
#             for f in fields(self):
#                 val = getattr(self, f.name)
#                 object.__setattr__(self, f.name, _wrap_value(val, self))

#         cls.__init__ = __init__

#     #def __init__(self, parent: Optional[RevisionNotifierMixin] = None):
#     #    super().__init__(parent)

#     #def __post_init__(self):
#     #    # Convert initial plain lists/dicts/children to observable variants
#     #    for f in fields(self): # pyright: ignore[reportArgumentType]
#     #        val  = getattr(self, f.name)
#     #        wrapped = _wrap_value(val, self)
#     #        super().__setattr__(f.name, wrapped)

#     def __setattr__(self, name: str, value: Any) -> None:
#         # Allow internal private attribute assignment without triggering checks
#         if name.startswith('_'): # or not '_revision' in self.__dict__: # A per-set check, replaced with the init_subclass
#             super().__setattr__(name, value)
#             return

#         has_old = hasattr(self, name)
#         old_val = getattr(self, name, None)
#         new_val = _wrap_value(value, self)

#         # Reassignment without equality triggers a revision increment
#         if not has_old or old_val != new_val:
#             # Clear parent link from removed child
#             if isinstance(old_val, RevisionNotifierMixin):
#                 old_val._set_parent(None)

#             super().__setattr__(name, new_val)
#             self._notify_change()

class DataWithRevision(RevisionNotifierMixin):
    """Base class for all revision-tracked dataclasses."""
    pass

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
            object.__setattr__(self, f.name, _wrap_value(val, self))

        # Reset revision to 0
        self._revision = 0

    def new_setattr(self, name: str, value: Any):
        # Allow internal variables or setup prior to _revision existence
        if name.startswith("_") or "_revision" not in self.__dict__:
            object.__setattr__(self, name, value)
            return

        has_old = hasattr(self, name)
        old_val = getattr(self, name, None)
        new_val = _wrap_value(value, self)

        if not has_old or old_val != new_val:
            if isinstance(old_val, RevisionNotifierMixin):
                old_val._set_parent(None)

            object.__setattr__(self, name, new_val)
            self._notify_change()

    # Override methods on class
    cls.__init__ = new_init
    cls.__setattr__ = new_setattr

    return cls
