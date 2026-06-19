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
import datetime
from typing import Any, Mapping, MutableSequence

from core import newsegscomponent
from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance
from newsegsvariable import variable

class NewsegsMetaModel(newsegscomponent.NewsegsComponent):

    model_id: str
    finance_id: str

    _name = 'NewSEGS MetaModel'
    _version = '0.0.1'
    _id_prefix = 'metam'
    _last_modified: datetime.datetime = datetime.datetime.now()

    def __init__(
        self,
        model: newsegsmodel.NewsegsModel,
        finance: newsegsfinance.NewsegsFinance,
        variables: MutableSequence[variable.Variable] = [],
    ):
        self.model = model
        self.finance = finance
        self.variables = variables
    
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

NewsegsMetaModel._excluded_attributes = super(NewsegsMetaModel, NewsegsMetaModel)._excluded_attributes + ('_model', '_finance')
