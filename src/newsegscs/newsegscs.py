# Abstract base class for NewSEGS Consumption and Storage module

from abc import abstractmethod

import pandas as pd

from src.core import NewsegsModule
from src.core import ABCNewsegsModuleResult
from src.core.newsegsmodule import filter_meters

class NewsegsCS(NewsegsModule):
    ...

def get_consumption_meters(
    cs_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """
    Extract final consumption meters from a cs module results.

    Also augments with total consumption 'consumption'
    """
    cons_meters = filter_meters(cs_results, 'load')
    cons_data = (
        cs_results.meters_to_pandas()
        .loc[:, cons_meters]
        .assign(
            consumption = lambda df: df.apply(sum, axis=1)
        )
    )
    return cons_data

def get_storage_import_meters(
    cs_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """
    Extract final to-storage import meters from a cs module results.

    Also augments with total storage import 'storage_import'.
    NB, this may overwrite any existing 'storage_import' meter.
    """
    cons_meters = filter_meters(cs_results, 'import_storage')
    cons_data = (
        cs_results.meters_to_pandas()
        .loc[:, cons_meters]
        .assign(
            storage_import = lambda df: df.apply(sum, axis=1)
        )
    )
    return cons_data

def get_storage_export_meters(
    cs_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """
    Extract final from-storage export meters from a cs module results.

    Also augments with total storage import 'storage_export'.
    NB, this may overwrite any existing 'storage_export' meter.
    """
    cons_meters = filter_meters(cs_results, 'export_storage')
    cons_data = (
        cs_results.meters_to_pandas()
        .loc[:, cons_meters]
        .assign(
            storage_export = lambda df: df.apply(sum, axis=1)
        )
    )
    return cons_data

def get_storage_loss_meters(
    cs_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """
    Extract loss meters from a cs module results.

    Also augments with total storage loss 'storage_loss'.
    NB, this may overwrite any existing 'storage_loss' meter.
    """
    cons_meters = filter_meters(cs_results, 'loss')
    cons_data = (
        cs_results.meters_to_pandas()
        .loc[:, cons_meters]
        .assign(
            storage_loss = lambda df: df.apply(sum, axis=1)
        )
    )
    return cons_data

def get_site_import_meters(
    cs_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """ 
    Extract site grid import meters from a cs module results.

    Also augments with a total grid_imports 'grid_import'.
    NB, this may overwrite any existing 'grid_import' meter.
    """
    cons_meters = filter_meters(cs_results, 'import')
    cons_data = (
        cs_results.meters_to_pandas()
        .loc[:, cons_meters]
        .assign(
            grid_import = lambda df: df.apply(sum, axis=1)
        )
    )
    return cons_data

def get_site_export_meters(
    cs_results: ABCNewsegsModuleResult
) -> pd.DataFrame:
    """ 
    Extract site grid export meters from a cs module results.

    Also augments with a total grid_exports 'grid_export'.
    NB, this may overwrite any existing 'grid_export' meter.
    """
    cons_meters = filter_meters(cs_results, 'export')
    cons_data = (
        cs_results.meters_to_pandas()
        .loc[:, cons_meters]
        .assign(
            grid_export = lambda df: df.apply(sum, axis=1)
        )
    )
    return cons_data
