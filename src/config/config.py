"""Settings for the `dynaconf` module.

Used to ensure that `dynaconf` picks up settings from the correct file paths
and responds to environment variables.
"""

from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    settings_files=['settings.toml', '.secrets.toml'],
    root_path = 'src',
    dotenv_path = './..',
    load_dotenv = True,
    environments = True,
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
