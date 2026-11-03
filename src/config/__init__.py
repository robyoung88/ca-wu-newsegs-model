"""Configuration constants for `newsegsmodelframework` and `newsegsmodelapp`

Provides a dictionary-like interface (`settings`) via `dynaconf`. Modify
settings via environmental variables, settings.toml, or secrets.toml

The environment (development, testing or production) is selected by the
`NEWSEGS_ENV` environment variable; see `config.environment`.

Exports:
    settings: dynaconf.LazySettings instance containing configuration constants.
    environment: Functions for querying the current environment.
"""
from .config import settings
from . import environment
