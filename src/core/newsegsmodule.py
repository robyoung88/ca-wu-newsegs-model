from __future__ import annotations

from abc import ABC, ABCMeta, abstractmethod
import copy
import datetime
from collections.abc import Sequence
import uuid
from functools import lru_cache
from typing import Any
import warnings

import numpy as np
import pandas as pd

from core import newsegscomponent
from core import environmentserverinterface
from core.newsegsmodelinterface import NewsegsModelInterface
from core.timespan import TimeSpan, RegTimeSpan
from core.newsegsmoduleresult import NewsegsModuleResult
from util import classfuncs



class NewsegsModule(newsegscomponent.NewsegsComponent):
    """
    Basic abstract class serving module results
    """

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'NewsegsModule'

    _dirty = True
    _model: NewsegsModelInterface

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    @abstractmethod
    def run(
        self,
        timespan:TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> NewsegsModuleResult:
        if run_start is None:
            run_start = datetime.datetime.now()
        self.last_run = run_start
        # Returns none as this is still abstract
   
    @property
    def model(self) -> NewsegsModelInterface:
        """
        The callback model associated with the module
        """
        if hasattr(self, '_model'):
            return self._model
        raise AttributeError('model has not been set')

    @model.setter
    def model(self, model: NewsegsModelInterface):
        try:
            current_mod = self.model
        except AttributeError:
            current_mod = None
        if current_mod is None or not(current_mod == model):
            self._dirty = self._dirty or True
        self._model = model

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self._dirty

    @dirty.setter
    def dirty(self, val:bool) -> None:
        self._dirty = val

NewsegsModule._excluded_attributes = super(NewsegsModule, NewsegsModule)._excluded_attributes + ('_model',)
