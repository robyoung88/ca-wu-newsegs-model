# Install and run

## Getting Started

## Contributing

Pull requests go to the `development` branch, with a Conventional Commit title (`feat: ...`, `fix: ...`); releases are made by promoting `development` to `canary` (prereleases) and `canary` to `main` (releases). See `docs/development.md`.

## Supported platforms
This program has been tested on the following platforms:

- Python 3.13 running on Microsoft Windows 10
- Python 3.13 running on Ubuntu 2404 LTS

## Installing dependencies
In order to run this model, it is recommended that you set up a virtual execution environment. Using conda or miniconda, it is recommended you do so from the relevant `conda-lock.yml` file using the command:

```
conda env create -f conda-lock.yml
```

There are a small number of `pip` dependencies that must be installed after creating this environment, listed in `requirements-pip.txt` and `requirements-docs.txt`

```
pip install -r requirements-pip.txt -r requirements-docs.txt
```

## Environment variables

It is suggested that the following variables are set in a .env file:

- PYTHONPATH = ./src
- PVLIB_USE_NUMBA = "1"

### Selecting the environment

A single variable, `NEWSEGS_ENV`, selects the environment: `development` (the default when unset), `testing` or `production`. (`spraketest`, a variant of `testing` that reproduces the original Sprake model, is also accepted.)

It selects the matching section of `src/settings.toml` (it is dynaconf's environment switcher, replacing `ENV_FOR_DYNACONF`), and it controls behaviour outside dynaconf: the Dash debug tools are only enabled in `development`. Code can query it through `config.environment` (e.g. `environment.is_production()`).

The tests select `testing` themselves (see `test/__init__.py`), whatever `NEWSEGS_ENV` is set to, unless it is `spraketest`.

### Storage locations

`DB_PATH`, `RESULTS_STORE` and `DB_BACKUP_PATH` can be set in `src/.secrets.toml`, in `src/settings.toml`, or with `DYNACONF_DB_PATH` etc. When they are not set, and the environment is not `production`, they default to a per-user data directory (see `src/config/default_paths.py`):

| Platform | Directory |
|---|---|
| Windows | `%LOCALAPPDATA%\NewSEGS` |
| macOS | `~/Library/Application Support/NewSEGS` |
| Linux | `$XDG_DATA_HOME/newsegs`, normally `~/.local/share/newsegs` |

holding `db/newsegs_db.db`, `results_store/` and `db_backups/`. These are adequate for local use, but the backups sit on the same disk as the database. In `production` there are no defaults, and the three must be configured (`docker-compose.yml` does so).

## Running with Docker

The production stack is the default `docker-compose.yml`:

```
docker compose up --build --detach
```

This runs the Dash app under gunicorn (configured in `gunicorn.conf.py`) with `NEWSEGS_ENV=production`, using the code baked into the image. The dozzle log viewer and the sqlite-web database browser are not started.

For development, layer `docker-compose.dev.yml` on top. This sets `NEWSEGS_ENV=development`, mounts the working copy for live code changes, runs the Flask development server with debug tools, and adds dozzle (port 9090) and sqlite-web (port 9080):

```
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

Setting `COMPOSE_FILE=docker-compose.yml:docker-compose.dev.yml` in your local `.env` makes plain `docker compose up` use the development stack.

To debug the Dash app, add `docker-compose.debug.yml` as well (the VS Code task "Start Dash app in Docker for debugging" does this), then attach with the "Attach to Dash app in Docker" launch configuration.