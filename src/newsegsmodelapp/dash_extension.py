"""The `NewsegsDash` app, which holds the providers used by the pages and callbacks.
"""
from typing import override

from dash import Dash

from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestHandlerInterface
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface


class NewsegsDash(Dash):
    """A Dash app which holds the providers used by the pages and callbacks.

    Callbacks reach the providers through the app instead of through globals.

    Args:
        project_provider: Provider of projects, metamodels and variables.
        results_provider: Provider of results.
        request_handler: Creator and monitor of requests for background procedures.
    """
    @override
    def __init__(
        self,
        *args,
        project_provider: NewsegsProjectProviderInterface,
        results_provider: NewsegsResultProviderInterface,
        request_handler: RequestHandlerInterface,
        #background_callback_manager: DiskcacheManager | CeleryManager,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._project_provider = project_provider
        self._results_provider = results_provider
        self._request_handler = request_handler
        #self._bcm = background_callback_manager

    @property
    def project_provider(self) -> NewsegsProjectProviderInterface:
        """Provider of projects, metamodels and variables.
        """
        return self._project_provider

    @property
    def results_provider(self) -> NewsegsResultProviderInterface:
        """Provider of results.
        """
        return self._results_provider

    @property
    def request_handler(self) -> RequestHandlerInterface:
        """Creator and monitor of requests for background procedures.
        """
        return self._request_handler

    # @property
    # def background_callback_manager(self) -> DiskcacheManager | CeleryManager:
    #     return self._bcm
    