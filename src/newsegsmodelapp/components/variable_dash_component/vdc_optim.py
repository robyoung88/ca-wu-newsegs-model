"""Vdc optim module.

TODO: Describe the purpose of the module.
"""
from typing import cast

from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.components.variable_dash_component import vdc as var_dc

def create_optim_input(
    var: variable.Variable
):
    """Create optim input.

    TODO: Add a description.

    Args:
        var: TODO.

    Returns:
        TODO.
    """
    if not var.optim_show:
        return None
    var = cast(variable.NumericScalarVariable, var)
    return var_dc.create_optim_input(var)
