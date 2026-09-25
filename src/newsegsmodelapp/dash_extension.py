from typing import Any, Callable, Dict, List, Sequence, override

from dash import Dash
from dash.dash import _default_index
from dash.dependencies import Input, State
from dash.types import RendererHooks

from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestHandlerInterface
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface


class NewsegsDash(Dash):
    @override
    def __init__(
        self,
        *args,
        project_provider: NewsegsProjectProviderInterface,
        results_provider: NewsegsResultProviderInterface,
        request_handler: RequestHandlerInterface,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._project_provider = project_provider
        self._results_provider = results_provider
        self._request_handler = request_handler

    @property
    def project_provider(self) -> NewsegsProjectProviderInterface:
        return self._project_provider

    @property
    def results_provider(self) -> NewsegsResultProviderInterface:
        return self._results_provider

    @property
    def request_handler(self) -> RequestHandlerInterface:
        return self._request_handler
    