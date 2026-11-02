"""Interface for providing Projects"""

from abc import abstractmethod
from typing import Literal, Optional, cast

import pandas as pd

from newsegsmodelframework.core.newsegscomponent import NewsegsComponentManagerInterface
from newsegsmodelframework.newsegsproject import NewsegsProject
from newsegsmodelframework.newsegsvariable.variableprovider import VariableManagerInterface

ON_MISSING_OPTION = Literal['last', 'create', 'none']

class NewsegsProjectProviderInterface(NewsegsComponentManagerInterface):
    """Interface of a store and provider of projects, with their sessions and snapshots.
    """
    metamodel_provider: NewsegsComponentManagerInterface
    variable_provider: VariableManagerInterface

    @abstractmethod
    def list_projects(
        self,
        model_type: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> pd.DataFrame:
        """Provide a list of available projects as a pandas dataframe"""

    # REVIEW (unreferenced): no references to `recover_session_project` found in src/, scripts/ or data/.
    @abstractmethod
    def recover_session_project(
        self,
        session_id: Optional[str] = None,
        model_type: Optional[str] = None
    ) -> NewsegsProject:
        """Provide a project for a recovered session."""

    @abstractmethod
    def get_session_project_id(
        self,
        session_id: Optional[str] = None,
        model_type: Optional[str] = None,
        on_missing: ON_MISSING_OPTION = 'last',
    ) -> str:
        """Provide a project id for a recovered session."""

    @abstractmethod
    def set_session_project_id(
        self,
        session_id: str,
        project_id: str,
    ):
        """Set a project id to the acive project of a session"""

    @abstractmethod
    def list_project_snapshots(self, project_id: str) -> pd.DataFrame:
        """Provide a list of available snapshots as a pandas dataframe."""

    @abstractmethod
    def create_project_snapshot(self, project_id: str, snapshot_label: str) -> int:
        """Snapshot the project state."""

    @abstractmethod
    def load_project_snapshot(self, project_id: str, snapshot_id: int) -> NewsegsProject:
        """Recover a snapshot of the project state."""

    @abstractmethod
    def delete_project_snapshot(self, project_id: str, snapshot_id: int):
        """Delete a specific snapshot"""

    def get_project(self, project_id: str) -> NewsegsProject:
        """Get a project by id.

        Args:
            project_id: See the description.

        Returns:
            The project.
        """
        return cast(NewsegsProject, self.get_component(project_id))

    @abstractmethod
    def list_project_metamodel_ids(self, project_id: str) -> tuple[str, ...]:
        """Get a tuple of the ids of the metamodels owned by a project."""

    @abstractmethod
    def get_focussed_metamodel_id(self, project_id: str) -> str:
        """Get the id of the focussed metamodel."""
