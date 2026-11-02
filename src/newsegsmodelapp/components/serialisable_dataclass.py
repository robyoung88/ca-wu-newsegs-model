"""Provides a dataclass with from_dict and as_dict methods"""
import inspect

from dataclasses import dataclass
from dataclasses import asdict as dc_asdict

@dataclass
class SerialisableDataclass:
    """Serialisable Dataclass.

    TODO: Add a description.
    """
    @classmethod
    def from_dict(cls, env):      
        """From dict.

        TODO: Add a description.

        Args:
            env: TODO.

        Returns:
            TODO.
        """
        return cls(**{
            k: v for k, v in env.items() 
            if k in inspect.signature(cls).parameters
        })
    
    def as_dict(self):
        """As dict.

        TODO: Add a description.

        Returns:
            TODO.
        """
        return dc_asdict(self)
