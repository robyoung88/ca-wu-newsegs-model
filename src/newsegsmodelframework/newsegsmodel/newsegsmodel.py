"""
Abstract base class for NewSEGS model
"""
from __future__ import annotations

from abc import abstractmethod
from typing import Any, Optional, Type, override

from newsegsmodelframework.core import newsegscomponent
from newsegsmodelframework.core import location as modlocation
from newsegsmodelframework.core import TimeSpan
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.core.newsegsmodule import NewsegsModule
from newsegsmodelframework.core.newsegsresultprovider import NewsegsResultProviderInterface
from newsegsmodelframework.core.serialisation import T
from newsegsmodelframework.core.trackeddata import ComponentProperty, DataWithRevision, revision_dataclass
from newsegsmodelframework.newsegsgeneration.newsegsgeneration import NewsegsGeneration
from newsegsmodelframework.newsegsgrid import NewsegsGrid
from newsegsmodelframework.newsegscs import NewsegsCS

from newsegsmodelframework.core import newsegsmodelinterface

class NewsegsModelProperty(ComponentProperty):
    @override
    def __set__(self, instance: 'newsegscomponent.NewsegsComponent', value: 'newsegscomponent.NewsegsComponent'): # pyright: ignore[reportIncompatibleMethodOverride]
        if not isinstance(instance, NewsegsModel):
            raise TypeError(f'Property accessing {self.name} should only be applied to a NewsegsModel, is attribute of {type(instance)}')
        if not isinstance(value, NewsegsModule):
            raise TypeError(f'Property assigned to {self.name} should be a NewsegsModule, is {type(value)}')
        super().__set__(instance, value)
        getattr(instance, self.name).model = instance


class NewsegsModelData(newsegscomponent.NewsegsComponent):
    """
    Holds data relating to the model configuration
    """
    component_type = 'energy_model'


