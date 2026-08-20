"""
Registers of classes implementing SerialiseToDictMixin.

Note the lazy imports, as SerialiseToDictMixin is dependent upon 
core.constructors, so to avoid circularity these imports can only
occur at runtime.
"""
import inspect
from types import ModuleType
from typing import Any, Callable, Literal

class NakedConstructor:
    def from_dict(self, config: dict[str, Any]) -> object:
        ...

def get_subclasses_in_module(
    pymod: ModuleType,
    parentclass: type
) -> dict[str, type]:
    """Get all children of a parent class in a module.

    Args:
        pymod (ModuleType): Module to search through
        parentclass (type): class to filter for in module

    Returns:
        dict[str, type]: Dictionary keyed by class names, with values set
            to the class definition; use of a `.from_dict(dict)` classmethod
            on these classes should result in an instance of the class.
    """
    odict = {}
    for objname in pymod.__all__:
        obj = getattr(pymod, objname)
        if not inspect.isabstract(obj):
            try:
                if issubclass(obj, parentclass):
                    odict[obj.__name__] = obj
            except TypeError:
                continue
    return odict

CONSTRUCTOR_CLASS_REGISTER: dict[str, Callable[[], dict[str, object] | dict[str, NakedConstructor]]] = {}

def register_constructor_class(cc_name: str):
    """Add a constructor class registry function to `CONSTRUCTOR_CLASS_REGISTER`

    Registration is necessary to use [core.find_constructor][] for a new constructor_class
    
    The decorated function should take no arguments, and return a dictionary
    of constructors for classes which implement a `.from_dict` constructor
    class method.

    A typical pattern for creating an appropriate dictionary is to use the following
    pattern:

    Example:
        ```python
        from core import register_constructor_class
        
        @register_constructor_class('my_constructor_class')
        def get_mcc_constructors():
            import my_constructor_class_module
            import also_implements_my_constructor_class_mod

            mods = [
                my_constructor_class_mod, 
                also_implements_my_constructor_class_mod
            ]
            constructors = {}
            for pymod in mods:
                constructors.update(
                    get_subclasses_in_module(
                        pymod, my_constructor_class_mod.MyConstructorClass
                    )
                )
            return constructors
        ```
    
    Args:
        cc_name (str): name used as _constructor_class in a SerialiseToDictMixin
    """
    def decorated(func):
        CONSTRUCTOR_CLASS_REGISTER[cc_name] = func
        return func
    return decorated

@register_constructor_class('NewsegsComponent')
def get_newsegscomponent_register():
    """
    Non-NewsegsModule classes that are NewsegsComponents
    """
    from newsegsmodelframework.core import newsegscomponent
    import newsegsmodelframework.newsegsmodel as newsegsmodel
    import newsegsmodelframework.newsegsfinance as newsegsfinance
    import newsegsmodelframework.newsegsvariable as newsegsvariable
    import newsegsmodelframework.newsegssensitivity as newsegssensitivity
    
    COMPONENT_CONSTRUCTORS = {}
    for pymod in [newsegsmodel, newsegsfinance, newsegscomponent, newsegssensitivity]:
        COMPONENT_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, newsegscomponent.NewsegsComponent)
        )

    # Variables use a form of polymorphic constructor and must be handled
    # differently
    COMPONENT_CONSTRUCTORS.update(newsegsvariable.VARIABLE_CONSTRUCTORS)
    
    return COMPONENT_CONSTRUCTORS

@register_constructor_class('NewsegsModule')
def get_newsegsmodule_register():
    """
    NewsegsModule classes

    All also inherit from NewsegsComponent, but we aim to slim down the registers.
    """
    from newsegsmodelframework.core import newsegsmodule
    import newsegsmodelframework.newsegsgeneration as newsegsgeneration
    import newsegsmodelframework.newsegsgrid as newsegsgrid
    import newsegsmodelframework.newsegscs as newsegscs

    MODULE_CONSTRUCTORS = {}
    for pymod in [newsegsgeneration, newsegsgrid, newsegscs]:
        MODULE_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, newsegsmodule.NewsegsModule)
        )
    
    return MODULE_CONSTRUCTORS

@register_constructor_class('Generator')
def get_generator_register():
    from newsegsmodelframework.core import generation
    
    GENERATOR_CONSTRUCTORS = {}
    for pymod in [generation]:
        GENERATOR_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, generation.ABCElecGenerator)
        )
    
    return GENERATOR_CONSTRUCTORS

