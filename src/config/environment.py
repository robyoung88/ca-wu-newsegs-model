"""The deployment environment the app is running in.

A single environment variable, `NEWSEGS_ENV`, selects the environment. It is also
the `dynaconf` environment switcher (see `config.py`), so the same value chooses
the `[development]`, `[testing]` or `[production]` section of `settings.toml` and
decides behaviour outside of `dynaconf`, such as whether the Dash app runs with
debug tools.

`NEWSEGS_ENV` may be set in the process environment or in the `.env` file. When it
is unset, the environment is `development`.

Values (case-insensitive):
    development: Local development. Dash debug tools are enabled.
    testing: Automated tests.
    production: Deployment. Debug tools are never enabled.
    spraketest: A variant of `testing` used to reproduce the original Sprake model.
"""
ENV_VAR = 'NEWSEGS_ENV'

DEVELOPMENT = 'development'
TESTING = 'testing'
PRODUCTION = 'production'
SPRAKETEST = 'spraketest'

VALID_ENVIRONMENTS = (DEVELOPMENT, TESTING, PRODUCTION, SPRAKETEST)


def get_environment() -> str:
    """Return the current environment name, in lower case.

    Read from `dynaconf`, so that `.env` files are taken into account.

    Raises:
        ValueError: If `NEWSEGS_ENV` is set to an unrecognised value.
    """
    from .config import settings
    env = str(settings.current_env or DEVELOPMENT).lower()
    if env not in VALID_ENVIRONMENTS:
        raise ValueError(
            f'{ENV_VAR}={env!r} is not recognised; expected one of {VALID_ENVIRONMENTS}'
        )
    return env


def is_development() -> bool:
    """True when running in the development environment."""
    return get_environment() == DEVELOPMENT


def is_testing() -> bool:
    """True when running in a testing environment (including `spraketest`)."""
    return get_environment() in (TESTING, SPRAKETEST)


def is_production() -> bool:
    """True when running in the production environment."""
    return get_environment() == PRODUCTION


def is_spraketest() -> bool:
    """True when reproducing the original Sprake model (the `spraketest` environment)."""
    return get_environment() == SPRAKETEST
