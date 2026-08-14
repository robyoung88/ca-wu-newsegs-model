
from dynaconf import Dynaconf

settings = Dynaconf(
    envvar_prefix="DYNACONF",
    #envvar_prefix=False,
    #ignore_unknown_envvars=True,
    settings_files=['settings.toml', '.secrets.toml'],
    root_path = 'src',
    dotenv_path = './..',
    load_dotenv = True,
    environments = True,
)

# `envvar_prefix` = export envvars with `export DYNACONF_FOO=bar`.
# `settings_files` = Load these files in the order.
