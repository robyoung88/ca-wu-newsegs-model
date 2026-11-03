"""Settings for the `dynaconf` module.

Used to ensure that `dynaconf` picks up settings from the correct file paths
and responds to environment variables.
"""

from pathlib import Path

from dynaconf import Dynaconf

from .environment import ENV_VAR, DEVELOPMENT

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    # Fallback DB_PATH, RESULTS_STORE and DB_BACKUP_PATH for local running (not production)
    preload=[str(Path(__file__).parent / 'default_paths.py')],
    settings_files=['settings.toml', '.secrets.toml'],
    root_path = 'src',
    dotenv_path = './..',
    load_dotenv = True,
    environments = True,
    env_switcher = ENV_VAR,
    env = DEVELOPMENT,
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
# `env_switcher` = `export NEWSEGS_ENV=production` selects the [production] section;
#     see `config.environment`. ENV_FOR_DYNACONF is not used.
