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
import copy
import re
import time
from typing import Any, Optional, Sequence, Type, override
import uuid as mod_uuid

from newsegsmodelframework.core import serialisation
from newsegsmodelframework.core import find_constructor
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass
from newsegsmodelframework.util import classfuncs

__all__ = [
    'NewsegsComponent', 'RunnableNewsegsComponent', 'TableConfigNewsegsComponent',
    'DataWithRevision', 'NoConfig',
]

class ComponentProperty:
    """Descriptor for attributes which are Components"""

    def __init__(self, default: Any = None):
        self.default = default
        self.name = ""
        self.id = ""

    def __set_name__(self, owner: type, name: str):
        self.name = f'_{name}' # Name as stored on object instance
        self.id = f'_{name}_id'

    def __get__(self, instance: Optional['NewsegsComponent'], owner: type) -> Any:
        if instance is None:
            return self
        return getattr(instance, self.name, None)

    def __set__(self, instance: 'NewsegsComponent', value: 'NewsegsComponent'):
        old_val = getattr(instance, self.name, None)

        if old_val is not None and old_val is not value:
            instance._config._remove_child(old_val)
        
        instance._config._add_child(value._config)
        instance._config._notify_change()

        setattr(instance, self.name, value)
        setattr(instance, self.id, value.id)


@revision_dataclass
class NoConfig(DataWithRevision):
    """A placeholder configuration object"""
    pass


class NewsegsComponent(
    serialisation.SerialiseToDictMixin,
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

    _config: DataWithRevision
    
    @classmethod
    def _make_id_regex(cls):
        return re.compile(rf'^{re.escape(cls._id_prefix)}' + r'-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$')
    
    @classmethod
    def generate_new_id(cls) -> str:
        return cls._id_prefix + '-' + str(mod_uuid.uuid4())

    def _generate_config(self, *args, **kwargs) -> DataWithRevision:
        """Return an implementation of DataWithRevision in order to set _config"""
        return NoConfig(*args, **kwargs)

    def __init__(self, *args, name: Optional[str] = None, **kwargs):
        self.uuid = str(mod_uuid.uuid4())
        if name is not None:
            self.name = name
        self._config = self._generate_config(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        # Called ONLY when 'name' is not found on the Component instance or class
        config = self.__dict__.get('_config')
        if config is not None and hasattr(config, name):
            return getattr(config, name)

        raise AttributeError(f'"{type(self).__name__}" object has no attribute "{name}"')

    def __setattr__(self, name: str, value: Any):
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
