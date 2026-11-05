"""Creation of the DSA input of a variable.
"""

from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

from newsegsmodelapp.components.variable_dash_component import vdc as var_dc

_SCALAR_DISTRIBUTIONS = ('constant', 'numeric_constant', 'normal', 'beta', 'gamma')

def create_dsa_input(
    var: variable.Variable | FullLightweightVariable,
    summary_contents: list | None = None,
    n_configurations: int = 1,
):
    """Create the DSA input of a variable.

    Nothing is created if the variable is not to be shown.

    Args:
        var: The variable.
        summary_contents: The summary of how the configurations' Variables differ (see
            `dsa_group_editor.create_dsa_sharing_summary_contents`).
        n_configurations: The number of configurations of the project.

    Returns:
        The input, or nothing.
    """
    if not var.dsa_show:
        return []
    distribution = var.distribution if isinstance(var, FullLightweightVariable) else var.distribution.distribution
    if distribution not in _SCALAR_DISTRIBUTIONS:
        raise ValueError(f'Distribution {distribution} not currently supported')
    return var_dc.create_dsa_input_scalar(var, summary_contents, n_configurations) # pyright: ignore[reportArgumentType]
