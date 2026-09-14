"""Interface for providing variables when provided with their ids or variable_uids"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import copy
from typing import Sequence, cast, overload, override

from useful_types import SequenceNotStr

from newsegsmodelframework.newsegsvariable.variable import Variable, variable_uid

class VariableProviderInterface(metaclass = ABCMeta):

    @overload
    @abstractmethod
    def get_variable(self, instance_id: str) -> Variable:
        ...

    @overload
    @abstractmethod
    def get_variable(self, instance_id: SequenceNotStr[str]) -> SequenceNotStr[Variable]:
        ...

    @abstractmethod
    def get_variable(self, instance_id: str | SequenceNotStr[str]) -> Variable | SequenceNotStr[Variable]:
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

    @abstractmethod
    def get_varids(self) -> tuple[str, ...]:
        """Return a tuple of the varids served by the provider.
        
        Useful for populating the variable list of a new metamodel.
        """


class VariablePersistenceInterface(metaclass = ABCMeta):
    """Interface for saving variables to persistent storage (in order that they may be accessed by other providers)"""

    @abstractmethod
    def upsert_variable(self, var: Variable | Sequence[Variable], force: bool = False) -> None:
        """Insert or update a variable or list of variables into the store.
                
        Args:
            var: A variable or sequence of variables to synchronise.
            force: Overwrite the variable(s) regardless of whether their revision number has incremented.
        """

    @abstractmethod
    def delete_variable(self, variable_id: str | SequenceNotStr[str]) -> list[str]:
        """Delete a component or list of components in the store.

        Will remove all dependent components and snapshots (if applicable).

        Args:
            component_id [str | Sequence[str]]: ID(s) of component(s) to delete.
            ignore_ids [list[str]]: IDs of components which may be ignored in dependents search
        Returns:
            List of component_ids for which deletion has failed.
        """

class VariableManagerInterface(VariableProviderInterface, VariablePersistenceInterface):
    ...


class InMemoryVariableProvider(VariableManagerInterface):

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

    @overload
    def get_variable(self, instance_id: str) -> Variable:
        ...

    @overload
    def get_variable(self, instance_id: SequenceNotStr[str]) -> SequenceNotStr[Variable]:
        ...

    def get_variable(self, instance_id: str | SequenceNotStr[str]) -> Variable | SequenceNotStr[Variable]:
        if isinstance(instance_id, str):
            if instance_id in self._variables_by_uid:
                return self._variables_by_uid[instance_id]
        else:
            return [self.get_variable(x) for x in instance_id]
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

    def get_varids(self) -> tuple[str, ...]:
        return tuple(self._variables_by_varid.keys())

    @override
    def upsert_variable(self, var: Variable | Sequence[Variable], force: bool = False) -> None:
        if isinstance(var, Variable):
            var = [var]
        for var in var:
            var.chain_syncronise()

    @override
    def delete_variable(self, variable_id: str | SequenceNotStr[str]) -> list[str]:
        if isinstance(variable_id, str):
            variable_id = [variable_id]
        for uid in variable_id:
            var = self._variables_by_uid.get(uid, None)
            if var is None:
                continue

            varid = variable_uid(var)
            try:
                del self._variables_by_varid[varid][uid]
            except KeyError as e:
                pass
            try:
                del self._variables_by_uid[uid]
            except KeyError as e:
                pass
        return []

class RecoverableInMemoryVariableProvider(InMemoryVariableProvider):
    """Extends InMemoryVariableProvider with capabilities to restore variables from another (store) provider."""

    def __getstate__(self) -> object:
        atts = vars(self).copy()
        del atts['_variables_by_varid']
        del atts['_variables_by_uid']

        # Rely on order preservation of standard dictionary keys
        atts['_variable_recovery_uids'] = dict()
        for k, v in self._variables_by_varid.items():
            atts['_variable_recovery_uids'][k] = list(v.keys())
        
        return atts

    def __setstate__(self, state):
        self.__dict__ = state.copy() # pyright: ignore[reportGeneralTypeIssues, reportAttributeAccessIssue]
        self._variables_by_varid = OrderedDict()
        self._variables_by_uid = dict()

    def reattach_variables(self, variable_provider: VariableProviderInterface):
        if not hasattr(self, '_variable_recovery_uids'):
            return
        vrus = self._variable_recovery_uids # pyright: ignore[reportAttributeAccessIssue]
        varid_list = []
        uid_list = []
        for varid, uids in vrus.items():
            for uid in uids:
                varid_list.append(varid)
                uid_list.append(uid)

        if uid_list:
            variables = variable_provider.get_variable(uid_list)
            if not hasattr(self, '_variables_by_varid'):
                self._variables_by_varid = OrderedDict()
            if not hasattr(self, '_variables_by_uid'):
                self._variables_by_uid = dict()
            for varid, uid, var in zip(varid_list, uid_list, variables):
                if not varid in self._variables_by_varid:
                    self._variables_by_varid[varid] = OrderedDict()

                self._variables_by_varid[varid][uid] = var
                self._variables_by_uid[uid] = var

    @override
    def delete_variable(self, variable_id: str | SequenceNotStr[str]) -> list[str]:
        if isinstance(variable_id, str):
            variable_id = [variable_id]
        for uid in variable_id:
            var = self._variables_by_uid.get(uid, None)
            if var is None:
                continue

            varid = variable_uid(var)
            try:
                del self._variables_by_varid[varid][uid]
            except KeyError as e:
                pass
            try:
                del self._variables_by_uid[uid]
            except KeyError as e:
                pass
            if hasattr(self, '_variable_recovery_uids'):
                    try:
                        self._variable_recovery_uids[varid].remove(uid) # pyright: ignore[reportAttributeAccessIssue]
                    except ValueError as e:
                        pass
        return []
