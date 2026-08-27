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
from collections import OrderedDict
import datetime
import logging
from typing import Any, Mapping, MutableSequence, Optional, Sequence, override

from newsegsmodelframework.core import serialisation
from newsegsmodelframework.core.newsegscomponent import ComponentProperty
from newsegsmodelframework.core.trackeddata import DataWithRevision
from newsegsmodelframework.newsegsmodel import newsegsmodel
from newsegsmodelframework.newsegsfinance import newsegsfinance
from newsegsmodelframework.core import NewsegsComponent, TableConfigNewsegsComponent
from newsegsmodelframework.newsegsvariable import variable

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


class NewsegsMetaModelConfig(DataWithRevision):
    ...


class NewsegsMetaModel(NewsegsComponent):
    """A container and controller for models and variables."""

    model_id: str
    finance_id: str
    checked_out: bool = False

    _name = 'NewSEGS MetaModel'
    _version = '0.0.1'
    _id_prefix = 'metam'
    _last_modified: datetime.datetime = datetime.datetime.now()

    last_dsa_run: float = 0.
    last_psa_run: float = 0.
    last_optim_run: float = 0.

    model = ComponentProperty(oftype = newsegsmodel.NewsegsModel)
    finance = ComponentProperty(oftype = newsegsfinance.NewsegsFinance)
    table_config = ComponentProperty(oftype = TableConfigNewsegsComponent)

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
        
        self.model = model
        self.finance = finance
        self.variables = variables
        self.require_sync = {x for x in self.variables.keys()} # pyright: ignore[reportAttributeAccessIssue]
        """
        A set of variables that have been updated and have not yet been synchronised with model/finance
        """
        self.table_config = table_config or TableConfigNewsegsComponent()

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

    def reattach_finance(self, finance_provider: Mapping[str, newsegsfinance.NewsegsFinance]) -> None:
        """Reattach the associated NewsegsFinance instance after metamodel reconstruction.
        
        Args:
            finance_provider: Mapping of finance IDs to NewsegsFinance instances.
            
        Raises:
            AttributeError: If the MetaModel has no associated finance ID.
            ValueError: If finance_provider cannot provide the finance.
            TypeError: If the provided object is not a NewsegsFinance.
        """
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

    @property
    def variables(self) -> OrderedDict[str, variable.Variable]:
        """An OrderedDict mapping variable UIDs to Variable instances."""
        return self._variables
    
    @variables.setter
    def variables(self, variables: Sequence[variable.Variable]):
        if not hasattr(self, '_variables'):
            self._variables = OrderedDict()
        for var in variables:
            uid = variable.variable_uid(var)
            if isinstance(uid, list):
                for id in uid:
                    self._variables[id] = var
            else:
                self._variables[uid] = var

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

        if det_changed:
            self.require_sync.add(varid)

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
        return var.configuration_type
    
    def sync_model_with_changed_variables_deterministic(
        self
    ) -> set[str]:
        affected_models = set()
        while len(self.require_sync) > 0:
            varid = self.require_sync.pop()
            try:
                affected_models.add(self.update_model_from_variable_deterministic(varid))
            except ValueError as e:
                logger.error(e)

        #if 'model' in affected_models:
        #    self.model._dirty = True
        #if 'finance' in affected_models:
        #    self.finance._dirty= True
            
        return affected_models

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        for dontpickle in ['_model', '_finance']:
            if dontpickle in state:
                del state[dontpickle]
        if self.model:
            state['_model_id'] = self.model.id
        if self.finance:
            state['_finance_id'] = self.finance.id
        return state
    
    # Will have no explicit setstate - require using 'reattach_' methods
    # to recover the missing components using external mappings.
    # We will also not use a custom pickler, because we don't want to switch out picklers
    # depending on what is being pickled, and ultimately we do want models and finances to be
    # picklable in other circumstances.

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
    
    @override
    def update(self, config: dict[str, Any] | type[serialisation.T]):
        super().update(config)
        # When coming from json, sets are as list, so will need reassigning
        if not isinstance(self.require_sync, set):
            self.require_sync = set(self.require_sync)

NewsegsMetaModel._excluded_attributes = super(NewsegsMetaModel, NewsegsMetaModel)._excluded_attributes + ('_model', '_finance')
