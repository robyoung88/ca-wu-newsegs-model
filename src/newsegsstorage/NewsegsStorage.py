# Abstract base class for NewSEGS Storage module

from abc import ABCMeta

class NewsegsStorage(metaclass=ABCMeta):
    @abstractmethod
    def run(self, start_datetime, end_datetime):
        ...

    # NB - cannot typehint without circular import
    @property
    @abstractmethod
    def model(self):
        ...

    @model.setter
    @abstractmethod
    def model(self, callback_model):
        ...
