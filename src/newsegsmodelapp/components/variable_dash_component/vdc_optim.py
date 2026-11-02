"""Creation of the optimisation input of a variable.
"""
from typing import cast

from newsegsmodelframework.newsegsvariable import variable

from newsegsmodelapp.components.variable_dash_component import vdc as var_dc

def create_optim_input(
    var: variable.Variable
):
    """Create the optimisation input of a variable.

    Args:
        var: The variable.

    Returns:
        The input.
    """
    if not var.optim_show:
        return None
    var = cast(variable.NumericScalarVariable, var)
    return var_dc.create_optim_input(var)
