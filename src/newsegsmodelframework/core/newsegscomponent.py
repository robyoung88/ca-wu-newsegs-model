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
import time
from typing import TYPE_CHECKING, Any, Iterable, Literal, Mapping, Optional, Protocol, Sequence, overload, override
import uuid as mod_uuid

from useful_types import SequenceNotStr

from newsegsmodelframework.constants.framework_constants import PREFIX_GROUP_KEY, PREFIX_GROUPS
from newsegsmodelframework.core import SerialisedConfigurationMixin
from newsegsmodelframework.core.trackeddata import ComponentProperty, ComponentPropertyInterface, DataWithRevision
from newsegsmodelframework.util import jsonfuncs

__all__ = [
    'NewsegsComponent', 'RunnableNewsegsComponent', 'TableConfigNewsegsComponent',
    'DataWithRevision'
]

_STATE_EXCLUDES = Literal[
    'excluded',
    'excluded_and_components'
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

    _serialisation_settings = dict(
        state_excludes = 'excluded_and_components'
    )

    _component_ids: dict[str, str]
    """IDs of subcomponents for reconstruction of component."""

    # NB - all ID generating attributes are now in ConfigurationMixin   

    @classmethod
    def set_state_exclusion_policy(cls, excludes: _STATE_EXCLUDES = 'excluded_and_components'):
        cls._serialisation_settings['state_excludes'] = excludes

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
    def get_excluded_attributes(self) -> set[str]:
        excluded = super().get_excluded_attributes()
        if self._serialisation_settings['state_excludes'] == 'excluded_and_components':
            component_property_names = self.get_component_attributes()
            excluded = excluded.union({'_' + x for x in component_property_names})        
        return excluded

    @override
    def _prepare_object_state(self):
        super()._prepare_object_state()
        self.update_component_id_dict()

    def to_dict_repr(self) -> dict[str, Any]:
        """A dictionary reproduction of the component including child components (not references)."""
        type_ = type(self)
        type_.set_state_exclusion_policy('excluded')
        odict = self.to_dict()
        type_.set_state_exclusion_policy('excluded_and_components')
        return odict

    def json_dumps_repr(self) -> str:
        return json.dumps(self.to_dict_repr(), cls = jsonfuncs.NumpyEncoder)
    
    def _repr_represent(self, value):
        if isinstance(value, object) and hasattr(value, 'to_dict_repr'):
            return value.to_dict_repr() # pyright: ignore[reportAttributeAccessIssue]
        return self._represent(value)

    @override
    def __setstate__(self, state: dict[str, Any]) -> None:
        state = copy.copy(state)
        compnames = self.get_component_attributes()
        for cn in compnames:
            if '_'+ cn in state and not cn in state:
                #print(f'Renaming from {'_'+cn} to {cn} in state')
                state[cn] = state['_' + cn]
                del state['_' + cn]

        super().__setstate__(state)

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        cls.set_state_exclusion_policy('excluded')
        state = copy.deepcopy(self.__getstate__())
        cls.set_state_exclusion_policy('excluded_and_components')

        result.__setstate__(state)

        return result

    @staticmethod
    def _anonymise_id_sequence(seq: SequenceNotStr):
        for x in seq:
            if isinstance(x, NewsegsComponent):
                x.id = x.generate_new_id()
            elif isinstance(x, Mapping):
                NewsegsComponent._anonymise_id_sequence(tuple(x.values()))
            elif not isinstance(x, str) and isinstance(x, Sequence):
                NewsegsComponent._anonymise_id_sequence(x) # pyright: ignore[reportArgumentType]
        
    @override
    def anonymise_ids(self):
        super().anonymise_ids()
        self._anonymise_id_sequence(self.get_components())            

    def get_component_attributes(self) -> tuple['str', ...]:
        """A tuple of all the attributes of the object that are themselves NewsegsComponents"""
        type_ = type(self)

        # Strip out dunders and single unders - the properties will not have a leading underscore
        atts = tuple(k for k in dir(type_) if not k.startswith('_'))
        atts = tuple(k for k in atts if isinstance(getattr(type_, k), ComponentPropertyInterface))
        return atts

    @staticmethod
    def _recursive_get_component(atts: NewsegsComponent | Iterable) -> list['NewsegsComponent']:
        rlist = []
            
        if isinstance(atts, NewsegsComponent):
            rlist.append(atts)
        elif isinstance(atts, Mapping):
            for x in atts.values():
                rlist.extend(NewsegsComponent._recursive_get_component(x))
            #(rlist.extend(NewsegsComponent._recursive_get_component(x)) for x in atts.values())
        elif isinstance(atts, Iterable):
            for x in atts:
                rlist.extend(NewsegsComponent._recursive_get_component(x))
            #(rlist.extend(NewsegsComponent._recursive_get_component(x)) for x in atts)
        return rlist                

    def get_components(self, component_group: Optional[PREFIX_GROUP_KEY] = None) -> tuple['NewsegsComponent', ...]:
        """A tuple of all subcomponents that would require saving to store and reattaching after deserialisation."""
        attnames = self.get_component_attributes()
        excl = self._excluded_attributes
        attnames = (x for x in attnames if '_'+x not in excl)

        atts = []
        for nm in attnames:
            try:
                atts.append(getattr(self, nm))
            except AttributeError:
                pass

        components = self._recursive_get_component(atts)
        
        if component_group is not None:
            prefixes = set(x+'-' for x in PREFIX_GROUPS[component_group])
            # Creatig a generator function doesn't seem to work
            sublist = []
            for x in components:
                if any(x.id.startswith(y) for y in prefixes):
                    sublist.append(x)
            components = sublist
            #components = (x for x in components if not any(x.id.startswith(y) for y in prefixes))
        
        return tuple(components)

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
        prefixes = tuple(x+'-' for x in PREFIX_GROUPS['component_configs'])
        for att_name, comp_id in self._component_ids.items():
            if any(comp_id.startswith(y) for y in prefixes):
                comp = component_provider.get_component(comp_id)
                setattr(self, att_name, comp)
        # Ensure that revision is not incremented due to reattachment
        self.revision = r0

    def _get_component_properties(self):
        # Stage 1 - strip out the dunders
        comp_props = [x for x in dir(self) if not x.startswith('__')]
        # Stage 2 - check has attribute
        comp_props = [x for x in comp_props if hasattr(self, x)]
        # Stage 3 - check has '_last_syncronised'
        comp_props = [x for x in comp_props if hasattr(getattr(self, x), '_last_syncronised')]
        # Stage 4 - keep only the single underscore versions
        comp_props.sort()
        r_props = set()
        for x in comp_props:
            if not '_' + x in r_props:
                r_props.add(x)
        return r_props

    def reset_revision(self, chain: bool = True):
        """Set the revision to 0 and _last_syncronised to -1
        
        If chain, also perform this for all ComponentProperties
    """
        if chain:
            comp_props = self._get_component_properties()
            for propname in comp_props:
                att = getattr(self, propname)
                att.revision = 0
                att._last_syncronised = -1
        self.revision = 0
        self._last_syncronised = -1        

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


class DictionaryComponentProvider(NewsegsComponentProviderInterface):
    def __init__(
        self,
        comp_dict: dict
    ) -> None:
        self.comp_dict = comp_dict

    @overload
    def get_component(self, component_id: str) -> NewsegsComponent:
        ...

    @overload
    def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsComponent]:
        ...

    def get_component(
        self, 
        component_id: str | SequenceNotStr[str]
    ) -> NewsegsComponent | SequenceNotStr[NewsegsComponent]:
        if isinstance(component_id, str):
            return self.comp_dict[component_id]
        else:
            return[self.comp_dict[x] for x in component_id]

    def duplicate_component(
        self, 
        component_id: str | NewsegsComponent
    ) -> NewsegsComponent:
        if isinstance(component_id, str):
            return copy.deepcopy(self.comp_dict[component_id])
        else:
            return copy.deepcopy(component_id)

    def add_component(
        self,
        component: NewsegsComponent
    ) -> str:
        self.comp_dict[component.id] = component
        return component.id

    def get_default_component(
        self, 
        component_type: str, 
        index: int = -1
    ) -> NewsegsComponent:
        return next(iter(self.comp_dict.values()))
    
    def get_component_metadata(
        self, 
        component_id: str | SequenceNotStr[str], 
        metadata_ids: str | SequenceNotStr[str]
    ) -> dict[str, Any] | dict[str, dict[str, Any]]:
        return {'message': 'No metadata'}

    def set_component_metadata(
        self, component_id: str, metadata_id: str, metadata_value: Any
    ):
        ...


