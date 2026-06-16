# Abstract base class for NewSEGS Generation module

from abc import abstractmethod
from typing import Sequence

import pandas as pd

from core import NewsegsModule
from core import ABCNewsegsModuleResult
from core import location as modlocation
from core.newsegsmodule import filter_meters

class NewsegsGeneration(NewsegsModule):
    
    @property
    @abstractmethod
    def location(self) -> modlocation.Location | Sequence[modlocation.Location]:
        """
        Read back the location of the generators / power plants.

        Generally, the location will itself be an attribute of the generator
        and so cannot be accessed until a generator is assigned.
        """
    
    @location.setter
    @abstractmethod
    def location(self, loc: modlocation.Location) -> None:
        ...
    
def get_generation_meters(
    gen_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """
    Extract generation meters from a generation module results.

    Also augments with total generation export.
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
