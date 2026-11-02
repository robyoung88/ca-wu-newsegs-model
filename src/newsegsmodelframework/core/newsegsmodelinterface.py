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
    """Interface of an energy model.

    A runnable, table-owning component which serves environmental data, holds the results of its modules
    and gives the time over which they are run.
    """
    ...


class NewsegsModelProviderInterface(NewsegsComponentProviderInterface):
    """Provider of energy models.
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
        """Get the model with an id, or models with a sequence of ids.

        Args:
            component_id: Id(s) of the component(s).

        Returns:
            The model, or sequence of models.
        """
        ...

    @abstractmethod
    def duplicate_component(self, component_id: str | NewsegsComponent) -> NewsegsModelInterface:
        """Make a copy of a model with new ids.

        Args:
            component_id: Id(s) of the component(s).

        Returns:
            The new model.
        """
        ...

    @abstractmethod
    def get_default_component(self, component_type: str, index: int = -1) -> NewsegsModelInterface:
        """Get the default model of a type.

        Args:
            component_type: The type of the component (e.g. `model`, `finance`).
            index: Which instance of the component type to return, in the order added; -1 is the most recent.

        Returns:
            The model.
        """
        ...


class NewsegsModelPersistenceInterface(NewsegsComponentPersistenceInterface):
    """Interface for saving models to persistent storage.
    """
    ...
