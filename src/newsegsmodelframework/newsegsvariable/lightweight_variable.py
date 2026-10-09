from dataclasses import KW_ONLY
from typing import Any

from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass


@revision_dataclass
class LightweightVariable(DataWithRevision):
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
    parameterisation_index: int

    dsa_show: bool
    dsa_selectable: bool
    dsa_selected: bool
    dsa_lower: Any | None
    dsa_upper: Any | None
    dsa_value_lower: Any | None
    dsa_value_upper: Any | None

    psa_show: bool
    psa_selectable: bool
    psa_selected: bool
    last_std: Any | None
    psa_ci_lower: Any | None
    psa_ci_upper: Any | None

    optim_show: bool
    optim_selectable: bool
    optim_selected: bool
    optim_min: Any | None
    optim_max: Any | None
