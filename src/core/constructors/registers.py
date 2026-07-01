"""
Registers of classes implementing SerialiseToDictMixin.

Note the lazy imports, as SerialiseToDictMixin is dependent upon 
core.constructors, so to avoid circularity these imports can only
occur at runtime.
"""
import inspect
from types import ModuleType
from typing import Any, Literal

CONSTRUCTOR_CLASS = Literal[
    'NewsegsComponent',
    'NewsegsModule',
    'Environment',
    'Generator',
    'Location',
    'Timespan',
    'Timestamp',
    'Timedelta',
    'datetime',
    'PVLib'
]

class NakedConstructor:
    def from_dict(self, config: dict[str, Any]) -> object:
        ...

def get_subclasses_in_module(
    pymod: ModuleType,
    parentclass: type
) -> dict[str, type]:
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

def get_newsegscomponent_register():
    """
    Non-NewsegsModule classes that are NewsegsComponents
    """
    from core import newsegscomponent
    import newsegsmodel
    import newsegsfinance
    import newsegsvariable
    
    COMPONENT_CONSTRUCTORS = {}
    for pymod in [newsegsmodel, newsegsfinance]:
        COMPONENT_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, newsegscomponent.NewsegsComponent)
        )

    # Variables use a form of polymorphic constructor and must be handled
    # differently
    COMPONENT_CONSTRUCTORS.update(newsegsvariable.VARIABLE_CONSTRUCTORS)
    
    return COMPONENT_CONSTRUCTORS

def get_newsegsmodule_register():
    """
    NewsegsModule classes

    All also inherit from NewsegsComponent, but we aim to slim down the registers.
    """
    from core import newsegsmodule
    import newsegsgeneration
    import newsegsgrid
    import newsegscs

    MODULE_CONSTRUCTORS = {}
    for pymod in [newsegsgeneration, newsegsgrid, newsegscs]:
        MODULE_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, newsegsmodule.NewsegsModule)
        )
    
    return MODULE_CONSTRUCTORS

def get_generator_register():
    from core import generation
    
    GENERATOR_CONSTRUCTORS = {}
    for pymod in [generation]:
        GENERATOR_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, generation.ABCElecGenerator)
        )
    
    return GENERATOR_CONSTRUCTORS

def get_environment_register():
    from core import environment

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

def get_location_register():
    from core import location

    LOCATION_CONSTRUCTORS = {}
    for pymod in [location]:
        LOCATION_CONSTRUCTORS.update(get_subclasses_in_module(pymod, location.Location))
            
    return LOCATION_CONSTRUCTORS

def get_timespan_register():
    from core import timespan

    TIMESPAN_CONSTRUCTORS = {}
    for pymod in [timespan]:
        TIMESPAN_CONSTRUCTORS.update(get_subclasses_in_module(pymod, timespan.TimeSpan))
            
    return TIMESPAN_CONSTRUCTORS

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

def get_pvlib_register():
    from core import location

    LOCATION_CONSTRUCTORS = {}
    for pymod in [location]:
        LOCATION_CONSTRUCTORS.update(get_subclasses_in_module(pymod, location.PVLibLocation))
            
    return LOCATION_CONSTRUCTORS

def get_register(constructor_class: CONSTRUCTOR_CLASS) -> dict[str, object]:
    """
    A dictionary of classes indexed by name for construction
    """
    match constructor_class:
        case 'NewsegsComponent':
            return get_newsegscomponent_register()
        case 'NewsegsModule':
            return get_newsegsmodule_register()
        case 'Environment':
            return get_environment_register()
        case 'Generator':
            return get_generator_register()
        case 'Location':
            return get_location_register()
        case 'TimeSpan':
            return get_timespan_register()
        case 'Timestamp':
            return get_timestamp_register()
        case 'Timedelta':
            return get_timedelta_register()
        case 'datetime':
            return get_datetime_register()
        case 'PVLib':
            return get_pvlib_register()
        case _:
            raise ValueError(f'constructor_class not recognised: {constructor_class}')
