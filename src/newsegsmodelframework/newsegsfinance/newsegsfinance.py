"""Provides abstract base class for NewSEGS financial calculations"""
from __future__ import annotations

from abc import abstractmethod
from typing import Callable, Hashable, Optional, TypeVar

import pandas as pd

from newsegsmodelframework.constants.framework_constants import COMPONENT_PREFIXES
from newsegsmodelframework.core import NewsegsComponent
from newsegsmodelframework.core.newsegscomponent import TableConfigNewsegsComponent
from newsegsmodelframework.core.newsegsfinanceinterface import NewsegsFinanceInterface
from newsegsmodelframework.core import newsegsmodelinterface
from newsegsmodelframework.core.trackeddata import ComponentProperty, DataWithRevision, revision_dataclass

T = TypeVar('T')

class NewsegsFinanceData(NewsegsComponent):
    """
    Holds data relating to the finance configuration and provides a reference for results.
    """
    component_type = 'finance_model'

@revision_dataclass
class NewsegsFinanceConfig(DataWithRevision):
    """Configuration of a finance model.

    Attributes:
        benefit_discount_rate: Discount rate applied to benefits (receipts).
        cost_discount_rate: Discount rate applied to costs.
    """
    benefit_discount_rate: float = 0.
    cost_discount_rate: float = 0.

