# Abstract base class for NewSEGS Generation module

from abc import abstractmethod

import pandas as pd

from src.core import NewsegsModule
from src.core import ABCNewsegsModuleResult
from src.core.newsegsmodule import filter_meters

class NewsegsGeneration(NewsegsModule):
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
