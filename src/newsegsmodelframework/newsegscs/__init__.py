"""Consumption and storage (CS) modules of a NewSEGS Energy Model.

A CS module models the electrical demand of the site and the storage that serves it. The
base class is exposed here; the implementation used by the Sprake model is in `sprakecs`.

Modules:
    newsegscs: `NewsegsCS`, the base class, and `NewsegsCSConfig`.
    sprakecs: `SprakeCS`, the Sprake consumption and storage module.
    elexon_profiles: Elexon profile class demand profiles of domestic customers.
    ev_profiles: Electric vehicle charging profiles.
    dhw_profiles: Domestic hot water demand profiles.
    sprake_thermal_model: Space heating demand model of the Sprake model.
    constructors: Construction of a CS module from a dictionary.
"""
from .newsegscs import NewsegsCS, NewsegsCSConfig
__all__ = ['NewsegsCS', 'NewsegsCSConfig']
