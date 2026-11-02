"""
Interface for serving NewsegsModel results data
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod

from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult

class ResultServerInterface(metaclass = ABCMeta):
    """Interface of an object, such as an energy model, which serves the results of the runs of its modules.
    """
    @abstractmethod
    def get_generation_result(self) -> NewsegsModuleResult:
        """
        Access the result of a generation module run
        """
    
    @abstractmethod
    def get_grid_result(self) -> NewsegsModuleResult:
        """
        Access the result of a grid module run
        """
    
    @abstractmethod
    def get_consumption_storage_result(self) -> NewsegsModuleResult:
        """
        Access the result of a consumption/storage module run
        """