@revision_dataclass
class NewsegsModelConfig(DataWithRevision):
    ...


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
    
    _name = 'NewSEGS Energy Model'
    _version = '0.0.1'
    _id_prefix = 'm'

    _excluded_attributes = newsegsmodelinterface.NewsegsModelInterface._excluded_attributes.union({
        '_grid_result', '_generation_result', '_cs_result',
    })

    model_data = ComponentProperty(default = NewsegsModelData)

    _last_hash = 1

    checked_out: bool = False
    
    def _generate_config(self, *args, **kwargs) -> NewsegsModelConfig:
        return NewsegsModelConfig(*args, **kwargs)

    def __init__(
        self,
        *args,
        model_data: Optional[NewsegsModelData] = None,
        table_config: Optional[newsegscomponent.TableConfigNewsegsComponent] = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.model_data = model_data or NewsegsModelData()
        self.table_config = table_config or newsegscomponent.TableConfigNewsegsComponent()
            
    @property
    def model_version(self) -> str:
        return self.version

    @abstractmethod
    def set_run_period(self, timespan: TimeSpan):
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
            from newsegsmodelframework.core import find_constructor
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
            from newsegsmodelframework.core import find_constructor
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
            from newsegsmodelframework.core import find_constructor
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

    @override
    def update(self, config: dict[str, Any] | type[T]):
        if isinstance(config, dict):
            attach_grid = '_grid' in config
            attach_generation = '_generation' in config
            attach_cs = '_consumption_storage' in config
        else:
            attach_grid = True
            attach_generation = True
            attach_cs = True
        super().update(config)

        if attach_grid:
            self.grid.model = self
        if attach_generation:
            self.generation.model = self
        if attach_cs:
            self.consumption_storage.model = self

    # @override
    # def __setstate__(self, state: dict[str, Any]) -> None:
    #     super().__setstate__(state)
    #     # Not sure why these don't seem to be triggering NewsegsModelProperty; probably because they are stored on the underscore
    #     try:
    #         self.grid.model = self
    #     except AttributeError:
    #         pass
    #     try:
    #         self.generation.model = self
    #     except AttributeError:
    #         pass
    #     try:
    #         self.consumption_storage.model = self
    #     except AttributeError:
    #         pass

    # @override
    # def update(self, config: dict[str, Any] | type[T]):
    #     if not isinstance(config, dict):
    #         super().update(config)
    #         return
        
    #     type_ = type(self)

    #     # If config exists in the dict, it has to be the first thing out
    #     inst_config = config.pop('_config', None)
    #     if inst_config:
    #         if isinstance(inst_config, dict):
    #             child_cc = inst_config.get('constructor_class', None)
    #             child_classname = inst_config.get('class', None)
    #             if child_cc is not None and child_classname is not None:
    #                 inst_config = find_constructor(child_cc, child_classname)(inst_config)
    #             else:
    #                 inst_config = type_.unserialise_dict(inst_config)
            
    #         setattr(self, '_config', inst_config)
    #     elif not hasattr(self, '_config'):
    #         # Need to generate a fresh config
    #         setattr(self, '_config', self._generate_config())
        
    #     for mod_name in ('mod_gen', '_mod_gen', 'generation'):
    #         generation = config.pop(mod_name, None)
    #         if generation:
    #             self.update_generation(generation)
    #             break

    #     for mod_name in ('mod_grid', '_mod_grid', 'grid'):
    #         grid = config.pop(mod_name, None)
    #         if grid:
    #             self.update_grid(grid)
    #             break
        
    #     for mod_name in ('mod_cs', '_mod_cs', 'consumption_storage'):
    #         cs = config.pop(mod_name, None)
    #         if cs:
    #             self.update_consumption_storage(cs)
    #             break
        
    #     return super().update(config)

    def reattach_grid(
        self,
        component_provider: newsegscomponent.NewsegsComponentProviderInterface
    ):
        if not hasattr(self, '_component_ids') or self._component_ids.get('grid', '') == '':
            raise AttributeError('This Energy Model has no grid module to reattach.')
        comp = component_provider.get_component(self._component_ids.get('grid', ''))
        if not isinstance(comp, NewsegsGrid):
            raise TypeError(f'component_provider did not provide a grid module for key {self._component_ids.get('grid', '')}')
        self.grid = comp

    def reattach_generation(
        self,
        component_provider: newsegscomponent.NewsegsComponentProviderInterface
    ):
        if not hasattr(self, '_component_ids') or self._component_ids.get('generation', '') == '':
            raise AttributeError('This Energy Model has no generation module to reattach.')
        comp = component_provider.get_component(self._component_ids.get('generation',''))
        if not isinstance(comp, NewsegsGeneration):
            raise TypeError(f'component_provider did not provide a generation module for key {self._component_ids.get('generation','')}')
        self.generation = comp

    def reattach_consumption_storage(
        self,
        component_provider: newsegscomponent.NewsegsComponentProviderInterface
    ):
        if not hasattr(self, '_component_ids') or self._component_ids.get('consumption_storage', '') == '':
            raise AttributeError('This Energy Model has no consumption_storage module to reattach.')
        comp = component_provider.get_component(self._component_ids.get('consumption_storage', ''))
        if not isinstance(comp, NewsegsCS):
            raise TypeError(f'component_provider did not provide a consumption_storage module for key {self._component_ids.get('consumption_storage', '')}')
        self.consumption_storage = comp

    def reattach_table_config(
        self,
        component_provider: newsegscomponent.NewsegsComponentProviderInterface
    ):
        if not hasattr(self, '_component_ids') or self._component_ids.get('table_config', '') == '':
            raise AttributeError('This Energy Model has no table_config module to reattach.')
        comp = component_provider.get_component(self._component_ids.get('table_config', ''))
        if not isinstance(comp, newsegscomponent.TableConfigNewsegsComponent):
            raise TypeError(f'component_provider did not provide a table_config module for key {self._component_ids.get('table_config', '')}')
        self.table_config = comp

    # @override
    # def get_component_attributes(self) -> tuple[str, ...]:
    #     atts = super().get_component_attributes()
    #     return atts
    #     #return ('grid', 'generation', 'consumption_storage', 'table_config', 'model_data', *atts)

    @override
    def reattach_components(self, component_provider: newsegscomponent.NewsegsComponentProviderInterface):
        r0 = self.revision
        super().reattach_components(component_provider)
        if self.revision != r0:
            raise ValueError('Revision incremented during component reattachment: from {r0} to {self.revision}')
        self.grid.model = self
        self.generation.model = self
        self.consumption_storage.model = self
        if self.revision != r0:
            raise ValueError('Revision incremented during model set: from {r0} to {self.revision}')


    def reattach_results(self, results_provider: NewsegsResultProviderInterface, allow_stale = True, run_id: int = -1) -> bool:
        """
        
        Returns:
            [bool] - True if any results are stale
        """
        any_stale = False
    
        try:
            res_ = None
            rev_ = None
            if run_id != -1:
                res_, rev_ = results_provider.get_run_result(
                    'deterministic_grid', run_id, self.grid
                )
            
            if res_ is None:
                res_, rev_ = results_provider.get_result(
                    'deterministic_grid', self.grid, allow_stale
                )

            self._grid_result = res_
            self._grid_result_revision = rev_

            any_stale = any_stale or res_ is None or self._grid_result_revision != self.grid.revision
        except Exception as e:
            print (e)
            any_stale = True

        try:
            res_ = None
            rev_ = None
            if run_id != -1:
                res_, rev_ = results_provider.get_run_result(
                    'deterministic_generation', run_id, self.generation
                )
            
            if res_ is None:
                res_, rev_ = results_provider.get_result(
                    'deterministic_generation', self.generation, allow_stale
                )

            self._generation_result = res_
            self._generation_result_revision = rev_

            any_stale = any_stale or res_ is None or self._generation_result_revision != self.generation.revision
        except Exception as e:
            print (e)
            any_stale = True

        try:
            res_ = None
            rev_ = None
            if run_id != -1:
                res_, rev_ = results_provider.get_run_result(
                    'deterministic_consumption_storage', run_id, self.consumption_storage
                )
            
            if res_ is None:
                res_, rev_ = results_provider.get_result(
                    'deterministic_consumption_storage', self.consumption_storage, allow_stale
                )

            self._cs_result = res_
            self._cs_result_revision = rev_

            any_stale = any_stale or res_ is None or self._cs_result_revision != self.consumption_storage.revision
        except Exception as e:
            print(e)
            any_stale = True
            
        return any_stale
        
    def __hash__(self) -> int:
        return self._last_hash

# NewsegsModel._excluded_attributes = tuple(
#     newsegscomponent.NewsegsComponent._excluded_attributes
# ) + (
#     '_grid', '_generation', '_consumption_storage',
#     '_generation_result', '_grid_result', '_cs_result',
#     '_table_config'
# )
