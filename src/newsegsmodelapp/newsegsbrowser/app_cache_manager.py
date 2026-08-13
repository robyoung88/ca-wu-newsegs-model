"""
Class for providing an interface to the caching and background callback manager functions needed for a NewsegsBrowser
"""
import copy
import datetime
import logging
from typing import Any, Literal, MutableMapping

import diskcache
from dash import CeleryManager, DiskcacheManager

from newsegsmodelapp.newsegsbrowser import energy_balance_estimation
from newsegsmodelapp.newsegsbrowser.postprocess import postprocess_utils
from newsegsmodelframework.newsegsfinance import newsegsfinance
from newsegsmodelframework.newsegsmetamodel import newsegsmetamodel
from newsegsmodelframework.newsegsmodel import newsegsmodel

class NewsegsBrowserCacheManager:
    cache: diskcache.Cache
    noncaching_background_callback_manager: DiskcacheManager | CeleryManager
    sts: MutableMapping[str, Any]
    """
    Short-term store suitable for temporarily holding state.
    """

    logger: logging.Logger | None

    models: MutableMapping[str, newsegsmodel.NewsegsModel]
    finances: MutableMapping[str, newsegsfinance.NewsegsFinance]
    metamodels: MutableMapping[str, newsegsmetamodel.NewsegsMetaModel]
    results: MutableMapping[str, Any]

    estimated_energy_balance: energy_balance_estimation.EstimatedEnergyBalance

    def __init__(
        self,
        cache: diskcache.Cache,
        noncaching_background_callback_manager: DiskcacheManager | CeleryManager,
        logger: logging.Logger | None = None
    ):
        
        self.models: MutableMapping[str, newsegsmodel.NewsegsModel] = {}
        self.finances: MutableMapping[str, newsegsfinance.NewsegsFinance] = {}
        self.metamodels: MutableMapping[str, newsegsmetamodel.NewsegsMetaModel] = {}
        self.results: MutableMapping[str, Any] = {}

        self.cache = cache
        self.noncaching_background_callback_manager = noncaching_background_callback_manager
        self.sts = {}

        if logger:
            self.logger = logger

        self.estimated_energy_balance = energy_balance_estimation.EstimatedEnergyBalance()

    def model_to_cache(self, model_id: str):
        """
        Write specified model to cache for background processing.
        """
        if self.logger:
            self.logger.info('writing model %s to cache, %s', model_id, datetime.datetime.now())
        
        mdl = self.models.get(model_id)
        if mdl:
            self.cache[model_id] = mdl

        if self.logger:
            self.logger.info('writing model %s to cache was successful, %s', model_id, datetime.datetime.now())
    
    def model_from_cache(self, model_id: str) -> newsegsmodel.NewsegsModel:
        """
        Retrive model from cache.

        Does not overwrite model in local mapping.
        """
        if self.logger:
            self.logger.info('retrieving model %s from cache', model_id)
        
        mdl = self.cache.get(model_id)
        if not isinstance(mdl, newsegsmodel.NewsegsModel):
            raise TypeError(f'{model_id} retrieved from cache is of type {type(mdl)}')
        
        if self.logger:
            self.logger.info('retrieving model %s was successful', model_id)
        
        return mdl
    
    def finance_to_cache(self, finance_id: str):
        """
        Write specified finance to cache for background processing.
        """
        if self.logger:
            self.logger.info('writing finance %s to cache', finance_id)
        
        fnc = self.finances.get(finance_id)
        if fnc:
            self.cache[finance_id] = fnc
        
        if self.logger:
            self.logger.info('writing finance %s to cache was successful', finance_id)

    def finance_from_cache(self, finance_id: str) -> newsegsfinance.NewsegsFinance:
        """
        Retrieve finance from cache.
        
        Does not overwrite finance in local mapping.
        """
        if self.logger:
            self.logger.info('retrieving finance %s from cache', finance_id)
        
        fnc = self.cache.get(finance_id)
        if not isinstance(fnc, newsegsfinance.NewsegsFinance):
            raise TypeError(f'{finance_id} retrieved from cache is of type {type(fnc)}')
        
        if self.logger:
            self.logger.info('retrieving finance %s was successful', finance_id)
        
        return fnc

    def metamodel_to_cache(self, metamodel_id: str):
        """
        Write specified metamodel to cache for background processing
        """
        mm = self.metamodels.get(metamodel_id)
        if self.logger:
            self.logger.info('writing metamodel %s to cache', metamodel_id)

        if mm:
            self.cache[metamodel_id] = mm

        if self.logger:
            self.logger.info('writing metamodel %s to cache was successful', metamodel_id)
    
    def metamodel_from_cache(
            self,  
            metamodel_id: str, 
            reattach_location: Literal['local', 'cache'] = 'local'
        ) -> newsegsmetamodel.NewsegsMetaModel:
        """
        Retrieve metamodel from cache and return.

        Does not automatically replace metamodel in local mapping.
        Can reattach the model and finance from the local mappings, or from the cache. If from the cache, these will not be replaced in the local mapping.
        """
        if self.logger:
            self.logger.info('retrieving metamodel %s from cache', metamodel_id)
        
        mm = self.cache.get(metamodel_id)
        if not isinstance(mm, newsegsmetamodel.NewsegsMetaModel):
            raise TypeError(f'{metamodel_id} retrieved from cache is of type {type(mm)}')
        match reattach_location:
            case 'local':
                mm.reattach_model(self.models)
                mm.reattach_finance(self.finances)
            case 'cache':
                mm.reattach_model(self.cache) # pyright: ignore[reportArgumentType]
                mm.reattach_finance(self.cache) # pyright: ignore[reportArgumentType]
                mm.finance.set_model(mm.model, False)

        if self.logger:
            self.logger.info('retrieving metamodel %s was successful', metamodel_id)
        
        return mm
    
    def duplicate_model(self, model_id: str) -> newsegsmodel.NewsegsModel:
        """
        Duplicate the model identified by model_id, add to local mapping, and copy any results.

        Returns the copy of the model.
        """
        ref = self.models.get(model_id)
        if ref is None:
            raise ValueError(f'NewsegsModel not found: {model_id}')
        
        # Construct
        mdl = type(ref)(ref)
        
        # Assign
        self.models[mdl.id] = mdl

        # Copy status
        new_model_id = mdl.id
        mdl.last_run = ref.last_run
        mdl._last_hash = hash((mdl.id, str(mdl.last_run)))
        
        # Copy over any results
        for res_class in ['generation', 'storage', 'consumption', 'net_energy']:
            ref_id = postprocess_utils.get_model_result_id(
                postprocess_utils.RESULT_CACHE_PREFIXES[res_class],
                model_id
            )
            new_id = postprocess_utils.get_model_result_id(
                postprocess_utils.RESULT_CACHE_PREFIXES[res_class],
                new_model_id
            )
            res = self.results.get(ref_id)
            if res is not None:
                self.results[new_id] = copy.copy(res)
                self.results[new_id]['run_hash'] = hash(mdl)

        return mdl
    
    def duplicate_finance(self, finance_id: str, model_id: str|None = None) -> newsegsfinance.NewsegsFinance:
        """
        Duplicate the finance identified by finance_id, add to local mapping, and copy any results.

        Returns the copy of the finance.
        """
        ref = self.finances.get(finance_id)
        if ref is None:
            raise ValueError(f'NewsegsFinance not found: {finance_id}')
        
        # Construct
        fnc = type(ref)(ref)

        try:
            ref_model_id = ref.model.id
        except AttributeError:
            ref_model_id = None
        
        # Default to the model attached to the reference finance if present.
        if not model_id:
            model_id = ref_model_id
        
        if model_id is not None:
            mdl = self.models.get(model_id, None)
            if mdl is not None:
                fnc.model = mdl
        
        self.finances[fnc.id] = fnc
        
        # Copy over any results
        if ref_model_id is not None:
            for res_class in ['finance_benefits_so', 'finance_costs_so', 'finance_value_so']:
                ref_id = postprocess_utils.get_finance_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES[res_class], 
                    ref.id, 
                    ref_model_id
                )

                new_id = postprocess_utils.get_finance_result_id(
                    postprocess_utils.RESULT_CACHE_PREFIXES[res_class], 
                    fnc.id,
                    model_id
                )

                res = self.results.get(ref_id)
                if res is not None:
                    self.results[new_id] = copy.copy(res)
                    self.results[new_id]['run_hash'] = hash(fnc) + hash(fnc.model)
            
        return fnc
    
    def duplicate_metamodel(self, metamodel_id: str) -> newsegsmetamodel.NewsegsMetaModel:
        """
        Duplicate the metamodel, including attached model and finance, and associated results.

        Assigns the metamodel to the local mapping; the model and finance duplicates will also be
        assigned.

        Returns the copy of the metamodel.
        """
        ref = self.metamodels.get(metamodel_id)
        if ref is None:
            raise ValueError(f'NewsegsMetaModel not found: {metamodel_id}')
        
        dup_mdl = self.duplicate_model(ref.model_id)
        dup_fnc = self.duplicate_finance(ref.finance_id, dup_mdl.id)
        
        variables = copy.deepcopy(list(ref.variables.values()))
        dup_mm = newsegsmetamodel.NewsegsMetaModel(dup_mdl, dup_fnc, variables)
        dup_mm.name = ref.name
        dup_mm.require_sync = copy.copy(ref.require_sync)

        self.metamodels[dup_mm.id] = dup_mm
        
        return dup_mm
    
    def remove_model(self, model_id: str) -> newsegsmodel.NewsegsModel | None:
        self.cache.delete(model_id)
        
        res_remove = []
        for k in self.results.keys():
            if model_id in k:
                res_remove.append(k)
        if res_remove:
            for k in res_remove:
                self.results.pop(k)
        
        return self.models.pop(model_id, None)
    
    def remove_finance(self, finance_id: str) -> newsegsfinance.NewsegsFinance | None:
        self.cache.delete(finance_id)

        res_remove = []
        for k in self.results.keys():
            if finance_id in k:
                res_remove.append(k)
        if res_remove:
            for k in res_remove:
                self.results.pop(k)
        return self.finances.pop(finance_id, None)
    
    def remove_metamodel(self, metamodel_id: str, remove_children: bool = True) -> newsegsmetamodel.NewsegsMetaModel | None:
        if remove_children:
            mm = self.metamodels.get(metamodel_id)
            if mm:
                self.remove_model(mm.model_id)
                self.remove_finance(mm.finance_id)
        
        # TODO: Clear DSA, PSA, Optim results
        
        self.cache.delete(metamodel_id)
        return self.metamodels.pop(metamodel_id, None)
    