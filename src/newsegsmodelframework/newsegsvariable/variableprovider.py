"""Interface for providing variables when provided with their ids or variable_uids"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import copy
from typing import cast

from newsegsmodelframework.newsegsvariable.variable import Variable, variable_uid

class VariableProviderInterface(metaclass = ABCMeta):

    @abstractmethod
    def get_variable(self, instance_id: str) -> Variable:
        ...

    @abstractmethod
    def get_default_variable(self, variable_id: str, index: int = -1) -> Variable:
        ...

    @abstractmethod
    def duplicate_variable(self, instance_id: str) -> Variable:
        ...

    @abstractmethod
    def add_variable(self, var: Variable) -> str:
        ...

class InMemoryVariableProvider(VariableProviderInterface):

    def __init__(self, default_variables):
        super().__init__()
        self._variables_by_varid = OrderedDict()
        self._variables_by_uid = dict()

        for var in default_variables:
            vid = variable_uid(var)
            if not vid in self._variables_by_varid:
                self._variables_by_varid[vid] = OrderedDict()

            self._variables_by_varid[vid][var.id] = var
            self._variables_by_uid[var.id] = var

    def get_variable(self, instance_id: str) -> Variable:
        if instance_id in self._variables_by_uid:
            return self._variables_by_uid[instance_id]
        raise KeyError(f'Variable {instance_id} not found - try get_default_variable with the varid')

    def get_default_variable(self, variable_id: str, index: int = -1) -> Variable:
        if variable_id in self._variables_by_varid:
            return list(self._variables_by_varid[variable_id].values())[index]
        raise KeyError(f'Variable type {variable_id} not found - a first application of this variable must be added.')

    def duplicate_variable(self, instance_id: str) -> Variable:
        if instance_id in self._variables_by_uid:
            v1 = self._variables_by_uid[instance_id]
            v2 = cast(Variable, copy.deepcopy(v1))
            v2.id = v2.generate_new_id()
            vid = variable_uid(v2)
            self._variables_by_varid[vid][v2.id] = v2
            self._variables_by_uid[v2.id] = v2
            return v2
        raise KeyError(f'Variable {instance_id} not found - try get_default_variable with the varid')

    def add_variable(self, var: Variable) -> str:
        vid = variable_uid(var)
        if not vid in self._variables_by_varid:
            self._variables_by_varid[vid] = OrderedDict()

        self._variables_by_varid[vid][var.id] = var
        self._variables_by_uid[var.id] = var

        return var.id
