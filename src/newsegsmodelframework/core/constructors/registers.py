"""
Registers of classes implementing SerialiseToDictMixin.

Note the lazy imports, as SerialiseToDictMixin is dependent upon 
core.constructors, so to avoid circularity these imports can only
occur at runtime.
"""
import inspect
from types import ModuleType
from typing import Any, Callable, Type

from newsegsmodelframework.core.serialisation import T

class NakedConstructor:
    """Interface of a class that can be constructed from a dictionary.

    Registers hold, for each class name, an object with this interface. For NewSEGS classes it is the class itself
    (they implement `from_dict`); for foreign types such as pandas timestamps it is a stand-in object whose
    `from_dict` builds the instance.
    """
    def to_dict(self) -> dict[str, Any]: ...
    def update(self, config: dict[str, Any]): ...

    @classmethod
    def unserialise_dict(cls, config: dict[str, Any]) -> dict[str, Any]: ...

    @classmethod
    def from_dict(cls: Type[T], config: dict[str, Any]) -> T:
        """Build an instance from its serialised dictionary.

        Args:
            config: Dictionary of the serialised state.

        Returns:
            The instance.
        """
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
    # A module with no `__all__` is searched for the public classes it defines
    objnames = getattr(pymod, '__all__', None)
    if objnames is None:
        objnames = [
            name for name, obj in vars(pymod).items()
            if isinstance(obj, type) and obj.__module__ == pymod.__name__ and not name.startswith('_')
        ]
    for objname in objnames:
        obj = getattr(pymod, objname)
        if not inspect.isabstract(obj):
            try:
                if issubclass(obj, parentclass):
                    odict[obj.__name__] = obj
            except TypeError:
                continue
    return odict

def _import_modules(*names: str) -> list[ModuleType]:
    """Import modules by name, expanding each package into all of its submodules, recursively.

    The registries search the modules that define the classes, rather than the packages that
    re-export them, so that the registries do not depend upon what the packages expose. Naming
    a package means that modules later added to it are searched without needing to be listed.
    """
    import importlib
    import pkgutil
    modules = []
    for name in names:
        pymod = importlib.import_module(name)
        if not hasattr(pymod, '__path__'):
            modules.append(pymod)
            continue
        for modinfo in pkgutil.walk_packages(pymod.__path__, pymod.__name__ + '.'):
            if not modinfo.ispkg:
                modules.append(importlib.import_module(modinfo.name))
    return modules

_FW = 'newsegsmodelframework.'

CONSTRUCTOR_CLASS_REGISTER: dict[str, Callable[[], dict[str, object] | dict[str, NakedConstructor]]] = {}

