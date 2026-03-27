"""
Abstract base class for NewSEGS model
"""

from abc import ABCMeta, abstractmethod

from src.core import TimeSpan, TimedeltaScalar
from src.core import NewsegsLocalEnvironment,NewsegsWiderEnvironment
from src.core import ABCNewsegsModuleResult
from src.newsegsgeneration import NewsegsGeneration
from src.newsegsgrid import NewsegsGrid
from src.newsegscs import NewsegsCS

class NewsegsModel(metaclass=ABCMeta):
    """
    Abstract base class of Newbuild on-Site Energy Generation and Storage (NewSEGS) model

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
    @abstractmethod
    def run(self):
        """
        Compute all submodules given current configuration

        Results are accessed via the model properties
        """

    @abstractmethod
    def set_run_period(self, timespan:TimeSpan):
        """
        Define the timespan of simulation
        """

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
    def generation(self, generation_module:NewsegsGeneration):
        """
        Replace the generation module
        """

    @abstractmethod
    def get_generation_result(self) -> ABCNewsegsModuleResult:
        """
        Access the result of a generation module run
        """

    @property
    @abstractmethod
    def grid(self) -> NewsegsGrid:
        """
        Access the grid module
        """

    @grid.setter
    @abstractmethod
    def grid(self, grid_module:NewsegsGrid):
        """
        Replace the grid module
        """

    @abstractmethod
    def get_grid_result(self) -> ABCNewsegsModuleResult:
        """
        Access the result of a grid module run
        """

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

    @abstractmethod
    def get_consumption_storage_result(self) -> ABCNewsegsModuleResult:
        """
        Access the result of a consumption/storage module run
        """

    @property
    @abstractmethod
    def local_env(self) -> NewsegsLocalEnvironment:
        """
        Access the local environment server
        """

    @local_env.setter
    @abstractmethod
    def local_env(self, local_environment_server:NewsegsLocalEnvironment):
        """
        Replace the local environment server
        """

    @property
    @abstractmethod
    def wider_env(self) -> NewsegsWiderEnvironment:
        """
        Access the wider environment server
        """

    @wider_env.setter
    @abstractmethod
    def wider_env(self, wider_env_server:NewsegsWiderEnvironment):
        """
        Replace the wider environment server
        """

    @abstractmethod
    def get_default_timestep(self) -> TimedeltaScalar:
        """
        Get the default timestep for discrete time simulations.

        It is not necessary that all modules operate in discrete time, but in all cases
        it is likely that at least some will (i.e. `grid` will naturally operate with respect to
        market closure times). This method is provided for convenience when sychronising
        such modules
        """
