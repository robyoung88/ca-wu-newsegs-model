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
import json
import re
import time
from typing import Any, Optional, Sequence, overload, override
import uuid as mod_uuid

from useful_types import SequenceNotStr

from newsegsmodelframework.core import serialisation, SerialisedConfigurationMixin
from newsegsmodelframework.core import find_constructor
from newsegsmodelframework.core.trackeddata import ComponentPropertyInterface, DataWithRevision
from newsegsmodelframework.util import jsonfuncs

__all__ = [
    'NewsegsComponent', 'RunnableNewsegsComponent', 'TableConfigNewsegsComponent',
    'DataWithRevision'
]


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
    
    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'NewsegsComponent'

    _component_ids: dict[str, str]
    """IDs of subcomponents for reconstruction of component."""

    # NB - all ID generating attributes are now in ConfigurationMixin   

    def __init__(self, *args, name: Optional[str] = None, **kwargs):
        super().__init__(*args, **kwargs) 
        self.uuid = str(mod_uuid.uuid4())
        if name is not None:
            self.name = name
        self._component_ids = {}
            
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
    def config(self) -> DataWithRevision:
        return self._config

    @override
    def to_dict(self) -> dict[str, Any]:
        self.update_component_id_dict()
        return super().to_dict()

    def to_dict_repr(self) -> dict[str, Any]:
        """A dictionary reproduction of the component including child components (not references)."""
        odict = self.to_dict()
        att_names = self.get_component_attributes()
        for att in att_names:
            odict[att] = self._repr_represent(getattr(self, att))
            attunder = '_' + att
            if attunder in odict:
                del odict[attunder]
        return odict

    def json_dumps_repr(self) -> str:
        return json.dumps(self.to_dict_repr(), cls = jsonfuncs.NumpyEncoder)
    
    def _repr_represent(self, value):
        if isinstance(value, object) and hasattr(value, 'to_dict_repr'):
                return value.to_dict_repr() # pyright: ignore[reportAttributeAccessIssue]
        return self._represent(value)

    @override
    def anonymise_ids(self):
        super().anonymise_ids()
        for comp in self.get_components():
            if comp is not None:
                comp.id = comp.generate_new_id()

    def get_component_attributes(self) -> tuple['str', ...]:
        """A tuple of all the attributes of the object that are themselves NewsegsComponents"""
        return ()

    def get_components(self) -> tuple['NewsegsComponent', ...]:
        """A tuple of all subcomponents that would require saving to store and reattaching after deserialisation."""
        return tuple(getattr(self, nm) for nm in self.get_component_attributes())

    def update_component_id_dict(self):
        """Update ._component_ids prior to serialisation."""
        self._component_ids.clear()
        att_names = self.get_component_attributes()
        for att in att_names:
            comp = getattr(self, att)
            if isinstance(comp, NewsegsComponent):
                self._component_ids[att] = comp.id

    def reattach_components(
        self,
        component_provider: NewsegsComponentProviderInterface
    ):
        """Using the component_provider, find all components for reattachment."""
        r0 = self.revision
        for att_name, comp_id in self._component_ids.items():
            comp = component_provider.get_component(comp_id)
            setattr(self, att_name, comp)
        # Ensure that revision is not incremented due to reattachment
        self.revision = r0

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


class NewsegsComponentProviderInterface(metaclass = ABCMeta):
    """Interface for providing components when given their ids."""

    @overload
    @abstractmethod
    def get_component(self, component_id: str) -> NewsegsComponent:
        ...

    @overload
    @abstractmethod
    def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsComponent]:
        ...

    @abstractmethod
    def get_component(self, component_id: str | SequenceNotStr[str]) -> NewsegsComponent | SequenceNotStr[NewsegsComponent]:
        ...

    @abstractmethod
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsComponent:
        ...

    @abstractmethod
    def add_component(self, component: NewsegsComponent) -> str:
        ...

    @abstractmethod
    def get_default_component(self, component_type: str, index: int = -1) -> NewsegsComponent:
        ...

    @abstractmethod
    def get_component_metadata(
        self,
        component_id: str | SequenceNotStr[str],
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        ...

    @abstractmethod
    def set_component_metadata(
        self,
        component_id: str,
        metadata_id: str,
        metadata_value: Any
    ):
        """Directly set a field in the table. Use with caution!"""


class NewsegsComponentPersistenceInterface(metaclass = ABCMeta):
    """Interface for saving components to persistent storage (in order that they may be accessed by other providers)"""

    @abstractmethod
    def upsert_component(self, component: NewsegsComponent | SequenceNotStr[NewsegsComponent], force: bool = False) -> None:
        """Insert or update a component or list of components into the store.
                        
        Args:
            component: A component or sequence of components to synchronise.
            force: Overwrite the components(s) regardless of whether their revision number has incremented.
        """

    @abstractmethod
    def delete_component(
        self, 
        component_id: str | SequenceNotStr[str],
        ignore_ids: list[str] = [],
    ) -> list[str]:
        """Delete a component or list of components in the store.

        Will remove all dependent components and snapshots (if applicable).

        Args:
            component_id [str | Sequence[str]]: ID(s) of component(s) to delete.
            ignore_ids [list[str]]: IDs of components which may be ignored in dependents search
        Returns:
            List of component_ids for which deletion has failed.
        """

class NewsegsComponentManagerInterface(NewsegsComponentProviderInterface, NewsegsComponentPersistenceInterface):
    ...