if TYPE_CHECKING:
    # During type checking, treat TableOwningMixin as a NewsegsComponent subclass
    _Base = NewsegsComponent
else:
    # At runtime, keep it as a pure lightweight mixin base
    _Base = object


class TableOwningMixin(_Base):
    """Mixin that adds table_config behavior to any NewsegsComponent subclass."""

    table_config = ComponentProperty(default = TableConfigNewsegsComponent)

    @override
    def _preupdate_from_dict(self, config):
        super()._preupdate_from_dict(config)
        # Table needs to be created early, for attachment by tablemodifyingproperties

        table_config_exists = hasattr(self, '_table_config')
        full_update = False

        inst_table = config.pop('_table_config', config.pop('table_config', None))
        if inst_table:
            if isinstance(inst_table, NewsegsComponent):
                self.table_config = inst_table
                table_config_exists = True
                full_update = True
            elif isinstance(inst_table, Mapping):
                if not table_config_exists:
                    full_update = True
                    table_config_exists = True
                tc = self.table_config # Should generate a default if not present
                for k, v in inst_table.items():
                    setattr(tc, k, v)
            else:
                raise TypeError(f'Unsupported type for table config update: {type(inst_table)}')
        
        # If the table config doesn't actually exist yet, force it to so we can reset the revision
        # after configuration completes
        if not table_config_exists:
            full_update = True

        if full_update:
            object.__setattr__(self, '_table_config_revis_0', self.table_config.revision)

    @override
    def _post_update_from_dict(self):
        if hasattr(self, '_table_config_revis_0'):
            self.table_config.revision = self._table_config_revis_0
            delattr(self, '_table_config_revis_0')
        super()._post_update_from_dict()


class TableOwningNewsegsComponent(TableOwningMixin, NewsegsComponent):
    """Component that owns a table_config."""


class TableOwningRunnableNewsegsComponent(TableOwningMixin, RunnableNewsegsComponent):
    """Runnable component that owns a table config."""
