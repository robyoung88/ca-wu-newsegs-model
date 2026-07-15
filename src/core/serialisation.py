"""
Classes and mixins related to serialising and unserialising objects
"""
from __future__ import annotations

import copy
from datetime import tzinfo, datetime
from typing import Any, Protocol, Sequence, Type, TypeAlias, TypeVar

import pandas as pd

from core import find_constructor

TimeZoneScalar: TypeAlias = str|tzinfo

class SerialiseToDictProtocol(Protocol):
    def to_dict(self) -> dict[str, Any]: ...
    def update(self, config: dict[str, Any]): ...

T = TypeVar('T', bound = SerialiseToDictProtocol)

class SerialiseToDictMixin:
    _constructor_class: str
    _excluded_attributes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
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
            elif isinstance(value, TimeZoneScalar):
                return str(value)
            elif isinstance(value, datetime):
                return datetime_to_dict(value)
            else:
                return value
        else:
            return value
        
    def update(self, config: dict[str, Any] | Type[T]):
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
        inst = cls.__new__(cls)
        inst.update(config)
        return inst
    
    @classmethod
    def unserialise_dict(
        cls,
        config: dict[str, Any]
    ) -> dict[str, Any]:
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
