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
from core import location as modlocation
from core import TimeSpan, TimedeltaScalar
from core import ABCNewsegsModuleResult
from newsegsgeneration.newsegsgeneration import NewsegsGeneration
from newsegsgrid import NewsegsGrid
from newsegscs import NewsegsCS
from util import classfuncs

class NewsegsModel(
    environmentserverinterface.EnvironmentServerIntrface,
    newsegscomponent.NewsegsComponent
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
    last_run = datetime.datetime.now()

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
    def mod_generation(self) -> NewsegsGeneration:
        """
        Alternative accessor for generation module
        """
        return self.generation
    
    @mod_generation.setter
    def mod_generatin(self, generation_module: NewsegsGeneration):
        self.generation = generation_module

    @abstractmethod
    def get_generation_result(self) -> ABCNewsegsModuleResult:
        """
        Access the result of a generation module run
        """

    def update_generation(self, generation_config: dict[str, Any]) -> None:
        """
        Synchronise the generation module with a config dictionary.
        """
        try:
            self.generation.update(generation_config)
        except (AttributeError, TypeError):
            from newsegsgeneration import constructors as genmodconstructors
            gen = genmodconstructors.generation_module_from_dict(generation_config)
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

    @abstractmethod
    def get_grid_result(self) -> ABCNewsegsModuleResult:
        """
        Access the result of a grid module run
        """
    
    def update_grid(self, grid_config: dict[str, Any]) -> None:
        """
        Synchronise the grid module with a config dictionary
        """
        try:
            self.grid.update(grid_config)
        except (AttributeError, TypeError):
            from newsegsgrid import constructors as gridmodconstructors
            grd = gridmodconstructors.grid_module_from_dict(grid_config)
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

    @abstractmethod
    def get_consumption_storage_result(self) -> ABCNewsegsModuleResult:
        """
        Access the result of a consumption/storage module run
        """
    
    def update_consumption_storage(self, cs_config: dict[str, Any]) -> None:
        """
        Synchronise the consumption and storage module with a config dictionary
        """
        try:
            self.consumption_storage.update(cs_config)
        except (AttributeError, TypeError):
            from newsegscs import constructors as csmodconstructors
            cs = csmodconstructors.cs_module_from_dict(cs_config)
            cs.model = self
            self.consumption_storage = cs

    

    @abstractmethod
    def get_default_timestep(self) -> TimedeltaScalar:
        """
        Get the default timestep for discrete time simulations.

        It is not necessary that all modules operate in discrete time, but in all cases
        it is likely that at least some will (i.e. `grid` will naturally operate with respect to
        market closure times). This method is provided for convenience when sychronising
        such modules
        """
    
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

    #def to_dict(self) -> dict[str, Any]:
    #    """
    #    A dictionary representation of the model configuration (not results).
    #    """
    #    odict = {
    #        'class': classfuncs.get_class(self),
    #        'name': self.name,
    #        'model_version': self.model_version
    #    }
    #
    #    return odict
    
    @override
    def _apply_dict(self, config: dict[str, Any]):
        generation = config.pop('mod_gen', None)
        if generation:
            self.update_generation(generation)

        grid = config.pop('mod_grid', None)
        if grid:
            self.update_grid(grid)

        cs = config.pop('mod_cs', None)
        if cs:
            self.update_consumption_storage(cs)
        
        return super()._apply_dict(config)
    
    def sync_with_dict(self, config: dict[str, Any]) -> None:
        """
        Update configuration using a dictionary.

        In the default implementation, will go through each key in the dict.
        If there is an attribute with an fset attribute, then assume it is a
        read-write property and update it via the fset. Otherwise, set the
        attribute directly.
        """
        config_cls = config.get('class')
        if config_cls is not None and config_cls != classfuncs.get_class(self):
            raise ValueError(f'Config model class inconsistent: {config_cls}')
        
        config_version = config.get('model_version')
        if config_version is not None and config_version != self.version:
            raise ValueError(f'Config has inconsistent model version {config_version}  vs {self.version}')
        
        config = copy.copy(config)
        
        generation = config.pop('mod_gen', None)
        if generation:
            self.update_generation(generation)

        grid = config.pop('mod_grid', None)
        if grid:
            self.update_grid(grid)

        cs = config.pop('mod_cs', None)
        if cs:
            self.update_consumption_storage(cs)
        
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
    
    # def update(
    #     self,
    #     config: dict[str, Any] | NewsegsModel,
    #     force: bool = False
    # ) -> None:
    #     """
    #     Update configuration using a dictionary or another instance.

    #     Throws TypeError if the configuration is not compatible; e.g. if the
    #     dict is for a different model or the other model instance is not of
    #     the same kind.

    #     If the dictionary has no 'class' key, it will be used anyway.
    #     """
    #     if isinstance(config, dict):
    #         conf_class = config.get('class')
    #         if conf_class and not force:
    #             if classfuncs.get_class(self) != conf_class:
    #                 raise TypeError(f'Update dictionary is for mismatched class: {conf_class} vs {classfuncs.get_class(self)}')
    #         self.sync_with_dict(config)
    #     else:
    #         if not isinstance(config, type(self)):
    #             if not force:
    #                 raise TypeError(f'Update model is of mismatched class: {type(config)} vs {type(self)}')
    #         vars(self).update(copy.deepcopy(vars(config)))

    def __hash__(self) -> int:
        return self._last_hash
