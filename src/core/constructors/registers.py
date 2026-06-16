"""
Registers of classes implementing SerialiseToDictMixin.
"""
import inspect
from types import ModuleType
from typing import Literal

CONSTRUCTOR_CLASS = Literal[
    'NewsegsComponent',
    'NewsegsModule',
    'Environment',
    'Generator',
    'Location',
    'Timespan',
]

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

def get_register(constructor_class: CONSTRUCTOR_CLASS) -> dict[str, type]:
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
        case 'Timespan':
            return get_timespan_register()
        case _:
            raise ValueError(f'constructor_class not recognised: {constructor_class}')
