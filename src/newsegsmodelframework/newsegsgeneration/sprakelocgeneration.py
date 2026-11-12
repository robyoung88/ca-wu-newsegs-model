from __future__ import annotations

import os
from typing import override

import numpy as np
import pandas as pd

from newsegsmodelframework.core.generation.generators import WindTurbineElecGenerator
from newsegsmodelframework.core.location.location import Location, RaisedLocation
from newsegsmodelframework.newsegsgeneration.sprakegeneration import SprakeGeneration, get_sprake_ned100

from config import settings
from newsegsmodelframework import STATICDATA
_LOOKUP_DIR = settings.get('SprakeDataLoc', STATICDATA / 'sprake_data')

NOMINAL_WT_HEIGHT = 15.0
"""Default hub height (m) of the wind turbine of the location-aware Sprake model. The Sprake model
uses `sprakegeneration.NOMINAL_WT_HEIGHT`, the height of its default wind speed series."""

def get_sprake_proven_12(hub_height: float = NOMINAL_WT_HEIGHT):
    """The Proven 12 kW wind turbine of the Sprake model, with the power curve from the user manual (see data directory).

    Args:
        hub_height: Height of the rotor centre (m).

    Returns:
        The turbine.
    """
    cpcurve = (
        pd.read_excel(
            os.path.join(
                _LOOKUP_DIR,
                'power-curve-proven-12.xlsx'
            ),
            sheet_name='power_curve',
            header=0
        )
        .loc[:,['wind_speed','coeff_power']]
    )
    tloc = RaisedLocation.from_none()
    tloc.height_agl = hub_height
    turbine = WindTurbineElecGenerator.from_characteristics(
        cut_in=3.5,
        cut_out=50.0,
        rated_power=100.0,
        swept_area=np.pi*(0.5 * 8.5)**2,
        hub_height=hub_height,
        name="Proven 12 WT (Sprake)",
        loc = tloc,
        cp_curve=cpcurve.to_numpy().T
    )
    turbine.revision = 0
    turbine._config._last_syncronised = -1

    return turbine


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
        return cls(get_sprake_proven_12(NOMINAL_WT_HEIGHT))

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
