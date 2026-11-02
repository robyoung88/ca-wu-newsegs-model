"""Variables - statistical characterisations of the parameters of energy and finance models.

See the `variable` module for an explanation of variables, distributions and parameterisations.

Modules:
    variable: `Variable`, its subclasses (one per distribution), and the distributions and
        parameterisations they use.
    lightweight_variable: Lightweight descriptions of a variable, for display and editing.
    update_variable: `update_variable`, which updates one parameter of a variable and reports what changed.
    variableprovider: Interfaces and in-memory implementations for serving variables by id.
"""
from .variable import Variable, VARIABLE_CONSTRUCTORS, VariableConfig, variable_uid
__all__ = [
    'Variable',
    'VARIABLE_CONSTRUCTORS',
    'VariableConfig',
    'variable_uid',
]
