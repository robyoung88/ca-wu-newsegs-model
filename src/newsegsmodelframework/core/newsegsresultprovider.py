from abc import ABCMeta, abstractmethod
from typing import Any

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent

class NewsegsResultProviderInterface(metaclass = ABCMeta):
    @abstractmethod
    def upsert_result(self,
        result_type: str,
        parent_component: NewsegsComponent,
        result_object: object
    ):
        """Add or update a result to the provider."""

    def get_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent,
        allow_stale: bool = True
    ) -> tuple[Any, str] | tuple[None, None]:
        """Retrieve a result from the provider. 
        
        If allow_stale is true, will return the latest result if none matching the revision string are found.
        
        Returns:
            tuple[object, str] - The result and the revision string of the component generating the result.
            None if no applicable results are found.
        """