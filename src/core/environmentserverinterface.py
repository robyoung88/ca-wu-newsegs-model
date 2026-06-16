"""
Interface for serving environmental data
"""
from __future__ import annotations

from abc import ABCMeta, abstractmethod

from core.environment import environment_servers

class EnvironmentServerIntrface(metaclass = ABCMeta):
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
