"""
A container and controller for metamodels and variables.

Provides a class which encapsulates multiple NewSEGS metamodels, for multi-way
sensitivity analysis.
"""
import logging
logger = logging.getLogger(__name__)

from collections import OrderedDict
import copy
from typing import Any, Optional, Sequence, override
import warnings
from useful_types import SequenceNotStr

from newsegsmodelframework.constants.framework_constants import COMPONENT_PREFIXES
from newsegsmodelframework.core import NewsegsComponent, TableConfigNewsegsComponent
from newsegsmodelframework import newsegsmetamodel
from newsegsmodelframework.core.newsegscomponent import NewsegsComponentProviderInterface, TableOwningNewsegsComponent
from newsegsmodelframework.core.trackeddata import (
    ComponentProperty, DataWithRevision, RevisionNotifierProtocol,
    SubscriptionRevisionNotifierMixin, TableModifyingComponentListProperty, TableModifyingObservableList, 
    TableModifyingObservableOrderedDict, revision_dataclass
)
from newsegsmodelframework.newsegssensitivity.dsa import DSAComponent
from newsegsmodelframework.newsegssensitivity.psa import PSAComponent
from newsegsmodelframework.newsegsvariable.variable import Variable
from newsegsmodelframework.newsegsvariable.variableprovider import InMemoryVariableProvider, RecoverableInMemoryVariableProvider, VariablePersistenceInterface

@revision_dataclass
class NewsegsProjectConfig(DataWithRevision):
    model_type: str = ''
    model_version: str = ''


class ProjVarWatcher(RevisionNotifierProtocol):
    
    def __init__(self, project: 'NewsegsProject'):
        self._project = project

    def _add_child(self, child: 'RevisionNotifierProtocol', subscribe: bool = True): 
        # Only need to receive notifications of change, don't need to check on revision status
        if subscribe and isinstance(child, SubscriptionRevisionNotifierMixin):
            child._subscribers.append(self)
    
    def _remove_child(self, child: 'RevisionNotifierProtocol'):
        if isinstance(child, SubscriptionRevisionNotifierMixin):
            child.unsubscribe(self)
    
    def _notify_change(self, trigger: Any | None = None, **kwargs):
        if isinstance(trigger, (TableModifyingObservableList, TableModifyingObservableOrderedDict)):
            proj = self._project
            # Something has happened to the metamodels table, check we have all variables
            var_uids = set(proj._variables_by_uid.keys())
            found_uids = set()
            for mm in proj.metamodels:
                for var in mm.variables.values():
                    vid = var.id
                    if not vid in var_uids:
                        added_uid = proj.add_variable(var)
                        if not vid == added_uid:
                            warnings.warn(f'Change of variable id on add - {vid} to {added_uid}')
                            vid = added_uid
                            var.id = vid
                        var_uids.add(vid)
                    found_uids.add(vid)
            lost_vars = var_uids - found_uids
            if lost_vars:
                logger.info('Removing variables from project: %s', lost_vars)
                proj.delete_variable(list(lost_vars))
        # Otherwise, do nothing


