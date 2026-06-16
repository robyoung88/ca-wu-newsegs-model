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
from core.timespan import TimeSpan, RegTimeSpan
from util import classfuncs

class ABCNewsegsModuleResult(metaclass = ABCMeta):
    """
    Abstract class holding module results
    """
    run_module_uuid = 1
    last_run = datetime.datetime.now()
    
    def __init__(
        self,
        run_module: NewsegsModule | str,
        last_run: datetime.datetime | None = None,
    ):
        if isinstance(run_module, NewsegsModule):
            if last_run is None:
                last_run = run_module.last_run
            run_module = run_module.uuid
        self.run_module_uuid = run_module
        if last_run is None:
            raise ValueError(f'`last_run` cannot be None if run_module is not a NewsegsModule, is {type(run_module)}')
        self.last_run = last_run

    @property
    @abstractmethod
    def meters(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        ...

    @property
    @abstractmethod
    def dsm(self) -> np.ndarray[tuple[int,int],  np.dtype[np.number]]:
        ...
        
    @abstractmethod
    def get_meter_names(self) -> Sequence[str]:
        ...

    @abstractmethod
    def get_meter_types(self) -> Sequence[str]:
        ...

    @abstractmethod
    def get_dsm_names(self) -> Sequence[str]:
        ...

    @abstractmethod
    def get_dsm_types(self) -> Sequence[str]:
        ...

    @abstractmethod
    def get_timespan(self) -> RegTimeSpan:
        ...

    def meters_to_pandas(self) -> pd.DataFrame:
        """
        Return the meter data as a pandas dataframe

        Caution - this implementation could become unweildy for large results
        """
        return defer_meters_to_pandas(self)
        
    def dsm_to_pandas(self) -> pd.DataFrame:
        """
        Return the dsm data as a pandas dataframe

        Caution - this implementation could become unweildy for large results
        """
        return defer_dsm_to_pandas(self)

    def __hash__(self):
        """The hash is dependent on the module uuid and run time."""
        return hash(
            (
                self.run_module_uuid, 
                self.last_run,
            )
        )


@lru_cache
def defer_meters_to_pandas(res: ABCNewsegsModuleResult):
    datetime = res.get_timespan().to_pandas()
    return pd.DataFrame(
        data = res.meters.T,
        index = datetime,
        columns = res.get_meter_names() # pyright: ignore[reportArgumentType]
    ) # type: ignore

@lru_cache
def defer_dsm_to_pandas(res: ABCNewsegsModuleResult):
    datetime = res.get_timespan().to_pandas()
    return pd.DataFrame(
        data = res.dsm.T,
        index = datetime,
        columns = res.get_dsm_names() # pyright: ignore[reportArgumentType]
    ) # type: ignore

def filter_meters(
    results: ABCNewsegsModuleResult,
    meter_type: Sequence[str]|str|None = None,
    meter_name: Sequence[str]|str|None = None,                
) -> Sequence[str]:
    """
    The meter names which match a particular type and/or name collection
    """
    if meter_type is None and meter_name is None:
        raise ValueError('Need at least one of `meter_type` and `meter_name`')
    
    nms = results.get_meter_names()
    if meter_type is not None:
        typs = results.get_meter_types()

        if isinstance(meter_type, str):
            nms = [mtr for mtr, typ in zip(nms, typs) if typ == meter_type]
        else:
            nms = [mtr for mtr, typ in zip(nms, typs) if typ in meter_type]
    
    if meter_name is not None:
        if isinstance(meter_type, str):
            nms = [mtr for mtr in nms if mtr == meter_name]
        else:
            nms = [mtr for mtr in nms if mtr in meter_name]

    return nms

def filter_meter_indices(
    results: ABCNewsegsModuleResult,
    meter_type: Sequence[str]|str|None = None,
    meter_name: Sequence[str]|str|None = None,
) -> Sequence[int]:
    """
    The meter indexes which match a particular type and/or name collection
    """
    if meter_type is None and meter_name is None:
        raise ValueError('Need at least one of `meter_type` and `meter_name`')
    
    nms = results.get_meter_names()
    indxs = range(len(nms))
    
    if meter_type is not None:
        typs = results.get_meter_types()

        if isinstance(meter_type, str):
            indxs = [indxs[i] for i, typ in enumerate(typs) if typ == meter_type]
            nms = [nms[i] for i in indxs]
        else:
            indxs = [indxs[i] for i, typ in enumerate(typs) if typ in meter_type]
            nms = [nms[i] for i in indxs]
    
    if meter_name is not None:
        if isinstance(meter_type, str):
            indxs = [indxs[i] for i, nm in enumerate(nms) if nm == meter_name]
        else:
            indxs = [indxs[i] for i, nm in enumerate(nms) if nm in meter_name]

    return indxs

class NewsegsModule(newsegscomponent.NewsegsComponent):
    """
    Basic abstract class serving module results
    """

    # Override of SerialiseToDictMixin _constructor_class
    _constructor_class = 'NewsegsModule'

    _dirty = True
    _model: environmentserverinterface.EnvironmentServerInterface

    def __init__(self, *args, **kwargs):
        self.uuid = str(uuid.uuid4())

    @abstractmethod
    def run(
        self,
        timespan:TimeSpan,
        run_start: datetime.datetime | None = None
    ) -> ABCNewsegsModuleResult:
        if run_start is None:
            run_start = datetime.datetime.now()
        self.last_run = run_start
        # Returns none as this is still abstract
   
    @property
    def model(self) -> environmentserverinterface.EnvironmentServerInterface:
        """
        The callback model associated with the module
        """
        if self._model is None:
            raise AttributeError('model has not been set')
        return self._model

    @model.setter
    def model(self, model: environmentserverinterface.EnvironmentServerInterface):
        try:
            current_mod = self.model
        except AttributeError:
            current_mod = None
        if current_mod is None or not(current_mod == model):
            self._dirty = self._dirty or True
        self._model = model

    
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        """
        Update configuration using a dictionary.

        In the default implementation, will go through each key in the dict.
        If there is an attribute with an fset attribute, then assume it is a
        read-write property and update it via the fset. Otherwise, set the
        attribute directly.
        """
        for k in config.keys():
            if hasattr(self, k):
                v = config.get(k)

                # If the attribute is a read-write property, its class attribute 
                # will have an fset
                try:
                    prop = getattr(type(self), k)
                    if hasattr(prop, 'fset'):
                        getattr(prop, 'fset')(self, v)
                    else:
                        # Otherwise, we assume it is a simple attribute that may be overwritten
                        setattr(self, k, v)
                except AttributeError:
                    setattr(self, k, v)
    
    def update(
        self, 
        config: dict | NewsegsModule, 
        force: bool = False
    ) -> None:
        """
        Update configuration using a dictionary or another instance.

        Throws TypeError if the configuration is not compatible; e.g. if the
        dict is for a different module or the other module instance is not of
        the same kind.

        If the dictionary is has no 'class' key, it will be used anyway.
        """
        if isinstance(config, dict):
            conf_class = config.get('class')
            if conf_class and not force:
                if classfuncs.get_class(self) != conf_class:
                    raise TypeError(f'Update dictionary is for mismatched class: {conf_class} vs {classfuncs.get_class(self)}')
            self.sync_with_dict(config)
        else:
            if not isinstance(config, type(self)):
                if not force:
                    raise TypeError(f'Update module is of mismatched class: {type(config)} vs {type(self)}')
            vars(self).update(copy.deepcopy(vars(config)))

    @classmethod
    @abstractmethod
    def from_dict(cls, config: dict) -> NewsegsModule:
        """
        An instance of the module configured per a dictionary.
        """

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self._dirty

    @dirty.setter
    def dirty(self, val:bool) -> None:
        self._dirty = val
