"""Creation of the PSA input of a variable.
"""

from newsegsmodelapp.components.variable_dash_component import vdc as var_dc
from newsegsmodelframework.newsegsvariable.lightweight_variable import FullLightweightVariable

def create_psa_input(
    var: FullLightweightVariable,
    summary_contents: list | None = None,
    n_configurations: int = 1,
):
    """Create the PSA input of a variable.

    Nothing is created if the variable is not to be shown.

    Args:
        var: The variable.
        summary_contents: The summary of how the configurations' Variables differ (see
            `psa_group_editor.create_psa_sharing_summary_contents`).
        n_configurations: The number of configurations of the project.

    Returns:
        The input, or nothing.
    """
    if not var.psa_show:
        return None
    var_dc.psa_parameter_labels(var.distribution)  # Raises for an unsupported distribution
    return var_dc.create_psa_input_scalar(var, summary_contents, n_configurations)
