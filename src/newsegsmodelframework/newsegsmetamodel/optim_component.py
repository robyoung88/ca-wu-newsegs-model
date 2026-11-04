"""Configuration of the optimisation of a metamodel: the method and the statistic to optimise.

The bounds of each variable are held by the variable itself (`Variable.optim_min`, `optim_max`);
this component holds the settings which apply to the optimisation as a whole.

It lives with the metamodel, rather than in `newsegssensitivity`, as that package imports the
metamodel and so cannot be imported by it.
"""
from typing import Literal, get_args, override

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent
from newsegsmodelframework.core.trackeddata import DataWithRevision, revision_dataclass

__all__ = [
    'OptimComponent', 'OptimComponentConfig',
    'OPTIM_TARGET_STATISTICS', 'OPTIM_TARGET_STATISTIC_LABELS', 'OPTIMISATION_METHODS',
]

OPTIM_TARGET_STATISTIC = Literal[
    'net_present_value_discounted',
    'net_present_value_undiscounted',
]

OPTIM_TARGET_STATISTICS = get_args(OPTIM_TARGET_STATISTIC)

OPTIM_TARGET_STATISTIC_LABELS = {
    'net_present_value_undiscounted': 'NPV (undiscounted)',
    'net_present_value_discounted': 'NPV (discounted)'
}

OPTIMISATION_METHOD = Literal[
    'Nelder-Mead',
    'L-BFGS-B',
    'TNC',
    'SLSQP',
    'Powell'
]

OPTIMISATION_METHODS = get_args(OPTIMISATION_METHOD)


@revision_dataclass
class OptimComponentConfig(DataWithRevision):
    """Configuration of the optimisation of a metamodel.

    Attributes:
        method: The scipy optimisation method; one of `OPTIMISATION_METHODS`.
        statistic: The statistic to maximise; one of `OPTIM_TARGET_STATISTICS`.
    """
    method: OPTIMISATION_METHOD = 'Nelder-Mead'
    statistic: OPTIM_TARGET_STATISTIC = 'net_present_value_discounted'


class OptimComponent(NewsegsComponent):
    """A container for the optimisation settings of a metamodel"""

    component_type = 'optim'

    @override
    def _generate_config(self, *args, **kwargs) -> OptimComponentConfig:
        return OptimComponentConfig(*args, **kwargs)
    _config: OptimComponentConfig # pyright: ignore[reportIncompatibleVariableOverride]

    def __init__(
        self,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
