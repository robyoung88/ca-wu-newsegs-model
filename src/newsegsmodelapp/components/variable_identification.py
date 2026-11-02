"""Identifying the components of variables.

The ids of the components of the interface are dictionaries; these dataclasses make and read them for the components of a variable.
"""
from dataclasses import dataclass
from typing import override

from newsegsmodelapp.components.serialisable_dataclass import SerialisableDataclass
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsvariable.lightweight_variable import LightweightVariable


@dataclass
class VariableComponentID(SerialisableDataclass):
    """Data to describe some component associated with a variable."""
    type: str
    purpose: str = 'variable'
    supersection: str = 'global'
    section: str = 'global'
    key: str = 'component'

    @classmethod
    def from_variable(
        cls,
        var: variable.Variable,
        type: str = 'notype',
        supersection: str = 'deterministic',
    ):
        """Create the id of a component of a variable.

        The section and key are those of the variable (the first, if it has several).

        Args:
            var: The variable.
            type: The type field of the component id.
            supersection: The supersection of the container.

        Returns:
            The id.
        """
        section = var.interface_section
        section = 'None' if section is None else section
        if not isinstance(section, str):
            # Take the first section if is a sequence
            section = section[0]
        key = var.interface_key
        if not isinstance(key, str):
            key = key[0]
    
        return cls(
            type = type,
            supersection = supersection,
            section = section,
            key = key,
        )

    @classmethod
    def from_lightweight_variable(
        cls,
        var: LightweightVariable,
        type: str = 'notype',
        supersection: str = 'deterministic',
    ):
        """Create the id of a component of a lightweight variable.

        The section and key are those of the variable (the first, if it has several).

        Args:
            var: The variable.
            type: The type field of the component id.
            supersection: The supersection of the container.

        Returns:
            The id.
        """
        section = var.interface_section
        section = 'None' if section is None else section
        if not isinstance(section, str):
            # Take the first section if is a sequence
            section = section[0]
        key = var.interface_key
        if not isinstance(key, str):
            key = key[0]
    
        return cls(
            type = type,
            supersection = supersection,
            section = section,
            key = key,
        )


@dataclass
class VariableInstanceComponentID(VariableComponentID):
    """Identification of a component of a variable instance: adds the subindex, which distinguishes instances of the same key.
    """
    subindex: int|str = 0

    @override
    @classmethod
    def from_variable(
        cls, 
        var: variable.Variable,
        *args,
        **kwargs
    ):
        obj = super().from_variable(var, *args, **kwargs)
        obj.subindex = var.interface_subindex
        return obj

    @override
    @classmethod
    def from_lightweight_variable(
        cls, 
        var: LightweightVariable,
        *args,
        **kwargs
    ):
        obj = super().from_lightweight_variable(var, *args, **kwargs)
        obj.subindex = var.interface_subindex
        return obj

@dataclass
class VariableInstanceParameterComponentID(VariableInstanceComponentID):
    """Identification of a component for one parameter of a variable instance: adds the index of the parameter and, for an array, the position within it.
    """
    parameter_index: int = 0
    vector_location: int = 0
    purpose: str = 'parameter'

    @override
    @classmethod
    def from_variable(
        cls,
        *args,
        parameter_index: int = 0,
        vector_location: int = 0,
        purpose: str = 'parameter',
        **kwargs
    ):
        obj = super().from_variable(*args, **kwargs)
        obj.parameter_index = parameter_index
        obj.vector_location = vector_location
        obj.purpose = purpose
        return obj

    @override
    @classmethod
    def from_lightweight_variable(
        cls,
        *args,
        parameter_index: int = 0,
        vector_location: int = 0,
        purpose: str = 'parameter',
        **kwargs
    ):
        obj = super().from_lightweight_variable(*args, **kwargs)
        obj.parameter_index = parameter_index
        obj.vector_location = vector_location
        obj.purpose = purpose
        return obj
