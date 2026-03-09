from abc import ABCMeta

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