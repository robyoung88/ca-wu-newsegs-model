from __future__ import annotations
from collections.abc import Mapping
import numpy as np
import numpy.typing as npt

from src.newsegsgrid import NewsegsGrid
from src.core import ABCNewsegsModuleResult
from src.core import RegTimeSpan

class SprakeGridResult(ABCNewsegsModuleResult):
    def __init__(self,
                 import_unit_cost:np.ndarray[tuple[int], np.dtype[np.number]],
                 export_unit_cost:np.ndarray[tuple[int], np.dtype[np.number]]
                 ) -> None:
        self.set_import_cost(import_unit_cost)
        self.set_export_cost(export_unit_cost)

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

    _default_name = "Sprake Grid Module"

    def __init__(self, import_per_unit:float=0.20, export_per_unit:float=0.07):
        self._name = self._default_name
        self.import_rate = import_per_unit
        self.export_rate = export_per_unit

    @property
    def model(self) -> NewsegsModel|None:
        return self._model

    @model.setter
    def model(self, model:NewsegsModel) -> None:
        self._model = model

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, name:str) -> None:
        self._name = name

    @property
    def import_rate(self) -> float:
        return self._import_rate

    @import_rate.setter
    def import_rate(self, rate:float):
        self._import_rate = rate

    @property
    def export_rate(self) -> float:
        return self._export_rate

    @export_rate.setter
    def export_rate(self, rate:float):
        self._export_rate = rate

    def run(self, timespan:TimeSpan):
        if not isinstance(timespan, RegTimeSpan):
            if self.model is None:
                raise ValueError("Grid module requires a model to serve timestep")
            timespan = RegTimeSpan(timespan)
            timespan.timestep = self.model.get_default_timestep()
        
        model_length = timespan.n_node
        return SprakeGridResult(self.import_rate * np.ones(model_length),
                                self.export_rate * np.ones(model_length))

    @classmethod
    def from_characteristics(cls,
                                name:str,
                                import_rate:float,
                                export_rate:float
                                ) -> SprakeGrid:
        
        o = cls(import_rate,export_rate)
        o.name = name
        return o

    def to_dict(self) -> Mapping:
        odict = {
            'class': re.search(r"\.(\w+)\'>$", str(type(self))).group(1),
            'name': self._name,
            'import_rate': self._import_rate,
            'export_rate': self._export_rate
        }

        return odict

    @classmethod
    def from_dict(cls, input:dict) -> SprakeGrid:
        return cls.from_characteristics(**input)