@register_constructor_class('Environment')
def get_environment_register():
    from newsegsmodelframework.core import environment

    ENVIRONMENT_CONSTRUCTORS = {}
    for pymod in [environment]:
        ENVIRONMENT_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, environment.NewsegsLocalEnvironment)
        )
    for pymod in [environment]:
        ENVIRONMENT_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, environment.NewsegsWiderEnvironment)
        )
    
    return ENVIRONMENT_CONSTRUCTORS

@register_constructor_class('Location')
def get_location_register():
    from newsegsmodelframework.core import location

    LOCATION_CONSTRUCTORS = {}
    for pymod in [location]:
        LOCATION_CONSTRUCTORS.update(get_subclasses_in_module(pymod, location.Location))
            
    return LOCATION_CONSTRUCTORS

@register_constructor_class('TimeSpan')
def get_timespan_register():
    from newsegsmodelframework.core import timespan

    TIMESPAN_CONSTRUCTORS = {}
    for pymod in [timespan]:
        TIMESPAN_CONSTRUCTORS.update(get_subclasses_in_module(pymod, timespan.TimeSpan))
            
    return TIMESPAN_CONSTRUCTORS

@register_constructor_class('Timestamp')
def get_timestamp_register():
    import pandas as pd
    def timestamp_from_dict(config: dict[str, Any]) -> pd.Timestamp:
        config = config.copy()
        config.pop('constructor_class', None)
        config.pop('class', None)
        return pd.Timestamp(**config)
    
    retobj = NakedConstructor()
    setattr(retobj, 'from_dict', timestamp_from_dict)

    return {
        'Timestamp': retobj
    }

@register_constructor_class('Timedelta')
def get_timedelta_register():
    import pandas as pd

    def timedelta_from_dict(config: dict[str, Any]) -> pd.Timedelta:
        config = config.copy()
        config.pop('constructor_class', None)
        config.pop('class', None)
        return pd.Timedelta(**config)

    retobj = NakedConstructor()
    setattr(retobj, 'from_dict', timedelta_from_dict)
    return {
        'Timedelta': retobj
    }

@register_constructor_class('datetime')
def get_datetime_register():
    import datetime

    def datetime_from_dict(config: dict[str, Any]) -> datetime.datetime:
        config = config.copy()
        config.pop('constructor_class', None)
        config.pop('class', None)
        return datetime.datetime.fromisoformat(config['value'])

    retobj = NakedConstructor()
    setattr(retobj, 'from_dict', datetime_from_dict)
    return {
        'datetime': retobj
    }

@register_constructor_class('PVLib')
def get_pvlib_register():
    from newsegsmodelframework.core import location

    LOCATION_CONSTRUCTORS = {}
    for pymod in [location]:
        LOCATION_CONSTRUCTORS.update(get_subclasses_in_module(pymod, location.PVLibLocation))
            
    return LOCATION_CONSTRUCTORS

@register_constructor_class('Variable')
def get_variable_register():
    return CONSTRUCTOR_CLASS_REGISTER['NewsegsComponent']()

def get_register(constructor_class: str) -> dict[str, object] | dict[str, NakedConstructor]:
    """
    A dictionary of classes indexed by name for construction
    """
    reg = CONSTRUCTOR_CLASS_REGISTER.get(constructor_class, None)
    if reg is None:
        raise ValueError(f'constructor_class not recognised: {constructor_class}; available values are {CONSTRUCTOR_CLASS_REGISTER.keys()}')

    return reg()
    # match constructor_class:
    #     case 'NewsegsComponent':
    #         return get_newsegscomponent_register()
    #     case 'NewsegsModule':
    #         return get_newsegsmodule_register()
    #     case 'Environment':
    #         return get_environment_register()
    #     case 'Generator':
    #         return get_generator_register()
    #     case 'Location':
    #         return get_location_register()
    #     case 'TimeSpan':
    #         return get_timespan_register()
    #     case 'Timestamp':
    #         return get_timestamp_register()
    #     case 'Timedelta':
    #         return get_timedelta_register()
    #     case 'datetime':
    #         return get_datetime_register()
    #     case 'PVLib':
    #         return get_pvlib_register()
    #     case 'Variable':
    #         return get_newsegscomponent_register()
    #     case _:
    #         raise ValueError(f'constructor_class not recognised: {constructor_class}')
