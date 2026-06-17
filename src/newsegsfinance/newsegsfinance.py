# Abstract base class for NewSEGS financial calculations
from __future__ import annotations

from abc import ABCMeta, abstractmethod
import copy
import datetime
from typing import Any
import uuid
import re

from core import newsegscomponent
from newsegsmodel import NewsegsModel
import pandas as pd

from util import classfuncs

class NewsegsFinance(newsegscomponent.NewsegsComponent):
    """
    Abstract base class of NewSEGS finance model

    Uses the results timeseries of a NewsegsModel instance in combination with
    configuration variables to calculate costs and benefits associated with
    energy generation, sales, and imports.
    """

    _dirty = True

    _name = 'NewSEGS Finance'
    _finance_version = '0.0.1'
    _id_prefix = 'f'
    
    _model = None
    
    last_update = datetime.datetime.now()

    _benefit_discount_rate: float = 0.
    _cost_discount_rate: float = 0.

    def __init__(self, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
    
    @property
    def finance_version(self) -> str:
        return self.version

    def run(self):
        """
        Perform any expensive computation required to "un-dirty" the finance
        """
        self._dirty = False
        return hash(self)

    # The model is assumed run, and used to extract results for providing the derived financial properties
    @abstractmethod
    def set_model(self, mdl: NewsegsModel | None, dirty: bool = True) -> None:
        ...
    
    @property
    def model(self) -> NewsegsModel | None:
        return self._model
    
    @model.setter
    def model(self, mdl: NewsegsModel | None) -> None:
        self.set_model(mdl)

    # Discount rates
    @property
    @abstractmethod
    def benefit_discount_rate(self) -> float:
        ...

    @property
    @abstractmethod
    def cost_discount_rate(self) -> float:
        ...
    
    @abstractmethod
    def set_discount_rates(self, *drs:float, **kwdrs:float) -> None:
        ...
    
    # Benefits
    @property
    @abstractmethod
    def resident_receipts_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of resident receipts.

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total).
        """
    
    @property
    @abstractmethod
    def resident_receipts_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of resident receipts (benefits discount applied).

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total).
        """

    @property
    @abstractmethod
    def ev_receipts_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of EV receipts.

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total).
        """

    @property
    @abstractmethod
    def ev_receipts_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of EV receipts (benefits discount applied).

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total).
        """

    @property
    @abstractmethod
    def export_receipts_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of grid export receipts.

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total). In this instance, fixed_receipts may be used for capacity 
        payments.
        """
    
    @property
    @abstractmethod
    def export_receipts_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of grid export receipts (benefits discount applied).

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total). In this instance, fixed_receipts may be used for capacity 
        payments.
        """

    @property
    @abstractmethod
    def all_receipts_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of receipts.

        Columns are divided into a multi-index by `customer` and `receipt`.
        `customer` may be e.g. 'resident', 'ev', 'export' and `receipt`
        may be `fixed_receipts`, `var_receipts` and `receipts` (i.e. total).
        """
    
    @property
    @abstractmethod
    def all_receipts_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of receipts (benefits discount applied).

        Columns are divided into a multi-index by `customer` and `receipt`.
        `customer` may be e.g. 'resident', 'ev', 'export' and `receipt`
        may be `fixed_receipts`, `var_receipts` and `receipts` (i.e. total).
        """

    @abstractmethod
    def get_total_present_benefits_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """
        The sum to horizon of undiscounted benefits.
        """
    
    @abstractmethod
    def get_total_present_benefits_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """
        The sum to horizon of discounted benefits.
        """

    # Costs
    @property
    @abstractmethod
    def import_costs_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of grid import costs.

        Broken down into `fixed_costs`, `var_costs`, `costs` (i.e.
        total).
        """

    @property
    @abstractmethod
    def import_costs_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of grid import costs (costs discount applied).

        Broken down into `fixed_costs`, `var_costs`, `costs` (i.e.
        total).
        """

    @property
    @abstractmethod
    def om_costs_generation_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of generators.

        May be broken down by generator, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_generation_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of generators (cost discount applied).

        May be broken down by generator, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_storage_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of storage technologies.

        May be broken down by storage, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_storage_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of o&m costs of storage technologies (cost discount applied).

        May be broken down by storage, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_billing_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of billing costs.

        May be broken down, but should include a totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_billing_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of billing costs (cost discount applied).

        May be broken down, but should include a totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_other_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of other costs.

        May be broken down, but should include a totals column: `costs`.
        """

    @property
    @abstractmethod
    def om_costs_other_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of other costs (cost discount applied).

        May be broken down, but should include a totals column: `costs`.
        """

    @property
    @abstractmethod
    def all_recurrent_costs_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of recurrent costs.

        Includes generation O&M, storage O&M, billing, other, and grid_import.
        Columns are divided into a multi-index by `system` and `cost`, where
        `system` may be e.g. `generation`, `storage`, `billing`, `other`, or `grid_import`
        and `cost` is the breakdown from that system, with a totals column `costs`.
        """

    @property
    @abstractmethod
    def all_recurrent_costs_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of recurrent costs (cost discount applied).

        Includes generation O&M, storage O&M, billing, other, and grid_import.
        Columns are divided into a multi-index by `system` and `cost`, where
        `system` may be e.g. `generation`, `storage`, `billing`, `other`, or `grid_import`
        and `cost` is the breakdown from that system, with a totals column `costs`.
        """

    @property
    @abstractmethod
    def capex_costs_generation_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of capital expenditures for generation.

        May be broken down by generator, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def capex_costs_generation_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of capital expenditures for generation (cost discount applied).

        May be broken down by generator, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def capex_costs_storage_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of capital expenditures for storage.

        May be broken down by storage, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def capex_costs_storage_discounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of capital expenditures for storage (cost discount applied).

        May be broken down by storage, but should include a
        totals column: `costs`.
        """

    @property
    @abstractmethod
    def capex_costs_distribution_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_distribution_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_metering_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_metering_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_other_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_other_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def all_capex_costs_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def all_capex_costs_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def all_costs_undiscounted(self) -> pd.DataFrame:
        ...
    
    @property
    @abstractmethod
    def all_costs_discounted(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_total_present_costs_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...
    
    @abstractmethod
    def get_total_present_costs_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...

    # Summary vectors
    @abstractmethod
    def get_benefits_series_undiscounted(self) -> pd.Series:
        """
        All benefits collapsed to a single series indexed by datetime (without discount)
        """
        ...
    
    @abstractmethod
    def get_benefits_series_discounted(self) -> pd.Series:
        """
        All benefits collapsed to a single series indexed by datetime (discounted)
        """
        ...

    @abstractmethod
    def get_costs_series_undiscounted(self) -> pd.Series:
        """
        All costs collapsed to a single series indexed by datetime (without discount)
        """
        ...
    
    @abstractmethod
    def get_costs_series_discounted(self) -> pd.Series:
        """
        All costs collapsed to a single series indexed by datetime (discounted)
        """
        ...

    @abstractmethod
    def get_benefits_costs_undiscounted(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_benefits_costs_discounted(self) -> pd.DataFrame:
        ...

    # Derived values
    @abstractmethod
    def get_benefit_cost_ratio_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...
    
    @abstractmethod
    def get_benefit_cost_ratio_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...

    @abstractmethod
    def get_simple_payback_time_days(self) -> float:
        ...
    
    @abstractmethod
    def get_net_present_value_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...
    
    @abstractmethod
    def get_net_present_value_discounted(self, horizon:pd.Timedelta|None=None) -> float:
        ...

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self._dirty

    @dirty.setter
    def dirty(self, val: bool) -> None:
        #import traceback
        if val:
            #print('finance last_update set')
            #print(traceback.print_stack())
            self.last_update = datetime.datetime.now()
        self._dirty = val

    # def to_dict(self) -> dict[str, Any]:
    #     """
    #     Configuration as a dictionary
    #     """
    #     odict = {
    #         'class': classfuncs.get_class(self),
    #         'name': self.name,
    #         'finance_version': self.finance_version,
    #     }
        
    #     return odict
    
    # def sync_with_dict(self, config: dict[str, Any]) -> None:
    #     """
    #     Update configuration using a dictionary.

    #     In the default implementation, will go through each key in the dict.
    #     If there is an attribute with an fset attribute, then assume it is a
    #     read-write property and update it via the fset. Otherwise, set the
    #     attribute directly.
    #     """
    #     config_cls = config.get('class')
    #     if config_cls is not None and config_cls != classfuncs.get_class(self):
    #         raise ValueError(f'Config model class inconsistent: {config_cls}')
        
    #     config_version = config.get('model_version')
    #     if config_version is not None and config_version != self.version:
    #         raise ValueError(f'Config has inconsistent model version {config_version}  vs {self.version}')
        
    #     config = copy.copy(config)

    #     for k in config.keys():
    #         if hasattr(self, k):
    #             v = config.get(k)

    #             # If the attribute is a read-write property, its class attribute 
    #             # will have an fset
    #             try:
    #                 prop = getattr(type(self), k)
    #                 if hasattr(prop, 'fset'):
    #                     getattr(prop, 'fset')(self, v)
    #                 else:
    #                     # Otherwise, we assume it is a simple attribute that may be overwritten
    #                     setattr(self, k, v)
    #             except AttributeError:
    #                 setattr(self, k, v)

    # def update(
    #     self,
    #     config: dict[str, Any] | NewsegsFinance,
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

    def __hash__(self):
        mdl = self.model
        if mdl is None:
            return hash(
                (
                    self.id,
                    self.last_update,
                )
            )
        return hash(
            (
                self.id,
                self.last_update,
                mdl.id,
                mdl.last_run
            )
        )
