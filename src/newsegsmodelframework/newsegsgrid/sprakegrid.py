"""Provides implementation of NewsegsGrid for Sprake Model."""
from __future__ import annotations
import copy
from collections.abc import Mapping
import datetime
from typing_extensions import override
from numbers import Number
from functools import singledispatchmethod

import numpy as np
import numpy.typing as npt

from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.newsegsgrid.newsegsgrid import NewsegsGrid
from newsegsmodelframework.util import classfuncs
from newsegsmodelframework.core import newsegsmodule
from newsegsmodelframework.core import timespan as modtimespan
from newsegsmodelframework.newsegsmodel import newsegsmodel

class SprakeGridResult(NewsegsModuleResult):
    """Container for results of SprakeGrid Module."""
    def __init__(
        self,
        *args,
        timespan: modtimespan.RegTimeSpan,
        import_unit_cost:np.ndarray[tuple[int], np.dtype[np.number]],
        export_unit_cost:np.ndarray[tuple[int], np.dtype[np.number]],
        **kwargs,
    ) -> None:
        super().__init__(*args, **kwargs)
        self._timespan = copy.copy(timespan)
        self.set_import_cost(import_unit_cost)
        self.set_export_cost(export_unit_cost)

    def get_timespan(self) -> modtimespan.RegTimeSpan:
        return self._timespan
    @property
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """
        Grid should never be metered - it provides pricing signals only
        """
        return np.empty((0,0))

    @property
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        """
        The DSM signals in a SprakeGridResult are simply the undiscounted per-unit import and export costs
        """
        minlength = np.min((len(self._import), len(self._export)))
        o_arr = np.empty((2, minlength), dtype=np.float64)
        o_arr[0,:] = self._import
        o_arr[1,:] = self._export
        return o_arr

    def get_meter_names(self):
        return ()

    def get_meter_types(self):
        return ()

    def get_dsm_names(self):
        return ('per_unit_import', 'per_unit_export')
    
    def get_dsm_types(self):
        return ('import', 'export')

    def set_import_cost(self, import_unit_cost:npt.ArrayLike) -> None:
        self._import = np.asarray(import_unit_cost).flatten()

    def set_export_cost(self, export_unit_cost:npt.ArrayLike) -> None:
        self._export = np.asarray(export_unit_cost).flatten()


class SprakeGrid(NewsegsGrid):
    """Implementation of NewsegsGrid for Sprake Model."""

    _name = "Sprake Grid Module"

    @singledispatchmethod
    def __init__(
        self,
        import_per_unit: Number | SprakeGrid,
        export_per_unit: Number | None = None,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None
    ) -> None:
        raise ValueError('First argument must be a number or a SprakeGrid, is %s', type(import_per_unit))

    # Copy constructor is registered underneath class definition for late-bind.
    
    @__init__.register(Number)
    def _from_Number(
        self,
        import_per_unit: Number,
        export_per_unit: Number = 0.07,
        name: str | None = None,
        model: newsegsmodel.NewsegsModel | None = None
    ) -> None:
        super().__init__()
        self.import_rate = import_per_unit
        self.export_rate = export_per_unit

        if name is not None:
            self.name = name
        
        if model is not None:
            self.model = model

    @classmethod
    def from_none(cls):
        return cls(0.20)

    @property
    def import_rate(self) -> float:
        return self._import_rate

    @import_rate.setter
    def import_rate(self, rate:float):
        self._import_rate = rate
        self.dirty = True

    @property
    def export_rate(self) -> float:
        return self._export_rate

    @export_rate.setter
    def export_rate(self, rate:float):
        self._export_rate = rate
        self.dirty = True

    def run(
        self, 
        timespan: modtimespan.TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> SprakeGridResult:
        super().run(timespan, run_start)
        if not isinstance(timespan, modtimespan.RegTimeSpan):
            if self.model is None:
                raise ValueError("Grid module requires a model to serve timestep")
            timespan = modtimespan.RegTimeSpan(timespan)
            timespan.timestep = self.model.get_default_timestep()
        
        model_length = timespan.n_node

        self.dirty = False
        return SprakeGridResult(
            self.id,
            datetime.datetime.now(),
            timespan = timespan,
            import_unit_cost = self.import_rate * np.ones(model_length),
            export_unit_cost = self.export_rate * np.ones(model_length)
        )

# SprakeGrid copy constructor
@SprakeGrid.__init__.register(SprakeGrid) # pyright: ignore[reportFunctionMemberAccess]
def _SprakeGrid_from_other(
    self,
    other: SprakeGrid
) -> None:
    super(SprakeGrid, self).__init__()
    self.import_rate = other.import_rate
    self.export_rate = other.export_rate
    self.name = other.name
    try:
        self.model = other.model
    except AttributeError:
        pass
