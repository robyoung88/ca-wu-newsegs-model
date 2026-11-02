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
    """Interface of a finance model: a runnable, table-owning component.
    """
    ...


class NewsegsFinanceProviderInterface(NewsegsComponentProviderInterface):
    """Provider of finance models.
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
        """Get the finance model with an id, or models with a sequence of ids.

        Args:
            component_id: Id(s) of the component(s).

        Returns:
            The finance model, or sequence of finance models.
        """
        ...

    @abstractmethod
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsFinanceInterface:
        """Make a copy of a finance model with new ids.

        Args:
            component_id: Id(s) of the component(s).

        Returns:
            The new finance model.
        """
        ...

    @abstractmethod
    def get_default_component(self, component_type: str, index: int = -1) -> NewsegsFinanceInterface:
        """Get the default finance model of a type.

        Args:
            component_type: The type of the component (e.g. `model`, `finance`).
            index: Which instance of the component type to return, in the order added; -1 is the most recent.

        Returns:
            The finance model.
        """
        ...


class NewsegsFinancePersistenceInterface(NewsegsComponentPersistenceInterface):
    """Interface for saving finance models to persistent storage.
    """
    ...