class NewsegsProject(TableOwningNewsegsComponent, RecoverableInMemoryVariableProvider):
    """A container and controller for metamodels and variables."""
    
    _name = 'NewSEGS Project'
    _version = 'v0.0.1'
    _id_prefix = COMPONENT_PREFIXES['project']

    _excluded_attributes = NewsegsComponent._excluded_attributes.union(
        {'_watcher', '_variables_by_uid', '_variables_by_varid'}
    )

    metamodels = TableModifyingComponentListProperty(oftype = newsegsmetamodel.NewsegsMetaModel)
    dsa_config = ComponentProperty(default = DSAComponent, oftype = DSAComponent)
    psa_config = ComponentProperty(default = PSAComponent, oftype = PSAComponent)

    _focussed_metamodel: int = 0
    _watcher: RevisionNotifierProtocol | None = None

    @override
    def _generate_config(self, *args, **kwargs) -> NewsegsProjectConfig:
        return NewsegsProjectConfig(*args, **kwargs)
    _config: NewsegsProjectConfig # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        metamodels: Optional[Sequence[newsegsmetamodel.NewsegsMetaModel]] = [],
        *args,
        default_variables: Optional[Sequence[Variable]] = [],
        dsa_config: Optional[DSAComponent] = None,
        psa_config: Optional[PSAComponent] = None,
        table_config: Optional[TableConfigNewsegsComponent] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        InMemoryVariableProvider.__init__(self, default_variables)

        self.table_config = table_config or TableConfigNewsegsComponent()
        self.watcher = ProjVarWatcher(self)
        self.dsa_config = dsa_config or DSAComponent()
        self.psa_config = psa_config or PSAComponent()

        self.metamodels = metamodels or []
        if len(self.metamodels):
            if not self.model_type == self.metamodels[0].model.model_type:
                if self.model_type == '':
                    self.model_type = self.metamodels[0].model.model_type
                else:
                    raise TypeError(f'First metamodel of incompatible type; Expected: {self.model_type}; received: {self.metamodels[0].model.model_type}')
            if not self.model_version == self.metamodels[0].model.version:
                if self.model_version == '':
                    self.model_version = self.metamodels[0].model.version
                else:
                    raise TypeError(f'First metamodel of incompatible version; Expected: {self.model_version}; received: {self.metamodels[0].model.version}')

    @property
    def metamodel_ids(self) -> tuple[str, ...]:
        return tuple(mm.id for mm in self.metamodels)

    @property
    def watcher(self) -> RevisionNotifierProtocol:
        if self._watcher is None:
            self._watcher = ProjVarWatcher(self)
        return self._watcher

    @watcher.setter
    def watcher(self, watcher: RevisionNotifierProtocol):
        self._watcher = watcher

    def get_focussed_metamodel_index(self) -> int:
        if self._focussed_metamodel >= len(self.metamodels):
            if len(self.metamodels) == 0:
                raise ValueError('No metamodels within project')
            else:
                self._focussed_metamodel = len(self.metamodels) - 1
        return self._focussed_metamodel

    def set_focussed_metamodel_index(self, metamodel_index: int = 0):
        self.set_focussed_metamodel(metamodel_index = metamodel_index)

    def get_focussed_metamodel(self):
        return self.metamodels[self.get_focussed_metamodel_index()]

    def set_focussed_metamodel(self, metamodel_id: Optional[str] = None, metamodel_index: int = 0):
        if metamodel_id:
            for i, mm in enumerate(self.metamodels):
                if mm.id == metamodel_id:
                    self._focussed_metamodel = i
                    return
        self._focussed_metamodel = max(0, min(len(self.metamodels)-1, metamodel_index))

    def duplicate_metamodel(self, metamodel_id: str) -> newsegsmetamodel.NewsegsMetaModel:
        try:
            wch = self.metamodel_ids.index(metamodel_id)
        except ValueError:
            raise ValueError(f'Metamodel not found: {metamodel_id}')
        mm = self.metamodels[wch]

        mm2 = copy.deepcopy(mm)
        mm2.anonymise_ids()
            
        self.metamodels.append(mm2) # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        return mm2 # pyright: ignore[reportReturnType]

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        
        cls.set_state_exclusion_policy('excluded')
        state = self.__getstate__()
        cls.set_state_exclusion_policy('excluded_and_components')

        state = {k:copy.deepcopy(v, memo) for k, v in state.items()}

        result.__setstate__(state)

        # Reattach the metamodel variables from self, then add them to result,
        # then duplicate and reattach
        for mm in result.metamodels:
            mm.reattach_variables(self)

        #for var in mm.variables.values():
        #    self.add_variable(var)

        new_vars = []
        for varid, varlist in self._variables_by_varid.items():
            for uid, var in varlist.items():
                old_id = var.id
                new_var = copy.deepcopy(var)
                new_var.anonymise_ids()
                new_vars.append(new_var)
                for mm in result.metamodels:
                    if mm.variables[varid].id == old_id:
                        mm.variables[varid] = new_var
        result._variables_by_varid.clear()
        result._variables_by_uid.clear()
        for var in new_vars:
            result.add_variable(var)

        result.revision = self.revision
        result.table_config.revision = self.table_config.revision

        # Other id anonymisation should take place outside of the copy

        return result

    def reattach_metamodels(self, provider: NewsegsComponentProviderInterface):
        if not hasattr(self, '_metamodel_ids') or not self._metamodel_ids:
            return
        r0 = self.revision
        tr0 = self.table_config.revision
        metamodels = provider.get_component(self._metamodel_ids)
        for i, mm in enumerate(metamodels):
            if not isinstance(mm, newsegsmetamodel.NewsegsMetaModel):
                raise TypeError(f'Component provider did not return a metamodel for id {self._metamodel_ids[i]}, is {type(mm)}')
            mm.reattach_variables(self)
        self.metamodels = metamodels
        self.revision = r0
        self.table_config.revision = tr0

    def get_metamodel_by_id(self, metamodel_id: str):
        for mm in self.metamodels:
            if mm.id == metamodel_id:
                break
        else:
            raise KeyError(f'Metamodel {metamodel_id} not found for project {self.name}[{self.id}] - available values are {[x.id for x in self.metamodels]}.')
        return mm

    @override
    def _prepare_object_state(self):
        super()._prepare_object_state()
        self._metamodel_ids = self.metamodel_ids
        vrus = dict()
        for k, v in self._variables_by_varid.items():
            vrus[k] = list(v.keys())

    def variable_to_store(
        self, 
        store_interface: VariablePersistenceInterface, 
        variable_id: Optional['str | SequenceNotStr[str]'] = None,
        force: bool = False,
    ):
        if isinstance(variable_id, str):
            variable_id = [variable_id, ]
        elif variable_id is None:
            variable_id = list(self._variables_by_uid.keys())

        vars = [self.get_variable(x) for x in variable_id]
        store_interface.upsert_variable(vars, force)

    @override
    def _preupdate_from_dict(self, config):
        super()._preupdate_from_dict(config)
        if not hasattr(self, '_variables_by_varid'):
            self._variables_by_varid = OrderedDict()
        if not hasattr(self, '_variables_by_uid'):
            self._variables_by_uid = dict()
            
