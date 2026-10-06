"""
A container and controller for models and variables.

Provides a class which encapsulates several structures and methods used for 
NewSEGS modelling.

Principally, this NewsegsMetaModel class holds:
    - A reference to a NewsegsModel
    - A reference to a NewsegsFinance which itself references the NewsegsModel
    - A series of Variables which locate the values in the NewsegsModel and 
      NewsegsFinance
The Metamodel can be set into a state:
    - Deterministic run
    - Deterministic probability analysis
    - Probabilisitic sensitivity analysis
Its state is used to control the behaviour of its Variables and to propagate 
live values into its NewsegsModel and NewsegsFinance. These models can then be
run and values extracted.

For a dsa run, a (small) number of statistics must be nominated to be held in a
dataframe which will be accessible after completion; each row will correspond
to a change in a single Variable.

For a psa run, a (small) number of statistics must be nominated to be held in a
dataframe which will be accessible after completion; each row will correspond
to a sample across all enabled PSA variables.
"""
import copy
import datetime
import logging
from typing import Any, Mapping, MutableSequence, Optional, override

from newsegsmodelframework.constants.framework_constants import COMPONENT_PREFIXES
from newsegsmodelframework.core import serialisation
from newsegsmodelframework.core.newsegscomponent import NewsegsComponentProviderInterface, TableOwningNewsegsComponent
from newsegsmodelframework.core.serialisedtrackeddata import SerialisedConfigurationMixin
from newsegsmodelframework.core.trackeddata import ComponentOrderedDictProperty, ComponentProperty, DataWithRevision, RevisionNotifierProtocol, SubscriptionRevisionNotifierMixin, TableModifyingComponentOrderedDictProperty, TableModifyingObservableList, TableModifyingObservableOrderedDict, revision_dataclass
from newsegsmodelframework.newsegsmodel import newsegsmodel
from newsegsmodelframework.newsegsfinance import newsegsfinance
from newsegsmodelframework.core import NewsegsComponent, TableConfigNewsegsComponent
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsvariable.variableprovider import VariableProviderInterface

logger = logging.getLogger(__name__)

def make_varid(
    *args,
    key: str,
    section: str|None = None,
    subindex: int|str = 0,
    **kwargs
) -> str:
    """
    Create a string id for a variable based on interface parameters

    Args:
        key (str): Interface key
        section (str | None, optional): Interface section. Defaults to None.
        subindex (int | str): Variable subindex

    Returns:
        str: Concatenation of section, key and subindex
    """
    if section is None:
        section = 'None'
    return f'{section}.{key}.{subindex}'
   

class MMVarWatcher(RevisionNotifierProtocol):
    def __init__(self, metamodel: 'NewsegsMetaModel'):
        self._metamodel = metamodel
        self._held_ids = {}

    def update_held_ids(self):
        mm = self._metamodel
        previous_varids = set(self._held_ids.keys())
        extant_varids = set(mm.variables.keys())

        new_varids = extant_varids - previous_varids
        removed_varids = previous_varids - extant_varids
        continuing_varids = extant_varids & previous_varids

        changed_varids = set(self._held_ids[x] != mm.variables[x].id for x in continuing_varids)

        for varid in removed_varids:
            if varid in mm._variables_last_model_sync:
                del mm._variables_last_model_sync[varid]

        for varid in new_varids:
            # Set to require sync
            mm._variables_last_model_sync[varid] = -1

        for varid in changed_varids:
            # Set to require sync
            mm._variables_last_model_sync[varid] = -1 

        self._held_ids = {x: mm.variables[x].id for x in extant_varids}
        
    def _add_child(self, child: 'RevisionNotifierProtocol', subscribe: bool = True): 
        # Only need to receive notifications of change, don't need to check on revision status
        if subscribe and isinstance(child, SubscriptionRevisionNotifierMixin):
            child._subscribers.append(self)
    
    def _remove_child(self, child: 'RevisionNotifierProtocol'):
        if isinstance(child, SubscriptionRevisionNotifierMixin):
            child.unsubscribe(self)
    
    def _notify_change(self, trigger: Any | None = None, **kwargs):
        if isinstance(trigger, (TableModifyingObservableOrderedDict)):
            self.update_held_ids()
            
        # Otherwise, do nothing


