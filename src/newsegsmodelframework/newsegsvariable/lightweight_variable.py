"""Lightweight descriptions of a variable, for display and editing without the machinery of a `Variable`.
"""
from dataclasses import KW_ONLY
from typing import Any

from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass


@revision_dataclass
class LightweightVariable(DataWithRevision):
    """Identifying and display information of a variable, with the parameters last given by the user.

    Holds the id, the varid (`interface_section`, `interface_key`, `interface_subindex`), the variable
    type and distribution, the label, icon and unit, the limits and step of the input field and
    the number of decimal places to display. The last deterministic value and the first two raw
    parameters are included so that the interface can be drawn without constructing the `Variable`.
    """
    id: str
    varid: str
    interface_section: str
    interface_key: str
    interface_subindex: int

    variable_type: str
    distribution: str
    
    label: str
    icon_name: str
    unit: str

    interface_min: float | None
    interface_max: float | None
    interface_step: float | None
    formatter_dp: int | None
    
    distribution: str
    _: KW_ONLY
    last_deterministic_value: Any | None = None
    raw_parameter_0: Any | None = None
    raw_parameter_1: Any | None = None

@revision_dataclass
class FullLightweightVariable(DataWithRevision):
    """The control information of a variable for DSA, PSA and optimisation, in lightweight form.

    Holds which analyses the variable is selectable and selected for and is shown on, the DSA bounds
    and the values at those bounds, the standard deviation and confidence interval for PSA, and the
    limits for optimisation.
    """
    parameterisation_index: int
    component_type: str

    dsa_show: bool
    dsa_selectable: bool
    dsa_selected: bool
    dsa_bounds_type: str
    dsa_lower: Any | None
    dsa_upper: Any | None
    dsa_value_lower: Any | None
    dsa_value_upper: Any | None

    psa_show: bool
    psa_selectable: bool
    psa_selected: bool
    last_std: Any | None = None
    psa_ci_lower: Any | None = None
    psa_ci_upper: Any | None = None

    optim_show: bool = False
    optim_selectable: bool = True
    optim_selected: bool = False
    optim_min: Any | None = None
    optim_max: Any | None = None

    @property
    def configuration_type(self) -> str:
        """Whether the variable sets a parameter of the `model` or the `finance` model.

        `'finance'` if the component type is `financedata`, otherwise `'model'`.
        """
        if self.component_type in ('financedata'):
            return 'finance'
        return 'model'
