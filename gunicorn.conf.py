"""Gunicorn configuration for serving the Dash app in production.

Run from the repository root with `src` on PYTHONPATH:

    gunicorn --config gunicorn.conf.py app:server

Settings can be overridden with environment variables (below) or with
GUNICORN_CMD_ARGS, e.g. GUNICORN_CMD_ARGS="--log-level debug".
"""
import os

bind = os.environ.get('GUNICORN_BIND', '0.0.0.0:8050')

# One worker process by default: the app initialises the SQLite database on import
# and keeps per-process caches of projects and results, so concurrency comes from
# threads rather than from extra processes.
workers = int(os.environ.get('GUNICORN_WORKERS', '1'))
worker_class = 'gthread'
threads = int(os.environ.get('GUNICORN_THREADS', '8'))

# Building the app (imports, plugins, validation layout) takes a while, and some
# callbacks read large results; do not let gunicorn kill slow requests too eagerly.
timeout = int(os.environ.get('GUNICORN_TIMEOUT', '120'))
graceful_timeout = 30
keepalive = 5

# Log to stdout/stderr so that `docker compose logs` picks it up
accesslog = '-'
errorlog = '-'
loglevel = os.environ.get('GUNICORN_LOG_LEVEL', 'info')

# Never auto-reload in production
reload = False
