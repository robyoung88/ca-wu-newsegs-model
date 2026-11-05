from __future__ import annotations

from typing import override

from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.newsegsgeneration.sprakegeneration import SprakeGeneration, get_sprake_ned100

NOMINAL_WT_HEIGHT = 15.0
"""Default hub height (m) of the wind turbine of the location-aware Sprake model. The Sprake model
uses `sprakegeneration.NOMINAL_WT_HEIGHT`, the height of its default wind speed series."""


class SprakeLocGeneration(SprakeGeneration):
    """Implementation of NewsegsGeneration for Sprake Location-Aware NewSEGS Model."""

    _name = 'Sprake Location-Aware Generation Module'

    @classmethod
    def from_none(cls) -> SprakeLocGeneration:
        """Create a location-aware Sprake generation module with the default wind turbine, at
        `NOMINAL_WT_HEIGHT`, and PV.

        Returns:
            The generation module.
        """
        return cls(get_sprake_ned100(NOMINAL_WT_HEIGHT))

    @override
    @SprakeGeneration.location.setter
    def location(self, loc: Location):
        # As an override to SprakeGeneration, this both sets the location in the module config
        # and passes that information through to the generators. In so doing, the generators are
        # expected to be able to maintain their existing height_agl, pitch and aspect when
        # provided with a raw Location, so we must make sure that the object is downcasted.
        pure_loc = Location(loc)
        self._config.location = pure_loc
        # Pass this point location on to the generators. The copy constructor sets the location
        # before the generator, which it then copies with the same locations.
        if self.generator is not None:
            self.generator.location = pure_loc