@revision_dataclass
class NewsegsMetaModelConfig(DataWithRevision):
    ...

class NewsegsMetaModel(TableOwningNewsegsComponent):
    """A container and controller for models and variables."""

    model_id: str
    finance_id: str
    checked_out: bool = False

    _name = 'NewSEGS MetaModel'
    _version = '0.0.1'
    _id_prefix = COMPONENT_PREFIXES['metamodel']
    _last_modified: datetime.datetime = datetime.datetime.now()

    _excluded_attributes = NewsegsComponent._excluded_attributes.union({'_watcher'})

    last_dsa_run: float = 0.
    last_psa_run: float = 0.
    last_optim_run: float = 0.

    model = ComponentProperty(default = None, oftype = newsegsmodel.NewsegsModel)
    finance = ComponentProperty(default = None, oftype = newsegsfinance.NewsegsFinance)

    variables = TableModifyingComponentOrderedDictProperty(oftype = variable.Variable)
    _variables_last_model_sync: dict
    """The revision number of the variable at last deterministic sync."""

    @override
    def _generate_config(self, *args, **kwargs) -> NewsegsMetaModelConfig:
        return NewsegsMetaModelConfig(*args, **kwargs)
    _config: NewsegsMetaModelConfig # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        model: newsegsmodel.NewsegsModel,
        finance: newsegsfinance.NewsegsFinance,
        variables: MutableSequence[variable.Variable] = [],
        table_config: Optional[TableConfigNewsegsComponent] = None,
        **kwargs
    ):
        super().__init__(**kwargs)
        
        self.table_config = table_config or TableConfigNewsegsComponent()
        self.watcher = MMVarWatcher(self)

        self.model = model
        self.finance = finance

        self.variables = {variable.variable_uid(x):x for x in variables}
        self._variables_last_model_sync = {}

    @property
    def watcher(self) -> RevisionNotifierProtocol:
        if self._watcher is None:
            self._watcher = MMVarWatcher(self)
        return self._watcher

    @watcher.setter
    def watcher(self, watcher: RevisionNotifierProtocol):
        self._watcher = watcher
        
    def reattach_model(
        self,
        model_provider: Mapping[str, newsegsmodel.NewsegsModel]
    ) -> None:
        """Reattach the associated NewsegsModel instance after metamodel reconstruction.
        
        Args:
            model_provider: Mapping of model IDs to NewsegsModel instances.
            
        Raises:
            AttributeError: If the MetaModel has no associated model ID.
            ValueError: If model_provider cannot provide the model.
            TypeError: If the provided object is not a NewsegsModel.
        """
        if not hasattr(self, '_model_id') or self._model_id == '':
            raise AttributeError('this MetaModel has no associated model to reattach.')
        mdl = model_provider.get(self._model_id)
        if mdl is None:
            raise ValueError(f'model_provider could not provide model for key {self._model_id}')
        if not isinstance(mdl, newsegsmodel.NewsegsModel):
            raise TypeError(f'model_provider did not provide a NewsegsModel for key {self._model_id} - {type(mdl)} returned instead')
        self.model = mdl
        try:
            if self.finance is not None:
                self.finance.set_model(self.model)
        except AttributeError:
            pass

    def reattach_em(self, em_provider: NewsegsComponentProviderInterface):
        """Reattach the associated NewsegsModel instance after metamodel reconstruction.
        
        """
        r0 = self.revision
        if not hasattr(self, '_model_id') or self._model_id == '':
            raise AttributeError('This MetaModel has no associated model to reattach.')
        mdl = em_provider.get_component(self._model_id)
        if not isinstance(mdl, newsegsmodel.NewsegsModel):
            raise TypeError(f'em_provider did not provide a NewsegsModel for key {self._model_id}')
        self.model = mdl
        try:
            if self.finance is not None:
                self.finance.set_model(self.model)
        except AttributeError:
            pass
        self.revision = r0

    def reattach_finance(self, finance_provider: Mapping[str, newsegsfinance.NewsegsFinance]) -> None:
        """Reattach the associated NewsegsFinance instance after metamodel reconstruction.
        
        Args:
            finance_provider: Mapping of finance IDs to NewsegsFinance instances.
            
        Raises:
            AttributeError: If the MetaModel has no associated finance ID.
            ValueError: If finance_provider cannot provide the finance.
            TypeError: If the provided object is not a NewsegsFinance.
        """
        r0 = self.revision
        if not hasattr(self, '_finance_id') or self._finance_id == '':
            raise AttributeError('this MetaModel has no associated finance to reattach.')
        fnc = finance_provider.get(self._finance_id)
        if fnc is None:
            raise ValueError(f'finance_provider could not provide finance for key {self._finance_id}')
        if not isinstance(fnc, newsegsfinance.NewsegsFinance):
            raise TypeError(f'finance_provider did not provide a NewsegsFinance for key {self._finance_id} - {type(fnc)} returned instead')
        self.finance = fnc
        if self.model is not None:
            self.finance.set_model(self.model, dirty = False)
        self.revision = r0

    def reattach_fm(self, fm_provider: NewsegsComponentProviderInterface):
        """Reattach the associated NewsegsFinance instance after metamodel reconstruction.
        
        """
        r0 = self.revision
        if not hasattr(self, '_finance_id') or self._finance_id == '':
            raise AttributeError('This MetaModel has no associated finance to reattach.')
        fnc = fm_provider.get_component(self._finance_id)
        if not isinstance(fnc, newsegsfinance.NewsegsFinance):
            raise TypeError(f'fm_provider did not provide a NewsegsFinance for key {self._finance_id}')
        self.finance = fnc
        try:
            if self.model is not None:
                self.finance.set_model(self.model, False)
        except AttributeError:
            pass
        self.revision = r0

    # def get_component_attributes(self) -> tuple[str, ...]:
    #     atts = super().get_component_attributes()
    #     return ('table_config', *atts)

    @property
    def variable_ids(self) -> tuple[dict[str, str], ...]:
        # As variables cannot exist until table_config has been reattached,
        # only search for _variable_ids during child uid update
        if self.table_config is None:
            return getattr(self, '_variable_ids', ())
        if len(self.variables) == 0 and hasattr(self, '_variable_ids'):
            return self._variable_ids
        return tuple(
            {
                'varid': k,
                'uid': x.id
            } for k, x in self.variables.items()
        )

    def reattach_variables(self, variable_provider: VariableProviderInterface) -> None:
        """Reattach any associated Variables after metamodel reconstruction.
        
        Args:
            variable_provider: Instance of VariableProviderInterface (typically a Project).
        """
        these_vars = self.variable_ids
        r0 = self.revision
        tr0 = self.table_config.revision
        vr0 = self.variables.revision # type: ignore
        for var_identifiers in these_vars:
            try:
                v = variable_provider.get_variable(var_identifiers['uid'])
            except KeyError:
                v = variable_provider.get_default_variable(var_identifiers['varid'])
            self.variables[var_identifiers['varid']] = v
        self.variables.revision = vr0 # type: ignore
        self.revision = r0
        self.table_config.revision = tr0
        

    def reattach_table_config(self, component_provider: Mapping[str, NewsegsComponent]):
        """Reattach the associated TableConfig instance after metamodel reconstruction.
        
        Args:
            component_provider: Mapping of component IDs to NewsegsComponent instances.
        Raises:
            AttributeError: If the MetaModel has no associated table config ID.
            ValueError: If component_provider cannot provide the table config.
            TypeError: If the provided object is not a TableConfigNewsegsComponent.
        """
        if not hasattr(self, '_table_config_id') or self._table_config_id == '':
            raise AttributeError('This MetaModel has no associated TableConfig to reattach.')
        tc = component_provider.get(self._table_config_id)
        if tc is None:
            raise ValueError(f'component_provider could not provide table config for key {self._table_config_id}')
        if not isinstance(tc, TableConfigNewsegsComponent):
            raise TypeError(f'component_provider did not provide a TableConfigNewsegsComponent for key {self._table_config_id}')
        self.table_config = tc
    
    def update_variable_from_interface(
        self,
        section: str,
        key: str,
        subindex: int,
        parameter_index: int,
        vector_location: int,
        value: variable.ScalarParam
    ) -> tuple[bool, bool, bool, bool, tuple[variable.Param,...]]:
        """
        Update the addressed variable with the new value.

        The Variable is addressed by {section}.{key}.{subindex} in the 
        .variables OrderedDict. After identifying the variable, the nominated 
        parameter index is updated with the scalar value; if the parameter is
        an array type, it is addressed by its location in the flattened array
        using the vector_location.

        Args:
            section: Interface section.
            key: Variable specifier.
            subindex: Index of multiple instances of specified Variable.
            parameter_index: Index of metaparameter within Variable to update.
            vector_location: Index of scalar metaparameter within flattened array of array-type parameter.
            value: Value with which to update metaparameter.

        Returns:
            - bool - The parameter has been set
            - bool - The deterministic value of the Variable has been impacted
            - bool - The DSA value(s) of the Variable has/have been impacted
            - bool - The PSA values(s) of the Variable has/have been impacted
            - tuple[Param, ...] - The set of parameters now held by the Variable
        """
        varid = make_varid(key = key, section = section, subindex = subindex)
        var = self.variables.get(varid)
        if var is None:
            raise ValueError(f'variable {varid} not found')
        old_params = var.parameters
        old_value = var.deterministic_value
        old_std = var.get_std()
        old_dsa_low = var.get_dsa_value('lower', True)
        old_dsa_high = var.get_dsa_value('upper', True)
        is_ok, new_params = var.set_single_parameter(value, parameter_index, vector_location)

        if not is_ok:
            var.set_parameters(*old_params)
            return False, True, True, True, old_params
        
        if var.dsa_show:
            try:
                dsa_changed = (
                    (var.get_dsa_value('lower', True) != old_dsa_low)
                    or (var.get_dsa_value('upper', True) != old_dsa_high)
                )
            except TypeError:
                var.set_parameters(*old_params)
                return False, True, True, True, old_params
        else:
            dsa_changed = False
            
        new_value = var.deterministic_value

        if var.psa_show:
            new_std = var.get_std()
            psa_changed = (
                old_value != new_value
                or old_std != new_std
            )
        else:
            psa_changed = False

        det_changed = old_value != new_value

        return is_ok, det_changed, dsa_changed, psa_changed, new_params
    
    def update_model_from_variable_deterministic(
        self,
        section: str,
        key: str | None = None,
        subindex: int | None = None,
    ) -> str:
        """
        Update the attached model with the deterministic value of the addressed variable

        Variable address is {section}.{key}.{subindex} in the .variables OrderedDict
        """
        if key is None and subindex is None:
            varid = section
        else:
            if key is None:
                key = ''
            if subindex is None:
                subindex = 0
            varid = make_varid(key = key, section = section, subindex = subindex)
        
        var = self.variables.get(varid)
        if var is None:
            raise ValueError(f'variable {varid} not found')
        if var.configuration_type == 'finance':
            var.update_model(self.finance)
        else:
            var.update_model(self.model)
        self._variables_last_model_sync[varid] = var.revision
        return var.configuration_type
    
    def sync_model_with_changed_variables_deterministic(
        self
    ) -> set[str]:
        affected_models = set()
        for varid, var in self.variables.items():
            if self._variables_last_model_sync.get(varid, -1) != var.revision:
                try:
                    if isinstance(varid, str):
                        affected_models.add(self.update_model_from_variable_deterministic(varid)) 
                except ValueError as e:
                    logger.error(e)
                
                self._variables_last_model_sync[varid] = var.revision
  
        return affected_models

    @override
    def _prepare_object_state(self):
        super()._prepare_object_state()
        self._variable_ids = self.variable_ids

    # @override
    # def to_dict(self) -> dict[str, Any]:
    #     odict = super().to_dict()
    #     odict['_table_config_id'] = self.table_config.id
    #     odict['_model_id'] = self.model.id
    #     odict['_finance_id'] = self.finance.id
    #     odict['_variable_ids'] = self.variable_ids
    #     return odict

    # @override
    # def to_dict_repr(self) -> dict[str, Any]:
    #     odict = super().to_dict_repr()
        
    #     odict['model'] = self.model.to_dict_repr()
    #     del odict['_model_id']
    #     odict['finance'] = self.finance.to_dict_repr()
    #     del odict['_finance_id']

    #     vars = {k: v.to_dict() for k, v in self.variables.items()}
    #     odict['variables'] = vars
    #     # Clear the old variable ids, as don't want to get confused when we reconstruct
    #     odict['_variable_ids'] = []

    #     return odict

    # @override
    # def anonymise_ids(self):
    #     super().anonymise_ids()
    #     self.model.anonymise_ids()
    #     self.finance.anonymise_ids()
    #     # Do not anonymise variables! Remember, the metamodel does not own its variables.

    
   
    @override
    def _preupdate_from_dict(self, config):
        super()._preupdate_from_dict(config)
        # Set the watcher prior to property attachment
        if not hasattr(self, '_watcher') or self._watcher is None:
            self.watcher = MMVarWatcher(self)

        if 'model' in config:
            self.model = config.pop('model')
        if 'finance' in config:
            self.finance = config.pop('finance')
            try:
                self.finance.set_model(self.model)
            except AttributeError:
                pass

    @override
    def _post_update_from_dict(self):
        try:
            if self.finance.model is None or self.finance.model is not self.model:
                self.finance.set_model(self.model, dirty = False)
        except AttributeError:
            pass
        super()._post_update_from_dict()

    @override
    def anonymise_ids(self, include_variables = False):
        if include_variables:
            return super().anonymise_ids()
        else:
            SerialisedConfigurationMixin.anonymise_ids(self)
            self._anonymise_id_sequence(self.get_components(component_group = 'exclude_variables'))

    def __deepcopy__(self, memo):
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result
        
        cls.set_state_exclusion_policy('excluded')
        state = self.__getstate__()
        cls.set_state_exclusion_policy('excluded_and_components')

        state = {k:copy.deepcopy(v, memo) for k, v in state.items() if k != '_variables'}

        result.__setstate__(state)
        
        # Need to generate a new container, but the contents must be identical
        result.variables = {k: v for k, v in self.variables.items()}
        result.variables.revision = self.variables.revision # pyright: ignore[reportAttributeAccessIssue]

        result.revision = self.revision
        result.table_config.revision = self.table_config.revision
        return result

    def to_config(self) -> dict[str, str|int|float]:
        """
        Simplify metamodel to a simple dictionary for passing around.
        """
        return {
            'name': self.name,
            'metamodel_id': self.id,
            '_model_id': self.model_id,
            '_finance_id': self.finance_id,
            'last_modified': self._last_modified.isoformat()
        }
    
    @classmethod
    def generate_new_config(cls) -> dict[str, str|int|float]:
        """
        Generate a configuration using random ids for self, model and finance.
        """
        return {
            'name': cls._name,
            'metamodel_id': cls.generate_new_id(),
            '_model_id': newsegsmodel.NewsegsModel.generate_new_id(),
            '_finance_id': newsegsfinance.NewsegsFinance.generate_new_id(),
            'last_modified': datetime.datetime.now().isoformat()
        }

    # @classmethod
    # @override
    # def from_dict(cls, config):
    #     config = config.copy()
    #     inst = cls.__new__(cls)
    #     inst._config = inst._generate_config()
    #     inst.watcher = MMVarWatcher(inst)
    #     inst.update(config)
    #     return inst
    
    @override
    def update(self, config: dict[str, Any] | type[serialisation.T]):
        super().update(config)
        try:
            self.finance.set_model(self.model)
        except AttributeError:
            pass

    

# NewsegsMetaModel._excluded_attributes = super(NewsegsMetaModel, NewsegsMetaModel)._excluded_attributes + (
#     '_model', '_finance', '_variables', '_table_config', '_watcher'
# )
