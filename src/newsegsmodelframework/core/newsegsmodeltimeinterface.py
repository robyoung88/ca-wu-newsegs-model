"""
Interface for serving model start, stop, and time resolution
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod

from newsegsmodelframework.core.timespan.timespan import TimedeltaScalar

class NewsegsModelTimeInterface(metaclass = ABCMeta):
    """
    Interface for serving discrete time modelling information.
    """
    @abstractmethod
    def get_default_timestep(self) -> TimedeltaScalar:
        """
        Get the default timestep for discrete time simulations.

        It is not necessary that all modules operate in discrete time, but in all cases
        it is likely that at least some will (i.e. `grid` will naturally operate with respect to
        market closure times). This method is provided for convenience when synchronising
        such modules.

        Returns:
            TimedeltaScalar: The default timestep for discrete time simulations.
        """
    