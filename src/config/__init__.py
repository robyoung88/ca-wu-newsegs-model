"""Configuration constants for `newsegsmodelframework` and `newsegsmodelapp`

Provides a dictionary-like interface (`settings`) via `dynaconf`. Modify 
settings via environmental variables, settings.toml, or secrets.toml

Exports:
    settings: dynaconf.LazySettings instance containing configuration constants.
"""
from .config import settings
