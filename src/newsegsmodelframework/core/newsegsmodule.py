"""
Abstract base class for NewsegsResult-returning NewsegsComponents within a NewsegsModel
"""
from __future__ import annotations

from abc import abstractmethod
import datetime

from typing import Optional
import warnings

from newsegsmodelframework.core import newsegscomponent
from newsegsmodelframework.core.newsegsmodelinterface import NewsegsModelInterface
from newsegsmodelframework.core.timespan import TimeSpan
from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult

class NewsegsModule(newsegscomponent.NewsegsComponent):
    """
    Abstract base class for modules that run within a Newsegs model.

    Subclasses should implement the abstract run() method to perform a
    computation over a given TimeSpan and return a NewsegsModuleResult.

    This class provides common plumbing including tracking the associated
    NewsegsModelInterface instance, a "dirty" flag that indicates whether
    the module configuration has changed since the last run, and recording
    the last run time.
    """

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'NewsegsModule'
    _excluded_attributes = newsegscomponent.NewsegsComponent._excluded_attributes.union({'_model'})

    _model: NewsegsModelInterface

    def __init__(self, *args, model: Optional[NewsegsModelInterface] = None, **kwargs):
        super().__init__(*args, **kwargs)
        if model is not None:
            self.model = model

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
   
    # NB - model is not a ComponentProperty in order to avoid circular references
    @property
    def model(self) -> NewsegsModelInterface:
        """
        The callback model associated with the module
        """
        if not hasattr(self, '_model'):
            raise AttributeError('model has not been set')
        return self._model

    @model.setter
    def model(self, model: NewsegsModelInterface):
        self._model = model

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self.modified

    @dirty.setter
    def dirty(self, val:bool) -> None:
        warnings.warn('Setting of dirty parameter is deprecated', DeprecationWarning)
        if val:
            self._config._revision += 1
        else:
            self._config._revision = self._config._last_syncronised
        self._dirty = val

