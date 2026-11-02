"""Requesthanderinterface module.

TODO: Describe the purpose of the module.
"""
from abc import ABCMeta, abstractmethod
from typing import Optional, Sequence, overload

from newsegsmodelapp import registers
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface

class RequestHandlerInterface(metaclass = ABCMeta):
    """Manages the creation, status updating, and deletion of (run) requests"""

    @abstractmethod
    def add_request(
        self,
        procedure_name: str,
        active_project_id: str,
        project_provider: NewsegsProjectProviderInterface,
        procedure_class: Optional[str] = None,
        config: Optional[dict] = None,
        triggering_request: Optional[registers.RunRequest] = None,
    ) -> registers.RunRequest:
        """Add a new request to the dispatch list.
        
        Returns:
            [RunRequest] The full RunRequest object for the added request.
        """

    @overload
    def get_request(self, request_id: int) -> registers.RunRequest:
        ...

    @overload
    def get_request(self, request_id: Sequence[int]) -> list[registers.RunRequest]:
        ...

    @abstractmethod
    def get_request(
        self,
        request_id: int | Sequence[int]
    ) -> registers.RunRequest | list[registers.RunRequest]:
        """Get one or more requests by id."""

    def get_active_requests(
        self,
        active_project_id: str | None = None
    ) -> list[registers.RunRequest]:
        """A list of RunRequests requiring management.
        
        Requests will either have status:
            - "AWAITING DISPATCH" (i.e. requiring a new run generated)
            or
            - "DISPATCHED" (i.e. with a run assigned and without having processed a completion of that run)
        """

    @abstractmethod
    def get_new_requests(
        self,
        active_project_id: str | None = None,
    ) -> list[registers.RunRequest]:
        """Get a list of the requests which have not been dispatched.
        
        Returns:
            [list[RunRequest]] Requests not dispatched.
        """

    @abstractmethod
    def mark_dispatched(
        self,
        request_id: int | Sequence[int],
        run_id: int | None | Sequence[int | None],
    ):
        """Alter the dispatch status of one or more requests."""

    @abstractmethod
    def mark_completed(
        self,
        request_id: int | Sequence[int],
        completed: bool = True
    ):
        """Alter the completion status of one or more requests.
        
        Caution that after marked complete, requests may no longer be present.
        """

    @abstractmethod
    def increment_failure(
        self,
        request_id: int
    ) -> bool:
        """Increment the number of failures for a request.
        
        Returns:
            [bool] - False if retries exceeds maximum number of retries.
        """