def register_constructor_class(cc_name: str):
    """Add a constructor class registry function to `CONSTRUCTOR_CLASS_REGISTER`

    Registration is necessary to use [find_constructor][newsegsmodelframework.core.find_constructor] for a new constructor_class
    
    The decorated function should take no arguments, and return a dictionary
    of constructors for classes which implement a `.from_dict` constructor
    class method.

    A typical pattern for creating an appropriate dictionary is to use the following
    pattern:

    Example:
        ```python
        from newsegsmodelframework.core.constructors.registers import register_constructor_class, get_subclasses_in_module
        
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

@register_constructor_class('DataWithRevision')
def get_datawithrevision_register():
    """
    Configuration data classes
    """
    from newsegsmodelframework.core import newsegscomponent
    CONSTRUCTORS = {}
    for pymod in _import_modules(
        _FW + 'core',
        _FW + 'newsegsmodel',
        _FW + 'newsegsfinance',
        _FW + 'newsegsgrid',
        _FW + 'newsegsgeneration',
        _FW + 'newsegscs',
        _FW + 'newsegsmetamodel',
        _FW + 'newsegsproject',
        _FW + 'newsegssensitivity',
        _FW + 'newsegsvariable',
    ):
        CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, newsegscomponent.DataWithRevision)
        )

    return CONSTRUCTORS

@register_constructor_class('NewsegsComponent')
def get_newsegscomponent_register():
    """
    Non-NewsegsModule classes that are NewsegsComponents
    """
    from newsegsmodelframework.core import newsegscomponent
    import newsegsmodelframework.newsegsvariable as newsegsvariable
    
    COMPONENT_CONSTRUCTORS = {}
    for pymod in _import_modules(
        _FW + 'newsegsmodel',
        _FW + 'newsegsfinance',
        _FW + 'core.newsegscomponent',
        _FW + 'newsegssensitivity',
        _FW + 'newsegsmetamodel',
        _FW + 'newsegsproject',
    ):
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

    MODULE_CONSTRUCTORS = {}
    for pymod in _import_modules(
        _FW + 'newsegsgeneration',
        _FW + 'newsegsgrid',
        _FW + 'newsegscs',
    ):
        MODULE_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, newsegsmodule.NewsegsModule)
        )
    
    return MODULE_CONSTRUCTORS

@register_constructor_class('Generator')
def get_generator_register():
    """Register of the electricity generators: the concrete subclasses of `ABCElecGenerator`.

    Returns:
        Dictionary of constructors by class name.
    """
    from newsegsmodelframework.core.generation import generators
    
    GENERATOR_CONSTRUCTORS = {}
    for pymod in [generators]:
        GENERATOR_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, generators.ABCElecGenerator)
        )
    
    return GENERATOR_CONSTRUCTORS

@register_constructor_class('Environment')
def get_environment_register():
    """Register of the environment servers: concrete subclasses of `NewsegsLocalEnvironment` and `NewsegsWiderEnvironment`.

    Returns:
        Dictionary of constructors by class name.
    """
    from newsegsmodelframework.core.environment import (
        dummy_env_servers, environment_servers, inmem_env_servers
    )

    ENVIRONMENT_CONSTRUCTORS = {}
    for pymod in [dummy_env_servers, inmem_env_servers]:
        ENVIRONMENT_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, environment_servers.NewsegsLocalEnvironment)
        )
        ENVIRONMENT_CONSTRUCTORS.update(
            get_subclasses_in_module(pymod, environment_servers.NewsegsWiderEnvironment)
        )
    
    return ENVIRONMENT_CONSTRUCTORS

@register_constructor_class('Location')
def get_location_register():
    """Register of the locations: concrete subclasses of `Location`.

    Returns:
        Dictionary of constructors by class name.
    """
    from newsegsmodelframework.core.location import location

    LOCATION_CONSTRUCTORS = {}
    for pymod in [location]:
        LOCATION_CONSTRUCTORS.update(get_subclasses_in_module(pymod, location.Location))
            
    return LOCATION_CONSTRUCTORS

@register_constructor_class('TimeSpan')
def get_timespan_register():
    """Register of the time spans: concrete subclasses of `TimeSpan`.

    Returns:
        Dictionary of constructors by class name.
    """
    from newsegsmodelframework.core.timespan import timespan

    TIMESPAN_CONSTRUCTORS = {}
    for pymod in [timespan]:
        TIMESPAN_CONSTRUCTORS.update(get_subclasses_in_module(pymod, timespan.TimeSpan))
            
    return TIMESPAN_CONSTRUCTORS

@register_constructor_class('Timestamp')
def get_timestamp_register():
    """Register of the constructor of a pandas `Timestamp` from its dictionary.

    Returns:
        Dictionary with the constructor.
    """
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
    """Register of the constructor of a pandas `Timedelta` from its dictionary.

    Returns:
        Dictionary with the constructor.
    """
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
    """Register of the constructor of a `datetime.datetime` from its dictionary (an ISO format string).

    Returns:
        Dictionary with the constructor.
    """
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
    """Register of the pvlib location wrappers: concrete subclasses of `PVLibLocation`.

    Returns:
        Dictionary of constructors by class name.
    """
    from newsegsmodelframework.core.location import location

    LOCATION_CONSTRUCTORS = {}
    for pymod in [location]:
        LOCATION_CONSTRUCTORS.update(get_subclasses_in_module(pymod, location.PVLibLocation))
            
    return LOCATION_CONSTRUCTORS

@register_constructor_class('Variable')
def get_variable_register():
    """Register of the variables; the same classes as the component register, which includes the variable constructors.

    Returns:
        Dictionary of constructors by class name.
    """
    return CONSTRUCTOR_CLASS_REGISTER['NewsegsComponent']()

# Storage for classes dynamically added at runtime
EXTRA_CLASS_REGISTER: dict[str, dict[str, type]] = {}

def register_custom_class(constructor_class: str, cls: type):
    """
    Appends a new class definition at runtime to a specified constructor category.
    
    Args:
        constructor_class (str): The category name (e.g., 'NewsegsComponent', 'Generator')
        cls (type): The class definition to add.
    """
    if constructor_class not in EXTRA_CLASS_REGISTER:
        EXTRA_CLASS_REGISTER[constructor_class] = {}
    
    # Register by class name
    EXTRA_CLASS_REGISTER[constructor_class][cls.__name__] = cls

def get_register(constructor_class: str) -> dict[str, object] | dict[str, NakedConstructor]:
    """
    Returns a dictionary of classes indexed by name for construction, 
    combining static module-inspected classes with dynamically added classes.
    """
    reg_func = CONSTRUCTOR_CLASS_REGISTER.get(constructor_class, None)
    if reg_func is None:
        raise ValueError(
            f'constructor_class not recognised: {constructor_class}; '
            f'available values are {list(CONSTRUCTOR_CLASS_REGISTER.keys())}'
        )

    # 1. Fetch static/module-based constructors
    constructors = reg_func()

    # 2. Append dynamically registered classes at runtime
    if constructor_class in EXTRA_CLASS_REGISTER:
        constructors.update(EXTRA_CLASS_REGISTER[constructor_class])  # type: ignore
        
    return constructors
