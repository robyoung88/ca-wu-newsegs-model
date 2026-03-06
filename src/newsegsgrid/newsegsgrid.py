# Abstract base class for NewSEGS Grid module

from abc import ABCMeta, abstractmethod

class NewsegsGrid(metaclass=ABCMeta):
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