class NewsegsFinance(NewsegsFinanceInterface):
    """
    Abstract base class of NewSEGS Finance model.

    Uses the results timeseries of a NewsegsModel instance in combination with
    configuration variables to calculate costs and benefits associated with
    energy generation, sales, and imports.
    """

    _name = 'NewSEGS Finance Model'
    _finance_version = '0.0.1'
    _id_prefix = COMPONENT_PREFIXES['fm']

    # The cache of results is for the current run only, so is not saved or copied
    _excluded_attributes = NewsegsFinanceInterface._excluded_attributes.union({'_model', '_result_cache'})

    finance_data = ComponentProperty(default = NewsegsFinanceData)

    model = ComponentProperty(default = None)
    
    last_update: float = 0.0

    checked_out: bool = False

    def _generate_config(self, *args, **kwargs) -> DataWithRevision:
        return NewsegsFinanceConfig(*args, **kwargs)

    def __init__(
            self, 
            *args,
            model: Optional[newsegsmodelinterface.NewsegsModelInterface] = None,
            finance_data: Optional['NewsegsFinanceData'] = None,
            table_config: Optional['TableConfigNewsegsComponent'] = None,
            **kwargs):
        super().__init__(*args, **kwargs)

        if model is not None:
            self.set_model(model)

        self.finance_data = finance_data or NewsegsFinanceData()
        self.table_config = table_config or TableConfigNewsegsComponent()
    
    # REVIEW (unreferenced): no references to `finance_version` found in src/, scripts/ or data/.
    @property
    def finance_version(self) -> str:
        """Version of the finance model.
        """
        return self.version

    def run(self):
        """
        Perform any expensive computation required to "un-dirty" the finance

        Empties the cache of results (see `cached_result`), so must be called before results are read
        after a run of the model or a change to the configuration.
        """
        super().run()
        self.clear_result_cache()
        return hash(self)

    def clear_result_cache(self) -> None:
        """Empty the cache of results (see `cached_result`)."""
        self._result_cache = (None, {})

    def cached_result(self, key: Hashable, compute: Callable[[], T]) -> T:
        """A result of the finance model, computed once for the current run.

        Results derived from the same run are often needed several times, such as the costs, which
        both the NPV and the benefit-cost ratio use. They are cached on the instance, and the cache
        is emptied by `run`. It is also emptied if the configuration or the run of the model has
        changed since it was filled (that is, if the hash of the instance has changed), so that
        a result is never that of an earlier run, and the cache holds the results of one run only.

        Args:
            key: Key of the result, unique to the function computing it and its arguments.
            compute: Function computing the result when it is not cached.

        Returns:
            The result.
        """
        state = hash(self)
        cached_state, cache = self.__dict__.get('_result_cache', (None, {}))
        if cached_state != state:
            cache = {}
            self._result_cache = (state, cache)
        if key not in cache:
            cache[key] = compute()
        return cache[key]

    # The model is assumed run, and used to extract results for providing the derived financial properties
    def set_model(
        self, 
        mdl: newsegsmodelinterface.NewsegsModelInterface,
        dirty: bool = True
    ) -> None:
        """Attach the NewSEGS Energy Model whose results the finance model values.

        Args:
            mdl: The NewSEGS Energy Model.
            dirty: Whether to mark the finance model as needing to be rerun.
        """
        last_revision = self.revision
        self.model = mdl
        if not dirty:
            self._config._revision = last_revision
    
    # REVIEW (unreferenced): no references to `set_discount_rates` found in src/, scripts/ or data/.
    def set_discount_rates(self, *drs:float, **kwdrs:float) -> None:
        """
        Set the benefit and cost discount rates

        Note that if only one positional argument is given, both discount rates
        will be set to this value.

        If mixing positional and keyword arguments, note that `benefit_discount_rate`
        is always the first positional argument, and will be over-written by a
        subsequent keyword argument of that key.

        Args:
            benefit_discount_rate: Also first positional argument (float)
            cost_discount_rate: Also second positional argument (float)
        """
        if len(drs) == 1 and len(kwdrs) == 0:
            # Assume that user wants to set both discount rates to nominated value
            dr = drs[0]
            self.benefit_discount_rate = dr
            self.cost_discount_rate = dr
        else:
            argnames = ['benefit_discount_rate', 'cost_discount_rate']
            argdict = dict(zip(argnames, drs))
            argdict.update(kwdrs)
            self.benefit_discount_rate = argdict.get('benefit_discount_rate', self._benefit_discount_rate) or 0.0
            self.cost_discount_rate = argdict.get('cost_discount_rate', self._cost_discount_rate) or 0.0
    
    # Benefits
    @property
    @abstractmethod
    def resident_receipts_undiscounted(self) -> pd.DataFrame:
        """
        Frame of timeseries of resident receipts.

        Broken down into `fixed_receipts`, `var_receipts`, `receipts` (i.e.
        total).
        """
    
    # REVIEW (unreferenced): no references to `resident_receipts_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `ev_receipts_discounted` found in src/, scripts/ or data/.
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
    
    # REVIEW (unreferenced): no references to `export_receipts_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `import_costs_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `om_costs_generation_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `om_costs_storage_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `om_costs_billing_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `om_costs_other_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `capex_costs_generation_discounted` found in src/, scripts/ or data/.
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

    # REVIEW (unreferenced): no references to `capex_costs_storage_discounted` found in src/, scripts/ or data/.
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
        """Frame of timeseries of capital expenditure on distribution (undiscounted).
        """
        ...

    # REVIEW (unreferenced): no references to `capex_costs_distribution_discounted` found in src/, scripts/ or data/.
    @property
    @abstractmethod
    def capex_costs_distribution_discounted(self) -> pd.DataFrame:
        """Frame of timeseries of capital expenditure on distribution (cost discount applied).
        """
        ...

    @property
    @abstractmethod
    def capex_costs_metering_undiscounted(self) -> pd.DataFrame:
        """Frame of timeseries of capital expenditure on metering (undiscounted).
        """
        ...

    # REVIEW (unreferenced): no references to `capex_costs_metering_discounted` found in src/, scripts/ or data/.
    @property
    @abstractmethod
    def capex_costs_metering_discounted(self) -> pd.DataFrame:
        """Frame of timeseries of capital expenditure on metering (cost discount applied).
        """
        ...

    @property
    @abstractmethod
    def capex_costs_other_undiscounted(self) -> pd.DataFrame:
        """Frame of timeseries of other capital expenditure (undiscounted).
        """
        ...

    # REVIEW (unreferenced): no references to `capex_costs_other_discounted` found in src/, scripts/ or data/.
    @property
    @abstractmethod
    def capex_costs_other_discounted(self) -> pd.DataFrame:
        """Frame of timeseries of other capital expenditure (cost discount applied).
        """
        ...

    @property
    @abstractmethod
    def all_capex_costs_undiscounted(self) -> pd.DataFrame:
        """Frame of timeseries of all capital expenditure (undiscounted).
        """
        ...

    @property
    @abstractmethod
    def all_capex_costs_discounted(self) -> pd.DataFrame:
        """Frame of timeseries of all capital expenditure (cost discount applied).
        """
        ...

    @property
    @abstractmethod
    def all_costs_undiscounted(self) -> pd.DataFrame:
        """Frame of timeseries of all costs, recurrent and capital (the columns of the systems are suffixed `_recurrent` and `_capex`) (undiscounted).
        """
        ...
    
    @property
    @abstractmethod
    def all_costs_discounted(self) -> pd.DataFrame:
        """Frame of timeseries of all costs, recurrent and capital (the columns of the systems are suffixed `_recurrent` and `_capex`) (cost discount applied).
        """
        ...

    @abstractmethod
    def get_total_present_costs_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """The sum to horizon of undiscounted costs.

        The sum of all the costs up to the horizon, with no discount applied.

        Args:
            horizon: Time up to which to sum, as a timestamp or a timedelta from the start of the data; the end of the data if None.

        Returns:
            Total costs.
        """
        ...
    
    @abstractmethod
    def get_total_present_costs_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """The sum to horizon of discounted costs.

        The sum of all the costs up to the horizon, with the cost discount applied.

        Args:
            horizon: Time up to which to sum, as a timestamp or a timedelta from the start of the data; the end of the data if None.

        Returns:
            Total discounted costs.
        """
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
        """Undiscounted benefits and costs as the columns of a dataframe indexed by datetime.

        Returns:
            The dataframe with `benefits` and `costs` columns.
        """
        ...

    @abstractmethod
    def get_benefits_costs_discounted(self) -> pd.DataFrame:
        """Discounted benefits and costs as the columns of a dataframe indexed by datetime.

        Returns:
            The dataframe with `benefits` and `costs` columns.
        """
        ...

    # Derived values
    @abstractmethod
    def get_benefit_cost_ratio_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """The ratio of undiscounted benefits to undiscounted costs up to the horizon.

        Where the costs are zero the ratio is infinite, signed as the benefits.

        Args:
            horizon: Time up to which to sum, as a timestamp or a timedelta from the start of the data; the end of the data if None.

        Returns:
            The ratio.
        """
        ...
    
    @abstractmethod
    def get_benefit_cost_ratio_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """The ratio of discounted benefits to discounted costs up to the horizon.

        Where the costs are zero the ratio is infinite, signed as the benefits.

        Args:
            horizon: Time up to which to sum, as a timestamp or a timedelta from the start of the data; the end of the data if None.

        Returns:
            The ratio.
        """
        ...

    @abstractmethod
    def get_simple_payback_time_days(self) -> float:
        """The simple payback time in days.

        The time from the start of the run until the cumulative undiscounted net revenue (receipts less recurrent costs) has repaid the capital expenditure. If this is not reached within the run it is extrapolated from the rate at which the debt is being reduced; it is infinite if the debt is not being reduced.

        Returns:
            The time in days.
        """
        ...
    
    @abstractmethod
    def get_net_present_value_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        """The undiscounted net value to horizon: benefits less costs.

        Args:
            horizon: Time up to which to sum, as a timestamp or a timedelta from the start of the data; the end of the data if None.

        Returns:
            The net value.
        """
        ...
    
    @abstractmethod
    def get_net_present_value_discounted(self, horizon:pd.Timedelta|None=None) -> float:
        """The net present value to horizon: discounted benefits less discounted costs.

        Args:
            horizon: Time up to which to sum, as a timestamp or a timedelta from the start of the data; the end of the data if None.

        Returns:
            The net present value.
        """
        ...

    def __hash__(self):
        mdl = self.model
        if mdl is None:
            return hash(
                (
                    self.id,
                    self.revision,
                )
            )
        return hash(
            (
                self.id,
                self.revision,
                mdl.id,
                mdl.last_run
            )
        )
