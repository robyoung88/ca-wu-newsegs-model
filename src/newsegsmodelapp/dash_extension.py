from typing import Any, Callable, Dict, List, Sequence, override

from dash import Dash
from dash.dash import _default_index
from dash.dependencies import Input, State
from dash.types import RendererHooks

from newsegsmodelframework.newsegsproject.newsegsprojectprovider import NewsegsProjectProviderInterface


class NewsegsDash(Dash):
    @override
    def __init__(
        self,
        *args,
        project_provider: NewsegsProjectProviderInterface,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self._project_provider = project_provider

    @property
    def project_provider(self) -> NewsegsProjectProviderInterface:
        return self._project_provider
    