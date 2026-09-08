"""Provides dataclass for holding critical result data"""
from dataclasses import dataclass
from dataclasses import asdict as dc_asdict
import inspect

@dataclass(frozen=True)
class ResultMeta:
    result_id: int
    result_directory_path: str
    type: str

    @classmethod
    def from_dict(cls, env):      
        return cls(**{
            k: v for k, v in env.items() 
            if k in inspect.signature(cls).parameters
        })
    
    def as_dict(self):
        return dc_asdict(self)
