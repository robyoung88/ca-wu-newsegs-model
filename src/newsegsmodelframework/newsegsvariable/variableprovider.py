"""Interface for providing variables when provided with their ids or variable_uids"""

from __future__ import annotations

from abc import ABCMeta, abstractmethod
from collections import OrderedDict
import copy
from typing import Sequence, cast, overload, override

from useful_types import SequenceNotStr

from newsegsmodelframework.newsegsvariable.variable import Variable, variable_uid

class VariableProviderInterface(metaclass = ABCMeta):

    """Interface for providing variables when given their ids or varids.

    A variable is held as an *instance* with a unique id. Several instances may share a *varid*
    (`{section}.{key}.{subindex}`), e.g. the same parameter in different metamodels; the
    provider holds them in the order added, the last being the default for the varid.
    """
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
        """Get the variable with an instance id, or variables with a sequence of ids.

        Raises `KeyError` if a variable is not found.

        Args:
            instance_id: Id(s) of the variable instance(s) - the `id` of the component, not the varid.

        Returns:
            The variable, or a sequence of variables.
        """
        ...

    @abstractmethod
    def get_default_variable(self, variable_id: str, index: int = -1) -> Variable:
        """Get the default instance of a variable by varid.

        Raises `KeyError` if there is no variable with the varid.

        Args:
            variable_id: The varid (`{section}.{key}.{subindex}`) of the variable.
            index: Which instance of the varid to return, in the order they were added; -1 is the most recent.

        Returns:
            The variable.
        """
        ...

    @abstractmethod
    def duplicate_variable(self, instance_id: str) -> Variable:
        """Make a copy of a variable with a new id, and add it to the provider.

        Args:
            instance_id: Id(s) of the variable instance(s) - the `id` of the component, not the varid.

        Returns:
            The new variable.
        """
        ...

    @abstractmethod
    def add_variable(self, var: Variable) -> str:
        """Add a variable to the VariableProvider
        
        Add an instance of a variable such that it is gettable by both instance id and variable id

        Returns:
            The uid of the variable
        """
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
        """Delete a variable or list of variables in the store.

        Will remove all dependent components and snapshots (if applicable).

        Args:
            variable_id: ID(s) of the variable(s) to delete.

        Returns:
            List of variable ids for which deletion has failed.
        """

class VariableManagerInterface(VariableProviderInterface, VariablePersistenceInterface):
    """A variable provider which can also persist variables: the interface of a store.
    """
    ...


class InMemoryVariableProvider(VariableManagerInterface):

    """Variable provider holding the variables in memory.

    Variables are indexed by their instance id and by varid (insertion-ordered).

    Note:
        `variable_uid` returns a list of varids for a variable with several `interface_key`s
        (a vector variable setting several parameters). Such a list cannot be used as a
        dictionary key, so these variables are not yet supported: adding one raises
        `NotImplementedError`.
    """

    # TODO: Support variables with several varids, e.g. by indexing the variable under each
    # varid in the list that `variable_uid` returns.
    @staticmethod
    def _get_varid(var: Variable) -> str:
        """The varid of a variable.

        Raises:
            NotImplementedError: if the variable has several varids.
        """
        vid = variable_uid(var)
        if not isinstance(vid, str):
            raise NotImplementedError(
                f'Variable {var.name} has several varids ({vid}); variables with more than one '
                'interface_key are not supported by the in-memory variable provider'
            )
        return vid

    def __init__(self, default_variables):
        super().__init__()
        self._variables_by_varid = OrderedDict()
        self._variables_by_uid = dict()

        for var in default_variables:
            vid = self._get_varid(var)
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
        """Get the variable with an instance id, or variables with a sequence of ids.

        Raises `KeyError` if a variable is not found.

        Args:
            instance_id: Id(s) of the variable instance(s) - the `id` of the component, not the varid.

        Returns:
            The variable, or a sequence of variables.
        """
        if isinstance(instance_id, str):
            if instance_id in self._variables_by_uid:
                return self._variables_by_uid[instance_id]
        else:
            return [self.get_variable(x) for x in instance_id]
        raise KeyError(f'Variable {instance_id} not found - try get_default_variable with the varid')

    def get_default_variable(self, variable_id: str, index: int = -1) -> Variable:
        """Get the default instance of a variable by varid.

        Raises `KeyError` if there is no variable with the varid.

        Args:
            variable_id: The varid (`{section}.{key}.{subindex}`) of the variable.
            index: Which instance of the varid to return, in the order they were added; -1 is the most recent.

        Returns:
            The variable.
        """
        if variable_id in self._variables_by_varid:
            return list(self._variables_by_varid[variable_id].values())[index]
        raise KeyError(f'Variable type {variable_id} not found - a first application of this variable must be added.')

    def duplicate_variable(self, instance_id: str) -> Variable:
        """Make a deep copy of a variable with a new id, and add it to the provider.

        Raises `KeyError` if the instance is not found.

        Args:
            instance_id: Id(s) of the variable instance(s) - the `id` of the component, not the varid.

        Returns:
            The new variable.
        """
        if instance_id in self._variables_by_uid:
            v1 = self._variables_by_uid[instance_id]
            v2 = cast(Variable, copy.deepcopy(v1))
            v2.id = v2.generate_new_id()
            vid = self._get_varid(v2)
            self._variables_by_varid[vid][v2.id] = v2
            self._variables_by_uid[v2.id] = v2
            return v2
        raise KeyError(f'Variable {instance_id} not found - try get_default_variable with the varid')

    def add_variable(self, var: Variable) -> str:
        """Add a variable instance, so that it can be got by instance id and by varid.

        The most recently added instance of a varid becomes its default.

        Args:
            var: The variable, or sequence of variables.

        Returns:
            The id of the variable.
        """
        vid = self._get_varid(var)
        if not vid in self._variables_by_varid:
            self._variables_by_varid[vid] = OrderedDict()

        self._variables_by_varid[vid][var.id] = var
        self._variables_by_uid[var.id] = var

        return var.id

    def get_varids(self) -> tuple[str, ...]:
        """The varids served by the provider.

        In the order that they were first added.

        Returns:
            Tuple of varids.
        """
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

            varid = self._get_varid(var)
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
        """Restore the variables of the provider from another provider.

        When the provider is pickled only the ids of its variables are kept; this restores the variables from, for example, the store.

        Args:
            variable_provider: Provider (e.g. a database store) from which to recover the variables by id.
        """
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

            varid = self._get_varid(var)
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
