from abc import ABCMeta, abstractmethod
from typing import Any, Optional

from newsegsmodelframework.core.newsegscomponent import NewsegsComponent

class NewsegsResultProviderInterface(metaclass = ABCMeta):
    @abstractmethod
    def upsert_result(self,
        result_type: str,
        parent_component: NewsegsComponent,
        result_object: object,
        mark_stale: bool = False,
        request: Optional[Any] = None,
    ):
        """Add or update a result to the provider."""

    @abstractmethod
    def get_result(
        self,
        result_type: str,
        parent_component: NewsegsComponent | str,
        allow_stale: bool = True,
        revision: Optional[int] = None,
    ) -> tuple[Any, int] | tuple[None, None]:
        """Retrieve a result from the provider. 
        
        If allow_stale is true, will return the latest result if none matching the revision are found.
        
        Returns:
            tuple[object, int] - The result and the revision of the component generating the result.
            None if no applicable results are found.
        """

    @abstractmethod
    def get_request_result(
        self,
        result_type: str,
        request_id: int,
        parent_component: Optional[NewsegsComponent | str] = None,
    ) -> tuple[Any, int] | tuple[None, None]:
        """Retrieve a result produced for a specific request.

        For single results per request, no need to specify a parent_component;
        If results are one per metamodel, include the parent component or a ValueError will be
        thrown for multiple returned results.

        Returns:
            tuple[object, int] - The result and the revision of the component generating the result.
            None, None if no applicable results are found.
        """
