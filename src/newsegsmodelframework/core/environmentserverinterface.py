"""
Interface for serving environmental data
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod

from newsegsmodelframework.core.environment import environment_servers

class EnvironmentServerInterface(metaclass = ABCMeta):
    """Interface of an object, such as an energy model, which serves environmental data.

    Provides access to the local environment server (conditions at the site) and the wider environment server
    (conditions affecting the wider electricity grid).
    """
    @property
    @abstractmethod
    def local_env(
        self
    ) -> environment_servers.NewsegsLocalEnvironment:
        """
        Access the local environment server
        """

    @local_env.setter
    @abstractmethod
    def local_env(
        self,
        local_environment_server: environment_servers.NewsegsLocalEnvironment
    ) -> None:
        """
        Replace the local environment server
        """

    @property
    @abstractmethod
    def wider_env(
        self
    ) -> environment_servers.NewsegsWiderEnvironment:
        """
        Access the wider environment server
        """

    @wider_env.setter
    @abstractmethod
    def wider_env(
        self, 
        wider_env_server: environment_servers.NewsegsWiderEnvironment
    ):
        """
        Replace the wider environment server
        """
