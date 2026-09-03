"""
A superclass defining behaviour required of multiple model components.

Components include:
- NewsegsModel
- NewsegsFinance
- Variable
- NewsegsModule

These components require the following common behaviour:
- A means to uniquely identify an instance
- A means to serialise and unserialise and instance
- A means to check of the configuration has been altered without synchronisation
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import copy
import re
import time
from typing import Any, Callable, Iterable, Optional, Sequence, SupportsIndex, Type, override
import uuid as mod_uuid

from newsegsmodelframework.core import serialisation, SerialisedConfigurationMixin
from newsegsmodelframework.core import find_constructor
from newsegsmodelframework.core.trackeddata import ConfigurationMixin, DataWithRevision, ObservableList, RevisionNotifierMixin, revision_dataclass
from newsegsmodelframework.core.trackeddata import wrap_value as default_wrap_value
from newsegsmodelframework.util import classfuncs

__all__ = [
    'NewsegsComponent', 'RunnableNewsegsComponent', 'TableConfigNewsegsComponent',
    'DataWithRevision'
]

class ComponentProperty:
    """Descriptor for attributes which are Components"""

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

        if old_val is not None and old_val is not value._config:
            instance._config._remove_child(old_val)
            setattr(instance, self.id, None)
        
        instance._config._add_child(value._config)
        instance._config._notify_change()

        setattr(instance, self.name, value)
        if isinstance(value, NewsegsComponent):
            setattr(instance, self.id, value.id)


def wrap_value(val: Any, parent: RevisionNotifierMixin) -> Any:
    if isinstance(val, NewsegsComponent):
        parent._add_child(val._config)
        return val
    return default_wrap_value(val, parent)


class ObservableComponentList(ObservableList):
    @classmethod
    @override
    def _wrap_value(cls, val: Any, parent: RevisionNotifierMixin) -> Any:
        return wrap_value(val, parent)

    def __init__(self, iterable = (), parent: Optional['RevisionNotifierMixin | NewsegsComponent'] = None):
        if parent:
            if isinstance(parent, NewsegsComponent):
                super().__init__(iterable, parent = parent._config)
            else:
                super().__init__(iterable, parent)
        else:
            super().__init__(iterable)

    def __setitem__(self, index, value):
        old_val = super().__getitem__(index)
        new_val = value
        if isinstance(new_val, NewsegsComponent):
            new_val._config = self._wrap_value(new_val._config, self)
        else:
            new_val = wrap_value(new_val, self)
        if old_val != new_val:
            if isinstance(old_val, NewsegsComponent):
                self._remove_child(old_val._config)
            if isinstance(old_val, RevisionNotifierMixin):
                self._remove_child(old_val)
            elif isinstance(old_val, Iterable):
                for x in old_val:
                    if isinstance(x, RevisionNotifierMixin):
                        self._remove_child(x)

            list.__setitem__(self, index, new_val)
            self._notify_change()

    def pop(self, index: SupportsIndex = -1):
        item = super().pop(index)
        if isinstance(item, NewsegsComponent):
            self._remove_child(item._config)

        # Notify is handled by ObservableList
        return item

    def remove(self, value):
        try:
            idx = self.index(value)
            item = self[idx]
        except ValueError:
            # Let the standard error be raised
            list.remove(self, value)
            return

        if isinstance(item, RevisionNotifierMixin):
            self._remove_child(item)
        elif isinstance(item, NewsegsComponent):
            self._remove_child(item._config)
        
        list.remove(self, value)
        self._notify_change()


class ComponentListProperty:
    """Descriptor for attributes which are lists of Components"""
    def __init__(self, oftype: Optional[type | tuple[type, ...]] = None):
        self.name = ""
        self.oftype = oftype

    def __set_name__(self, owner: type, name: str):
        self.name = f'_{name}' # Name as stored on object instance

    def __get__(self, instance: Optional['ConfigurationMixin'], owner: type) -> Any:
        if instance is None:
            return self
        att = getattr(instance, self.name, [])
        return att

    def __set__(self, instance: 'ConfigurationMixin', value: Iterable):
        if not isinstance(instance, NewsegsComponent):
            raise TypeError(f'Component list properties should only be applied to NewsegsComponents, is applied to {type(instance)}')
        
        old_val = getattr(instance, self.name, None)
        is_wrapped = False
        if not isinstance(value, ObservableComponentList):    
            value = ObservableComponentList(value, instance)
            is_wrapped = True
            
        if old_val and not old_val == value:
            instance._config._remove_child(old_val)
            if not is_wrapped:
                value = ObservableComponentList(value, instance)

            instance._config._notify_change()

        setattr(instance, self.name, value)


class ObservableComponentOrderedDict(OrderedDict, RevisionNotifierMixin):
    """Ordered dictionary wrapper that triggers a revision increment on mutation of child components."""
    @classmethod
    def _wrap_value(cls, val: Any, parent: RevisionNotifierMixin) -> Any:
        return wrap_value(val, parent)

    def __init__(
        self,
        mapping = (),
        parent: Optional['RevisionNotifierMixin | NewsegsComponent'] = None,
        **kwargs
    ):
        RevisionNotifierMixin.__init__(self)
        initial = OrderedDict(mapping, **kwargs)
        wrapped = {k: self._wrap_value(v, self) for k, v in initial.items()}
        super().__init__(wrapped)
        if isinstance(parent, NewsegsComponent):
            parent._config._add_child(self)
        elif parent:
            parent._add_child(self)

    def __setitem__(self, key: Any, value: Any) -> None:
        exists = key in self
        old_val = self.get(key) if exists else None
        new_val = self._wrap_value(value, self)

        if not exists or old_val != new_val:
            super().__setitem__(key, new_val)
            self._notify_change()
            if old_val is not None:
                if isinstance(old_val, NewsegsComponent):
                    self._remove_child(old_val._config)
                elif isinstance(old_val, RevisionNotifierMixin):
                    self._remove_child(old_val)
            
    def __delitem__(self, key):
        old_val = self.get(key)
        if  old_val is not None:
            if isinstance(old_val, NewsegsComponent):
                self._remove_child(old_val._config)
            elif isinstance(old_val, RevisionNotifierMixin):
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
                if old_val is not None:
                    if isinstance(old_val, NewsegsComponent):
                        self._remove_child(old_val._config)
                    elif isinstance(old_val, RevisionNotifierMixin):
                        self._remove_child(old_val)
                
                super().__setitem__(k, wrapped_v)
                changed = True
        if changed:
            self._notify_change()
    
    def pop(self, key, *args, **kwargs):
        if key in self:
            item = super().pop(key)
            self._notify_change()
            if isinstance(item, NewsegsComponent):
                self._remove_child(item._config)
            elif isinstance(item, RevisionNotifierMixin):
                self._remove_child(item)
            return item
        return super().pop(key, *args, **kwargs)

    def popitem(self, last: bool = True) -> tuple:
        item = super().popitem(last)
        self._notify_change()
        if isinstance(item, NewsegsComponent):
            self._remove_child(item._config)
        elif isinstance(item, RevisionNotifierMixin):
            self._remove_child(item)
        return item

    def clear(self):
        if len(self) > 0:
            super().clear()
            self._children = []
            self._notify_change()


class NewsegsComponent(
    SerialisedConfigurationMixin,
    metaclass = ABCMeta
):
    """
    Base class of a NewSEGS (meta)model component.
    
    Provides common functionality for model components including unique identification,
    serialization/deserialization, and configuration synchronization checks.
    """
    
    _name: str = 'Model component'
    _version: str = '0.0.1'
    _id_prefix: str = 'cmp'
    _revision: int = 0

    uuid: str = '1'
    component_type = 'abstract'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'NewsegsComponent'

    @classmethod
    def _make_id_regex(cls):
        return re.compile(rf'^{re.escape(cls._id_prefix)}' + r'-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$')
    
    @classmethod
    def generate_new_id(cls) -> str:
        return cls._id_prefix + '-' + str(mod_uuid.uuid4())

    def __init__(self, *args, name: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs) 
        self.uuid = str(mod_uuid.uuid4())
        if name is not None:
            self.name = name
            
    @property
    def name(self) -> str:
        return self._name
    
    @name.setter
    def name(self, name: str) -> None:
        self._name = name

    @property
    def version(self) -> str:
        return self._version

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

    @property
    def config(self) -> DataWithRevision:
        return self._config

    @override
    def update(self, config: dict[str, Any] | type[serialisation.T]):
        type_ = type(self)
        if not isinstance(config, dict):
            vars(self).update(copy.copy(vars(config)))
            return
        
        config = config.copy()
        
        # We want to be able to accept property updates, but need to strip
        # them out of the update dict and apply them after other updates
        property_updates = {}
        for k in config.keys():
            if hasattr(type_, k):
                prop = getattr(type_, k)
                if hasattr(prop, 'fset') and getattr(prop, 'fset') is not None:
                    v = config.get(k)
                    if isinstance(v, dict):
                        child_cc = v.get('constructor_class', None)
                        child_classname = v.get('class', None)
                        if child_cc is not None and child_classname is not None:
                            v = find_constructor(child_cc, child_classname)(v)
                        else:
                            v = type_.unserialise_dict(v.copy())
                    elif not isinstance(v, str) and isinstance (v, Sequence):
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
                                        templist[i] = type_.unserialise_dict(childv)
                            v = type(v)(templist) # pyright: ignore[reportCallIssue]
                    property_updates[k] = v

        for k in property_updates.keys():
            config.pop(k)
        
        super().update(config)
        # Not all properties with a valid fset; if so, we are going to overwrite it
        for k, v in property_updates.items():
            try:
                prop = getattr(type_, k)
                getattr(prop, 'fset')(self, v)
            except AttributeError:
                setattr(self, k, v)

    @classmethod
    @override
    def from_dict(cls, config):
        config = config.copy()
        #cfg = config.pop('_config', None)
        inst = cls.__new__(cls)
        inst._config = inst._generate_config()
        inst.update(config)
        #if cfg:
        #    for k, v in cfg.items():
        #        setattr(inst, k, v)
        return inst

    @property
    def dirty(self):
        return self.chain_modified
    

class RunnableNewsegsComponent(NewsegsComponent):
    last_run: float = 0.0

    def run(self) -> Any:
        """
        Compute all submodules given current configuration

        Results are accessed via the model properties.

        Returns a hash representing the model and datetime of run completion.
        """
        self.last_run = time.time()
        return hash(self)


class TableConfigNewsegsComponent(NewsegsComponent):
    """A reference config object to anchor table results."""
    component_type = 'table'
