"""Interface for providing Projects"""

from abc import abstractmethod
from typing import Literal, Optional

import pandas as pd

from newsegsmodelframework.core.newsegscomponent import NewsegsComponentProviderInterface, NewsegsComponentPersistenceInterface
from newsegsmodelframework.newsegsproject import NewsegsProject

ON_MISSING_OPTION = Literal['last', 'create', 'none']

class NewsegsProjectProviderInterface(NewsegsComponentProviderInterface, NewsegsComponentPersistenceInterface):
    @abstractmethod
    def list_projects(
        self,
        model_type: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> pd.DataFrame:
        """Provide a list of available projects as a pandas dataframe"""

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

