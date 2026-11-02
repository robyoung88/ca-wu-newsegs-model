"""Provides a dataclass with from_dict and as_dict methods"""
import inspect

from dataclasses import dataclass
from dataclasses import asdict as dc_asdict

@dataclass
class SerialisableDataclass:
    """A dataclass which can be converted to and from a dictionary, e.g. for JSON.
    """
    @classmethod
    def from_dict(cls, env):      
        """Create an instance from a dictionary.

        Keys which are not parameters of the class are ignored.

        Args:
            env: Dictionary of the values.

        Returns:
            The instance.
        """
        return cls(**{
            k: v for k, v in env.items() 
            if k in inspect.signature(cls).parameters
        })
    
    def as_dict(self):
        """The dataclass as a dictionary.

        Returns:
            The dictionary.
        """
        return dc_asdict(self)
