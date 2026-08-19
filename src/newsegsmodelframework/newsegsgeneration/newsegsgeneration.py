"""Provides abstract base class for NewSEGS Generation Module."""

from abc import abstractmethod
from typing import Sequence

import pandas as pd

from newsegsmodelframework.core import NewsegsModule
from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.core.newsegsmoduleresult import filter_meters
from newsegsmodelframework.core import location as modlocation

class NewsegsGeneration(NewsegsModule):
    """Abstract base class for NewSEGS Generation Module."""
    module_type = 'generation'
    
    @property
    @abstractmethod
    def location(self) -> modlocation.Location | Sequence[modlocation.Location]:
        """Read back the location of the generators / power plants.

        Generally, the location will itself be an attribute of the generator
        and so cannot be accessed until a generator is assigned.

        Returns:
            Location or sequence of locations of the generators / power plants.
        """
    
    @location.setter
    @abstractmethod
    def location(self, loc: modlocation.Location) -> None:
        ...
    
def get_generation_meters(
    gen_results: NewsegsModuleResult
) -> pd.DataFrame:
    """Extract generation meters from a generation module results.

    Also augments the returned data with total generation export.

    Args:
        gen_results: Results from a generation module.

    Returns:
        Data frame containing generation meter values and a total export column.
    """
    gen_meters = filter_meters(gen_results, 'export')
    gen_data = (
        gen_results.meters_to_pandas()
        .loc[:, gen_meters]
        .assign(
            generation_export = lambda df: df.apply(sum, axis=1)
        )
    )
    return gen_data
