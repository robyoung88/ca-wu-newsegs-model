# Abstract base class for NewSEGS financial calculations

from abc import ABCMeta, abstractmethod

from src.newsegsmodel import NewsegsModel
import pandas as pd
import numpy.typing as npt

class NewsegsFinance(metaclass=ABCMeta):

    _dirty_flag = True

    # The model is assumed run, and used to extract results for providing the derived financial properties
    @abstractmethod
    def set_model(self, mdl:NewsegsModel):
        ...

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
        ...
    
    @property
    @abstractmethod
    def resident_receipts_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def ev_receipts_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def ev_receipts_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def export_receipts_undiscounted(self) -> pd.DataFrame:
        ...
    
    @property
    @abstractmethod
    def export_receipts_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def all_receipts_undiscounted(self) -> pd.DataFrame:
        ...
    
    @property
    @abstractmethod
    def all_receipts_discounted(self) -> pd.DataFrame:
        ...

    @abstractmethod
    def get_total_present_benefits_undiscounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...
    
    @abstractmethod
    def get_total_present_benefits_discounted(self, horizon:pd.Timestamp|pd.Timedelta|None=None) -> float:
        ...

    # Costs
    @property
    @abstractmethod
    def import_costs_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def import_costs_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_generation_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_generation_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_storage_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_storage_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_billing_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_billing_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_other_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def om_costs_other_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def all_recurrent_costs_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def all_recurrent_costs_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_generation_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_generation_discounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_storage_undiscounted(self) -> pd.DataFrame:
        ...

    @property
    @abstractmethod
    def capex_costs_storage_discounted(self) -> pd.DataFrame:
        ...

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
    def get_net_present_value_discounted(self, horizon:pd.Timedelta|None=None):
        ...

    @abstractmethod
    def to_dict(self):
        """
        Configuration as a dictionary
        """
        ...

    @property
    def dirty(self) -> bool:
        """
        Has the model configuration changed since last run?
        """
        return self._dirty_flag

    @dirty.setter
    def dirty(self, val:bool) -> None:
        self._dirty_flag = val
