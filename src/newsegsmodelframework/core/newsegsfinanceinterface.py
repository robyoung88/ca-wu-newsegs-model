"""
Abstract base class defining the minimal interface for a NewsegsFinance
"""
from __future__ import annotations
from abc import abstractmethod
from typing import overload

from useful_types import SequenceNotStr

from newsegsmodelframework.core.newsegscomponent import TableOwningRunnableNewsegsComponent, NewsegsComponent
from newsegsmodelframework.core.newsegscomponent import NewsegsComponentPersistenceInterface, NewsegsComponentProviderInterface

class NewsegsFinanceInterface(
    TableOwningRunnableNewsegsComponent,
):
    """Newsegs Finance Interface.

    TODO: Add a description.
    """
    ...


class NewsegsFinanceProviderInterface(NewsegsComponentProviderInterface):
    """Newsegs Finance Provider Interface.

    TODO: Add a description.
    """
    @overload
    @abstractmethod
    def get_component(self, component_id: str) -> NewsegsFinanceInterface:
        ...

    @overload
    def get_component(self, component_id: SequenceNotStr[str]) -> SequenceNotStr[NewsegsFinanceInterface]:
        ...

    @abstractmethod
    def get_component(self, component_id: str | SequenceNotStr[str]) -> NewsegsFinanceInterface | SequenceNotStr[NewsegsFinanceInterface]:
        """Get component.

        TODO: Add a description.

        Args:
            component_id: TODO.

        Returns:
            TODO.
        """
        ...

    @abstractmethod
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsFinanceInterface:
        """Duplicate component.

        TODO: Add a description.

        Args:
            component_id: TODO.

        Returns:
            TODO.
        """
        ...

    @abstractmethod
    def get_default_component(self, component_type: str, index: int = -1) -> NewsegsFinanceInterface:
        """Get default component.

        TODO: Add a description.

        Args:
            component_type: TODO.
            index: TODO.

        Returns:
            TODO.
        """
        ...


class NewsegsFinancePersistenceInterface(NewsegsComponentPersistenceInterface):
    """Newsegs Finance Persistence Interface.

    TODO: Add a description.
    """
    ...
