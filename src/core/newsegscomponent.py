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

from abc import ABCMeta
import copy
import re
from typing import Any, Sequence, Type, override
import uuid as mod_uuid

from core import serialisation
from core import find_constructor
from util import classfuncs

class NewsegsComponent(
    serialisation.SerialiseToDictMixin,
    metaclass = ABCMeta
):
    """
    Abstract base class of a NewSEGS model component
    """
    
    _name: str = 'Model component'
    _version: str = '0.0.1'
    _id_prefix: str = 'cmp'

    uuid: str = '1'

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'NewsegsComponent'
    
    @classmethod
    def _make_id_regex(cls):
        return re.compile(rf'^{re.escape(cls._id_prefix)}-([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})$')

    def __init__(self, *args, **kwargs):
        self.uuid = str(mod_uuid.uuid4())
        
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
        type_ = type(self)
        for k in config.keys():
            if hasattr(type_, k):
                prop = getattr(type_, k)
                if hasattr(prop, 'fset') and getattr(prop, 'fset') is not None:
                    v = config.get(k)
                    if isinstance(v, dict):
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
    
    # def verify_config_dict(
    #     self,
    #     config: dict[str, Any]
    # ):
    #     config_cls = config.pop('class', None)
    #     if config_cls is not None and config_cls != classfuncs.get_class(self):
    #         raise ValueError(f'Config class inconsistent: config {config_cls} updating {classfuncs.get_class(self)}')
        
    #     config_version = config.pop('version', None)
    #     if config_version is not None and config_version != self.version:
    #         raise ValueError(f'Config has inconsistent model version {config_version}  vs {self.version}')
        
    # def _apply_dict(
    #     self,
    #     config: dict[str, Any]
    # ):
    #     vars(self).update(config)
    
    # def update_from_dict(
    #     self,
    #     config: dict[str, Any]
    # ) -> None:
    #     """
    #     Update configuration using a dictionary.

    #     In the default implementation, will go through each key in the dict.
    #     If there is an attribute with an fset attribute, then assume it is a
    #     read-write property and update it via the fset. Otherwise, set the
    #     attribute directly.
    #     """
    #     config = copy.copy(config)
    #     self.verify_config_dict(config)
    #     self._apply_dict(config)

    # def update(
    #     self,
    #     config: dict[str, Any] | NewsegsComponent,
    #     force: bool = False
    # ):
    #     """
    #     Update configuration using a dictionary or another instance.

    #     Throws TypeError if the configuration is not compatible; e.g. if the
    #     dict is for a different model or the other model instance is not of
    #     the same kind.

    #     If the dictionary has no 'class' key, it will be used anyway.
    #     """
    #     if isinstance(config, dict):
    #         self.update_from_dict(config)
    #     else:
    #         if not isinstance(config, type(self)):
    #             if not force:
    #                 raise TypeError(f'Update model is of mismatched class: {type(config)} vs {type(self)}')
    #         vars(self).update(copy.deepcopy(vars(config)))

    # @classmethod
    # def from_dict(
    #     cls: Type[NewsegsComponent],
    #     config: dict[str, Any]
    # ) -> NewsegsComponent:
    #     """
    #     An instance of the component configured per a dictionary
    #     """
    #     inst = cls.__new__(cls)
    #     inst.update(config)
    #     return(inst)
