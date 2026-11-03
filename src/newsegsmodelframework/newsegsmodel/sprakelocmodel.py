"""An extended Sprake NewSEGS Energy Model.

Extends the model of Dr David Sprake by making the environmental conditions
adaptable to the latitude/longitude of the selected site.
"""

import copy
from functools import lru_cache, singledispatchmethod
from typing import cast, override

from newsegsmodelframework.core.environment import pvgis_newa_env_servers
from newsegsmodelframework.core.environment.dummy_env_servers import DummyWiderEnv
from newsegsmodelframework.core.environment.environment_servers import NewsegsLocalEnvironment, NewsegsWiderEnvironment
from newsegsmodelframework.core.location.location import RaisedLocation
from newsegsmodelframework.core.timespan.timespan import SECONDS_TO_DAYS, RegTimeSpan, TimeSpan
from newsegsmodelframework.core.trackeddata import revision_dataclass
from newsegsmodelframework.newsegsgeneration.newsegsgeneration import NewsegsGeneration
from newsegsmodelframework.newsegsgeneration.sprakegeneration import get_sprake_ned100
from newsegsmodelframework.newsegsgeneration.sprakelocgeneration import SprakeLocGeneration
from newsegsmodelframework.newsegsmodel.newsegsmodel import NewsegsModelProperty
from newsegsmodelframework.newsegsmodel.sprakemodel import _DEFAULT_LOCATION, SprakeModel, SprakeModelConfig


@lru_cache
def get_sprakeloc_environment_server():
    server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv()
    return server

@lru_cache
def get_sprakeloc_wider_env_server():
    return DummyWiderEnv()

# TODO: Check if the run period is OK for NEWA and PVGIS
@revision_dataclass
class SprakeLocModelConfig(SprakeModelConfig):
    """Configuration of the location-aware Sprake NewSEGS Energy Model.
    
    Attributes:
        timestep: Timestep of the model.
        run_period: The time span over which the model is run. (may differ from the nominal period - currently this nominal period is not implemented)
    """

class SprakeLocModel(SprakeModel):
    _name = 'Sprake Location-aware Energy Model'
    model_type = 'sprakeloc'
    _version = '0.0.1'

    # _excluded_attributes are as per SprakeModel

    # Overridden descriptors
    generation = NewsegsModelProperty(
        default = SprakeLocGeneration.from_none, 
        oftype = SprakeLocGeneration
    )

    @singledispatchmethod
    def __init__(
        self,
        dispatch_arg: str | SprakeModel | NewsegsGeneration,
        *args,
        **kwargs,
    ) -> None:
        super().__init__(dispatch_arg, *args, **kwargs)

    @__init__.register(str)
    def _from_str(self, name: str, *args, **kwargs) -> None:
        mod_gen = SprakeLocGeneration(get_sprake_ned100())
        mod_gen.location = copy.copy(_DEFAULT_LOCATION)
        cast(RaisedLocation, mod_gen.generator.generators[1].location).height_agl = 2.

        self.__init__(mod_gen, name=name, *args, **kwargs)

    def _generate_config(self, *args, **kwargs) -> SprakeLocModelConfig:
        return SprakeLocModelConfig(*args, **kwargs)
    _config: SprakeLocModelConfig

    @override
    @SprakeModel.local_env.getter
    def local_env(self) -> NewsegsLocalEnvironment:
        """The local environment server; the default PVGIS/NEWA server is created on first use.
        """
        try:
            return self._local_environment_server
        except AttributeError:
            self._local_environment_server = get_sprakeloc_environment_server()
            return self._local_environment_server

    @override
    @SprakeModel.wider_env.getter
    def wider_env(self) -> NewsegsWiderEnvironment:
        """The wider environment server; the default Sprake server is created on first use.
        """
        try:
            return self._wider_environment_server
        except AttributeError:
            self._wider_environment_server = get_sprakeloc_wider_env_server()
            return self._wider_environment_server    
