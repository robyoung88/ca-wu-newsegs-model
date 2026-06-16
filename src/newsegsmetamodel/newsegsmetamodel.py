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
from typing import MutableSequence

from newsegsmodel import newsegsmodel
from newsegsfinance import newsegsfinance
from newsegsvariable import variable

class NewsegsMetaModel:

    def __init__(
        self,
        model: newsegsmodel.NewsegsModel,
        finance: newsegsfinance.NewsegsFinance,
        variables: MutableSequence[variable.Variable] = [],
    ):
        self.model = model
        self.finance = finance
        self.variables = variables
    