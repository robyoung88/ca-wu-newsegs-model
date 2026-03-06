# Abstract base class for NewSEGS model and environment data

from abc import ABCMeta
from newsegsgeneration import NewsegsGeneration
from newsegsgrid import NewsegsGrid
from newsegsconsumption import NewsegsConsumption
from newsegsstorage import NewsegsStorage

class NewsegsLocalEnvironment(metaclass=ABCMeta):
    @abstractmethod
    def get_wind_speeds(self, heights, start_datetime, end_datetime):
        ...

    @abstractmethod
    def get_horizontal_solar_flux(self, start_datetime, end_datetime):
        ...

    @abstractmethod
    def get_external_temperature(self, start_datetime, end_datetime):
        ...
    
    @abstractmethod
    def get_solar_flux_on_plane(self, collector_facing, start_datetime, end_datetime):
        ...

class NewsegsWiderEnvironment(metaclass=ABCMeta):
    @abstractmethod
    def get_temperature(self, start_datetime, end_datetime):
        ...
    
    @abstractmethod
    def get_horizontal_solar_flux(self, start_datetime, end_datetime):
        ...

class NewsegsModel(metaclass=ABCMeta):
    @abstractmethod
    def run(self):
        ...
    
    @abstractmethod
    def set_run_period(self, start_datetime, end_datetime):
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
    def consumption(self) -> NewsegsConsumption:
        ...
    
    @consumption.setter
    @abstractmethod
    def consumption(self, consumption_module:NewsegsConsumption):
        ...

    @property
    @abstractmethod
    def storage(self) -> NewsegsStorage:
        ...
    
    @storage.setter
    @abstractmethod
    def storage(self, storage_module:NewsegsStorage):
        ...

    @property
    @abstractmethod
    def local_env(self) -> NewsegsLocalEnvironment:
        ...

    @local_env.setter
    @abstractmethod
    def local_env(self, local_environment_module:NewsegsLocalEnvironment):
        ...
    
    @property
    @abstractmethod
    def wider_env(self) -> NewsegsWiderEnvironment:
        ...
    
    @wider_env.setter
    @abstractmethod
    def wider_env(self, wider_env_module:NewsegsWiderEnvironment):
        ...
