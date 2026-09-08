"""Provides a dataclass with from_dict and as_dict methods"""
import inspect

from dataclasses import dataclass
from dataclasses import asdict as dc_asdict

@dataclass
class SerialisableDataclass:
    @classmethod
    def from_dict(cls, env):      
        return cls(**{
            k: v for k, v in env.items() 
            if k in inspect.signature(cls).parameters
        })
    
    def as_dict(self):
        return dc_asdict(self)
