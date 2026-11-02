"""Core of the modelling framework: the base classes that everything else is built on.

Components (`NewsegsComponent`) are revision-tracked and serialisable objects: they can be
configured, saved to a dictionary and restored with `find_constructor`. Modules (`NewsegsModule`)
are the components of an energy model that are run over a `TimeSpan` to give results.
Locations, time spans and the environment servers that supply weather data support them.

Only the names used elsewhere in the framework and the app are imported here; the rest is
in the modules of the package.

Modules:
    newsegscomponent: `NewsegsComponent` and its variants, providers and the revision-tracked
        data classes.
    newsegsmodule: `NewsegsModule`, a component which is run to give a result.
    newsegsmoduleresult: `NewsegsModuleResult`, the result of running a module.
    newsegsmodelinterface, newsegsfinanceinterface: Interfaces of energy and finance models and their providers.
    newsegsmodeltimeinterface, resultsserverinterface, environmentserverinterface, newsegsresultprovider:
        Interfaces for the services that models rely on.
    lightweightnewsegscomponent: Lightweight descriptions of components.
    trackeddata: Revision tracking of data, and the observable containers and component properties.
    serialisation, serialisedtrackeddata: Conversion of objects to and from dictionaries.

Subpackages:
    constructors: Registries of the classes that can be constructed from dictionaries.
    environment: Servers of environmental (weather) data.
    generation: Electricity generators.
    location: Locations of sites.
    timespan: Blocks of time and the functions that index them.
"""
from .constructors.constructors import find_constructor
from .serialisedtrackeddata import SerialisedConfigurationMixin
from .location.location import Location, RaisedLocation, AspectLocation
from .timespan.timespan import TimeSpan, SECONDS_TO_HOURS
from .newsegscomponent import NewsegsComponent, RunnableNewsegsComponent, TableConfigNewsegsComponent
from .newsegsmodule import NewsegsModule

__all__ = [
    'find_constructor',
    'SerialisedConfigurationMixin',
    'Location',
    'RaisedLocation',
    'AspectLocation',
    'TimeSpan',
    'SECONDS_TO_HOURS',
    'NewsegsComponent',
    'RunnableNewsegsComponent',
    'TableConfigNewsegsComponent',
    'NewsegsModule',
]
