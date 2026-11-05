"""Fallback storage locations for running the app locally.

Preloaded by `dynaconf` (see `config.py`) before `settings.toml` and `.secrets.toml`,
so a value set in either file, or by a DYNACONF_* environment variable, takes
precedence over these.

The fallbacks live in a per-user application data directory:

    Windows:  %LOCALAPPDATA%\\NewSEGS
    macOS:    ~/Library/Application Support/NewSEGS
    Linux:    $XDG_DATA_HOME/newsegs (normally ~/.local/share/newsegs)

They are not applied in production, where DB_PATH, RESULTS_STORE and DB_BACKUP_PATH
must be configured explicitly (docker-compose.yml does so): a deployment that has lost
its configuration should fail rather than quietly write data to the home directory.

The database backups live beside the database, rather than on a separate drive, which
offers little protection against disk failure; hence "safe, if suboptimal".

HEARTBEAT_FILE, which holds no data, falls back to the system temporary directory in
every environment; production pins it in `settings.toml` to the path that the
docker-compose health check watches.

ENV_CACHE_PATH, the persistent cache of environmental data (see
`newsegsmodelframework.core.environment.environment_cache`), falls back to the user data
directory, or to the system temporary directory in production, where docker-compose.yml
keeps it on the database volume.

BACKGROUND_CALLBACK_CACHE_PATH, where the background callbacks of the app (such as fetching
the environmental data of a site) keep their jobs and results, holds nothing needed between runs,
so falls back to the system temporary directory in every environment.
"""
import os
import sys
import tempfile
from pathlib import Path


def user_data_dir() -> Path:
    """The per-user application data directory for this platform."""
    home = Path.home()
    if sys.platform == 'win32':
        base = os.environ.get('LOCALAPPDATA')
        return (Path(base) if base else home / 'AppData' / 'Local') / 'NewSEGS'
    if sys.platform == 'darwin':
        return home / 'Library' / 'Application Support' / 'NewSEGS'
    base = os.environ.get('XDG_DATA_HOME')
    return (Path(base) if base else home / '.local' / 'share') / 'newsegs'


HEARTBEAT_FILE = str(Path(tempfile.gettempdir()) / 'dispatcher_heartbeat.txt')

# NEWSEGS_ENV is read directly: dynaconf has already loaded .env into the
# environment, but has not yet resolved the current environment.
if os.environ.get('NEWSEGS_ENV', '').strip().lower() != 'production':
    _DATA_DIR = user_data_dir()
    DB_PATH = str(_DATA_DIR / 'db' / 'newsegs_db.db')
    RESULTS_STORE = str(_DATA_DIR / 'results_store')
    DB_BACKUP_PATH = str(_DATA_DIR / 'db_backups')
    ENV_CACHE_PATH = str(_DATA_DIR / 'env_cache')
else:
    # The environment cache holds no data that cannot be fetched again, so may fall back
    # to the system temporary directory; docker-compose.yml keeps it on a volume.
    ENV_CACHE_PATH = str(Path(tempfile.gettempdir()) / 'newsegs_env_cache')

BACKGROUND_CALLBACK_CACHE_PATH = str(Path(tempfile.gettempdir()) / 'newsegs_background_callbacks')
