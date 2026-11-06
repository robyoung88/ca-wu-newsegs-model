"""Servers of environmental (weather) data.

The two base classes - the local environment of a site and the wider environment that affects
electricity prices - are exposed here; the implementations are in the modules.

Modules:
    environment_servers: The base classes `NewsegsLocalEnvironment` and `NewsegsWiderEnvironment`.
    inmem_env_servers: Implementations which hold their data in memory.
    dummy_env_servers: Implementations which provide placeholder data.
    environment_progress: Reporting waits for environmental data to the code running a model.
"""
from .environment_servers import NewsegsLocalEnvironment, NewsegsWiderEnvironment
__all__ = [
    'NewsegsLocalEnvironment',
    'NewsegsWiderEnvironment',
]
