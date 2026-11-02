"""
Abstract base class defining the minimal interface for a NewsegsModel
"""
from __future__ import annotations
from abc import abstractmethod
from typing import overload

from useful_types import SequenceNotStr

from newsegsmodelframework.core import environmentserverinterface
from newsegsmodelframework.core import resultsserverinterface
from newsegsmodelframework.core import RunnableNewsegsComponent, NewsegsComponent
from newsegsmodelframework.core import newsegsmodeltimeinterface
from newsegsmodelframework.core.newsegscomponent import NewsegsComponentPersistenceInterface, NewsegsComponentProviderInterface, TableOwningRunnableNewsegsComponent

class NewsegsModelInterface(
    environmentserverinterface.EnvironmentServerInterface,
    resultsserverinterface.ResultServerInterface,
    newsegsmodeltimeinterface.NewsegsModelTimeInterface,
    TableOwningRunnableNewsegsComponent,
):
    """Newsegs Model Interface.

    TODO: Add a description.
    """
    ...


class NewsegsModelProviderInterface(NewsegsComponentProviderInterface):
    """Newsegs Model Provider Interface.

    TODO: Add a description.
    """
    @overload
    @abstractmethod
    def get_component(self, component_id: str) -> NewsegsModelInterface:
        ...

    @overload
    def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsModelInterface]:
        ...

    @abstractmethod
    def get_component(self, component_id: str | SequenceNotStr[str]) -> NewsegsModelInterface | SequenceNotStr[NewsegsModelInterface]:
        """Get component.

        TODO: Add a description.

        Args:
            component_id: TODO.

        Returns:
            TODO.
        """
        ...

    @abstractmethod
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsModelInterface:
        """Duplicate component.

        TODO: Add a description.

        Args:
            component_id: TODO.

        Returns:
            TODO.
        """
        ...

    @abstractmethod
    def get_default_component(self, component_type: str, index: int = -1) -> NewsegsModelInterface:
        """Get default component.

        TODO: Add a description.

        Args:
            component_type: TODO.
            index: TODO.

        Returns:
            TODO.
        """
        ...


class NewsegsModelPersistenceInterface(NewsegsComponentPersistenceInterface):
    """Newsegs Model Persistence Interface.

    TODO: Add a description.
    """
    ...
