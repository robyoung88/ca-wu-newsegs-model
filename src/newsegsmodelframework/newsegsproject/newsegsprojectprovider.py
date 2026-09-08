"""Interface for providing Projects"""

from abc import abstractmethod
from typing import Optional

import pandas as pd

from newsegsmodelframework.core.newsegscomponent import NewsegsComponentProviderInterface, NewsegsComponentPersistenceInterface
from newsegsmodelframework.newsegsproject import NewsegsProject


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
