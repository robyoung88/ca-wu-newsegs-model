"""
Abstract base class defining the minimal interface for a NewsegsModel
"""
from __future__ import annotations
from abc import abstractmethod
from typing import overload

from useful_types import SequenceNotStr

from newsegsmodelframework.core import environmentserverinterface
from newsegsmodelframework.core import resultsserverinterface
from newsegsmodelframework.core import RunnableNewsegsComponent
from newsegsmodelframework.core import newsegsmodeltimeinterface
from newsegsmodelframework.core.newsegscomponent import NewsegsComponentPersistenceInterface, NewsegsComponentProviderInterface

class NewsegsModelInterface(
    environmentserverinterface.EnvironmentServerInterface,
    resultsserverinterface.ResultServerInterface,
    newsegsmodeltimeinterface.NewsegsModelTimeInterface,
    RunnableNewsegsComponent,
    
):
    ...


class NewsegsModelProviderInterface(NewsegsComponentProviderInterface):
    @overload
    @abstractmethod
    def get_component(self, component_id: str) -> NewsegsModelInterface:
        ...

    @overload
    def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsModelInterface]:
        ...

    @abstractmethod
    def get_component(self, component_id: str | SequenceNotStr[str]) -> NewsegsModelInterface | SequenceNotStr[NewsegsModelInterface]:
        ...

    @abstractmethod
    def duplicate_component(self, component_id: str) -> NewsegsModelInterface:
        ...

    @abstractmethod
    def get_default_component(self, component_type: str, index: int = -1) -> NewsegsModelInterface:
        ...


class NewsegsModelPersistenceInterface(NewsegsComponentPersistenceInterface):
    ...
