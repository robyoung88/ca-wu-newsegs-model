"""
Abstract base class for NewSEGS model
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod
import copy
from typing import Any, Type, override
import re
import datetime
import uuid

from core import newsegscomponent
from core import environmentserverinterface
from core import resultsserverinterface
from core import location as modlocation
from core import TimeSpan, TimedeltaScalar
from core.serialisation import T
from newsegsgeneration.newsegsgeneration import NewsegsGeneration
from newsegsgrid import NewsegsGrid
from newsegscs import NewsegsCS
from util import classfuncs

from core import newsegsmodelinterface

class NewsegsModel(
    newsegsmodelinterface.NewsegsModelInterface
):
    """
    Abstract base class of NewSEGS energy model

    Holder for three submodules:
    - NewsegsGeneration
    - NewsegsGrid
    - NewsegsCS (Consumption and Storage)

    Provides access to two environment servers providing data on weather conditions:
    - NewsegsLocalEnvironment
    - NewsegsWiderEnvironment

    Also holds global model settings (e.g. time horizon)

    Provides method to run model

    Holds and provides results for the current configuration after run

    In implementation, the model should not ideally not hold configuration for submodules, but
    provide access to those submodules.

    When restoring state from dictionary, then the configuration of the submodules should be
    passed down
    """

    _dirty = False
    
    _name = 'NewSEGS Model'
    _version = '0.0.1'
    _id_prefix = 'm'

    _last_hash = 1

    checked_out: bool = False

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)

    @property
    def model_version(self) -> str:
        return self.version

    @abstractmethod
    def run(self) -> int:
        """
        Compute all submodules given current configuration

        Results are accessed via the model properties.

        Returns a hash representing the model and datetime of run completion.
        """

    @abstractmethod
    def set_run_period(self, timespan:TimeSpan):
        """
        Define the timespan of simulation
        """

    @abstractmethod
    def get_run_period(self) -> TimeSpan:
        """
        Get the current timespan of the simulation

        This is a TimeSpan, and so simply represents a start and an end date.
        
        This can be used for deriving e.g. the horizon.
        """

    @property
    @abstractmethod
    def generation(self) -> NewsegsGeneration:
        """
        Access the generation module
        """

    @generation.setter
    @abstractmethod
    def generation(self, generation_module: NewsegsGeneration):
        """
        Replace the generation module
        """

    @property
    def mod_gen(self) -> NewsegsGeneration:
        """
        Alternative accessor for generation module
        """
        return self.generation
    
    @mod_gen.setter
    def mod_generation(self, generation_module: NewsegsGeneration):
        self.generation = generation_module

    def update_generation(self, generation_config: dict[str, Any]) -> None:
        """
        Synchronise the generation module with a config dictionary.
        """
        try:
            self.generation.update(generation_config)
        except (AttributeError, TypeError):
            from core import find_constructor
            cclass = generation_config.get('constructor_class')
            classname = generation_config.get('class')
            if cclass is None or classname is None:
                raise AttributeError('No generation module present to update')
            constr = find_constructor(
                cclass,
                classname
            )
            
            gen = constr(generation_config)
            if not isinstance(gen, NewsegsGeneration):
                raise TypeError(f'config did not produce a generation module - {type(gen)} instanced')
            gen.model = self
            self.generation = gen

    @property
    @abstractmethod
    def grid(self) -> NewsegsGrid:
        """
        Access the grid module
        """

    @grid.setter
    @abstractmethod
    def grid(self, grid_module: NewsegsGrid):
        """
        Replace the grid module
        """

    @property
    def mod_grid(self) -> NewsegsGrid:
        """
        Alternative accessor for grid module
        """
        return self.grid
    
    @mod_grid.setter
    def mod_grid(self, grid_module: NewsegsGrid):
        self.grid = grid_module
    
    def update_grid(self, grid_config: dict[str, Any]) -> None:
        """
        Synchronise the grid module with a config dictionary
        """
        try:
            self.grid.update(grid_config)
        except (AttributeError, TypeError):
            from core import find_constructor
            cclass = grid_config.get('constructor_class')
            classname = grid_config.get('class')
            if cclass is None or classname is None:
                raise AttributeError('No grid module present to update')
            constr = find_constructor(
                cclass,
                classname
            )

            grd = constr(grid_config)
            if not isinstance(grd, NewsegsGrid):
                raise TypeError(f'config did not produce a grid module - {type(grd)} instanced')
            grd.model = self
            self.grid = grd

    @property
    @abstractmethod
    def consumption_storage(self) -> NewsegsCS:
        """
        Access the consumption/storage module
        """

    @consumption_storage.setter
    @abstractmethod
    def consumption_storage(self, cs_module:NewsegsCS):
        """
        Replace the consumption/storage module
        """

    @property
    def mod_cs(self) -> NewsegsCS:
        """
        Alternative accessor for consumption/storage module
        """
        return self.consumption_storage
    
    @mod_cs.setter
    def mod_cs(self, cs_module: NewsegsCS):
        self.consumption_storage = cs_module
    
    def update_consumption_storage(self, cs_config: dict[str, Any]) -> None:
        """
        Synchronise the consumption and storage module with a config dictionary
        """
        try:
            self.consumption_storage.update(cs_config)
        except (AttributeError, TypeError):
            from core import find_constructor
            cclass = cs_config.get('constructor_class')
            classname = cs_config.get('class')
            if cclass is None or classname is None:
                raise AttributeError('No consumption_storage module present to update')
            constr = find_constructor(
                cclass,
                classname
            )

            cs = constr(cs_config)
            if not isinstance(cs, NewsegsCS):
                raise TypeError(f'config did not produce a consumption_storage module - {type(cs)} instanced')
            cs.model = self
            self.consumption_storage = cs
    
    @property
    @abstractmethod
    def location(self) -> modlocation.Location:
        """
        A generalised location for the model.

        May or may not relate to the local environment of any of the
        generators, storage units or consumers, but should give an
        indication of the site location.
        """
    
    @location.setter
    @abstractmethod
    def location(self, loc: modlocation.Location) -> None:
        ...

    @property
    def dirty(self) -> bool:
        """
        Is the model aware of config changes since last run?
        """
        return (
            self.generation.dirty or
            self.grid.dirty or
            self.consumption_storage.dirty or
            self._dirty
        )
    
    @override
    def update(self, config: dict[str, Any] | type[T]):
        if not isinstance(config, dict):
            super().update(config)
            return
        
        for mod_name in ('mod_gen', '_mod_gen'):
            generation = config.pop(mod_name, None)
            if generation:
                self.update_generation(generation)
                break

        for mod_name in ('mod_grid', '_mod_grid'):
            grid = config.pop(mod_name, None)
            if grid:
                self.update_grid(grid)
                break
        
        for mod_name in ('mod_cs', '_mod_cs'):
            cs = config.pop(mod_name, None)
            if cs:
                self.update_consumption_storage(cs)
                break
        
        return super().update(config)

    def __hash__(self) -> int:
        return self._last_hash

NewsegsModel._excluded_attributes = tuple(newsegscomponent.NewsegsComponent._excluded_attributes) + ('_generation_result', '_grid_result', '_cs_result')
