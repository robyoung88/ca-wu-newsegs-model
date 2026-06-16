"""
Classes and mixins related to serialising and unserialising objects
"""
from typing import Any


class SerialiseToDictMixin:
    _constructor_class: str

    def to_dict(self):
        return (
            {
                'class': self.__class__.__name__,
                'constructor_class': self._constructor_class,
            }
            .update(
                {
                    prop: self._represent(value)
                    for prop, value in self.__dict__.items()
                }
            )
        )
    
    def _represent(self, value):
        if isinstance(value, object):
            if hasattr(value, 'to_dict'):
                return value.to_dict() # pyright: ignore[reportAttributeAccessIssue]
            else:
                return str(value)
        else:
            return value
        
    def update(self, config: dict[str, Any]):
        config = config.copy()
        classname = config.pop('class', None)
        if not classname is None:
            if self.__class__.__name__ != classname:
                raise ValueError(f'Configuration for class {classname} cannot be applied to an instance of class {self.__class__.__name__}')
            
        config.pop('constructor_class', None)
        
        for k, v in config.items():
            if isinstance(v, dict):
                cc = v.get('constructor_class', None)
                if cc is not None:
                    ...
                    


        
    @classmethod
    def from_dict(cls, config: dict[str, Any]):
        ...

