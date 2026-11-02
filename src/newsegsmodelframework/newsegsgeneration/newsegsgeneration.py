"""Provides abstract base class for NewSEGS Generation Module."""

from abc import abstractmethod
from dataclasses import field
from typing import Mapping, Sequence, override

import pandas as pd

from newsegsmodelframework.core import NewsegsModule, newsegscomponent
from newsegsmodelframework.core import generation
from newsegsmodelframework.core.generation.generators import NewsegsGeneratorProperty
from newsegsmodelframework.core.newsegsmoduleresult import NewsegsModuleResult
from newsegsmodelframework.core.newsegsmoduleresult import filter_meters
from newsegsmodelframework.core import location as modlocation
from newsegsmodelframework.core.trackeddata import ConfigurationMixin, DataWithRevision, revision_dataclass


@revision_dataclass
class NewsegsGenerationConfig(DataWithRevision):
    """Newsegs Generation Config.

    TODO: Add a description.
    """
    location: modlocation.Location | list[modlocation.Location] = field(default_factory = modlocation.Location.from_none)
    """The location of the generators / power plants.
    
    Generally, the location will itself be an attribute of the generator
    and so cannot be accessed until a generator is assigned.

    Returns:
        Location or sequence of locations of the generators / power plants.
    """


class NewsegsGeneration(NewsegsModule):
    """Abstract base class for NewSEGS Generation Module."""
    component_type = 'generation'

    @override
    def _generate_config(self, *args, **kwargs) -> NewsegsGenerationConfig:
        return NewsegsGenerationConfig(*args, **kwargs)
    _config: NewsegsGenerationConfig # pyright: ignore[reportIncompatibleVariableOverride]

    @override
    def update(self, config):
        if isinstance(config, dict):
            has_location = ('_config' in config.keys())
        else:
            has_location = True
        super().update(config)
        # After updating, trigger any logic on location
        if has_location:
            self.location = self._config.location

    @override
    def get_component_attributes(self) -> tuple[str, ...]:
        """A tuple of all the attributes of the object that are themselves NewsegsComponents

        Excludes the generators, as these are not handled in the component database.
        Returns:
            tuple[str, ...]: Names of attributes which are NewsegsComponents
        """
        atts = super().get_component_attributes()
        type_ = type(self)
        return tuple(x for x in atts if not isinstance(getattr(type_, x), NewsegsGeneratorProperty))

def get_generation_meters(
    gen_results: NewsegsModuleResult
) -> pd.DataFrame:
    """Extract generation meters from a generation module results.

    Also augments the returned data with total generation export.

    Args:
        gen_results: Results from a generation module.

    Returns:
        Data frame containing generation meter values and a total export column.
    """
    gen_meters = filter_meters(gen_results, 'export')
    gen_data = (
        gen_results.meters_to_pandas()
        .loc[:, gen_meters]
        .assign(
            generation_export = lambda df: df.apply(sum, axis=1)
        )
    )
    return gen_data
