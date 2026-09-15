from dataclasses import dataclass
from typing import override

from newsegsmodelapp.components.serialisable_dataclass import SerialisableDataclass
from newsegsmodelframework.newsegsvariable import variable


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
    subindex: int = 0

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

@dataclass
class VariableInstanceParameterComponentID(VariableInstanceComponentID):
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
