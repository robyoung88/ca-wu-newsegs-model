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
from typing import Any, Mapping, MutableSequence, Sequence, override

from core import newsegscomponent, serialisation
from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance
from newsegsvariable import variable

logger = logging.getLogger(__name__)

class NewsegsMetaModel(newsegscomponent.NewsegsComponent):

    model_id: str
    finance_id: str
    checked_out: bool = False

    _name = 'NewSEGS MetaModel'
    _version = '0.0.1'
    _id_prefix = 'metam'
    _last_modified: datetime.datetime = datetime.datetime.now()
    last_dsa_run: float = 0.
    last_psa_run: float = 0.

    def __init__(
        self,
        model: newsegsmodel.NewsegsModel,
        finance: newsegsfinance.NewsegsFinance,
        variables: MutableSequence[variable.Variable] = [],
    ):
        super().__init__()
        self.model = model
        self.finance = finance
        self.variables = variables
        self.require_sync = {x for x in self.variables.keys()}
        """
        A set of variables that have been updated and have not yet been synchronised with model/finance
        """
    
    @property
    def model(self) -> newsegsmodel.NewsegsModel:
        return self._model
    
    @model.setter
    def model(self, model: newsegsmodel.NewsegsModel) -> None:
        self._model = model
        self.model_id = model.id

    def reattach_model(self, model_provider: Mapping[str, newsegsmodel.NewsegsModel]) -> None:
        """
        After reconstruction of the metamodel, reattach the associated instance of NewsegsModel
        """
        if not hasattr(self, 'model_id') or self.model_id == '':
            raise AttributeError('this MetaModel has no associated model to reattach.')
        mdl = model_provider.get(self.model_id)
        if mdl is None:
            raise ValueError(f'model_provider could not provide model for key {self.model_id}')
        if not isinstance(mdl, newsegsmodel.NewsegsModel):
            raise TypeError(f'model_provider did not provide a NewsegsModel for key {self.model_id} - {type(mdl)} returned instead')
        self.model = mdl
    
    @property
    def finance(self) -> newsegsfinance.NewsegsFinance:
        return self._finance
    
    @finance.setter
    def finance(self, finance: newsegsfinance.NewsegsFinance) -> None:
        self._finance = finance
        self.finance_id = finance.id

    def reattach_finance(self, finance_provider: Mapping[str, newsegsfinance.NewsegsFinance]) -> None:
        """
        After reconstruction of the metamodel, reattach the associated instance of NewsegsModel
        """
        if not hasattr(self, 'finance_id') or self.finance_id == '':
            raise AttributeError('this MetaModel has no associated finance to reattach.')
        fnc = finance_provider.get(self.finance_id)
        if fnc is None:
            raise ValueError(f'finance_provider could not provide finance for key {self.finance_id}')
        if not isinstance(fnc, newsegsfinance.NewsegsFinance):
            raise TypeError(f'finance_provider did not provide a NewsegsFinance for key {self.finance_id} - {type(fnc)} returned instead')
        self.finance = fnc

    @property
    def variables(self) -> OrderedDict[str, variable.Variable]:
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

        Returns:
            - bool - The parameter has been set
            - bool - The deterministic value of the Variable has been impacted
            - bool - The DSA value(s) of the Variable has/have been impacted
            - bool - The PSA values(s) of the Variable has/have been impacted
            - tuple[Param, ...] - The set of parameters now held by the Variable
        """
        varid = section + "." + key + "." + str(subindex)
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
            varid = section + "." + key + "." + str(subindex)
        
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

        if 'model' in affected_models:
            self.model._dirty = True
        if 'finance' in affected_models:
            self.finance._dirty= True
            
        return affected_models

    def __getstate__(self) -> dict[str, Any]:
        state = self.__dict__.copy()
        for dontpickle in ['_model', '_finance']:
            if dontpickle in state:
                del state[dontpickle]
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
            'model_id': self.model_id,
            'finance_id': self.finance_id,
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
            'model_id': newsegsmodel.NewsegsModel.generate_new_id(),
            'finance_id': newsegsfinance.NewsegsFinance.generate_new_id(),
            'last_modified': datetime.datetime.now().isoformat()
        }
    
    @override
    def update(self, config: dict[str, Any] | type[serialisation.T]):
        super().update(config)
        # When coming from json, sets are as list, so will need reassigning
        if not isinstance(self.require_sync, set):
            self.require_sync = set(self.require_sync)

NewsegsMetaModel._excluded_attributes = super(NewsegsMetaModel, NewsegsMetaModel)._excluded_attributes + ('_model', '_finance')
