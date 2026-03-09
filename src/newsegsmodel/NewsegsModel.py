# Abstract base class for NewSEGS model and environment data

from abc import ABCMeta
from src.core import TimeSpan
from src.core import NewsegsLocalEnvironment,NewsegsWiderEnvironment
from src.newsegsgeneration import NewsegsGeneration
from src.newsegsgrid import NewsegsGrid
from src.newsegscs import NewsegsCS

class NewsegsModel(metaclass=ABCMeta):
    @abstractmethod
    def run(self):
        ...
    
    @abstractmethod
    def set_run_period(self, timespan:TimeSpan):
        ...
    
    @property
    @abstractmethod
    def generation(self) -> NewsegsGeneration:
        ...
    
    @generation.setter
    @abstractmethod
    def generation(self, generation_module:NewsegsGeneration):
        ...

    @property
    @abstractmethod
    def grid(self) -> NewsegsGrid:
        ...

    @grid.setter
    @abstractmethod
    def grid(self, grid_module:NewsegsGrid):
        ...
    
    @property
    @abstractmethod
    def consumption_storage(self) -> NewsegsCS:
        ...
    
    @consumption_storage.setter
    @abstractmethod
    def consumption_storage(self, cs_module:NewsegsCS):
        ...

    @property
    @abstractmethod
    def local_env(self) -> NewsegsLocalEnvironment:
        ...

    @local_env.setter
    @abstractmethod
    def local_env(self, local_environment_server:NewsegsLocalEnvironment):
        ...
    
    @property
    @abstractmethod
    def wider_env(self) -> NewsegsWiderEnvironment:
        ...
    
    @wider_env.setter
    @abstractmethod
    def wider_env(self, wider_env_server:NewsegsWiderEnvironment):
        ...
