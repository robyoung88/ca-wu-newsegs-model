

from typing import override

from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.newsegsgeneration.sprakegeneration import SprakeGeneration


class SprakeLocGeneration(SprakeGeneration):
    """Implementation of NewsegsGeneration for Sprake Location-Aware NewSEGS Model."""

    _name = 'Sprake Location-Aware Generation Module.'

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
