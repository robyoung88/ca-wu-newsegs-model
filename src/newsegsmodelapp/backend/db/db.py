"""Functions for database creation and management."""

import random
import time
from typing import Any, Literal, Optional
import logging
import os
import sqlite3
from contextlib import contextmanager
from collections.abc import Generator
import threading

from alembic.config import Config as AlembicConfig
from pathlib import Path
import fasteners
import sqlalchemy as sa
from sqlalchemy.exc import OperationalError, DBAPIError
from sqlalchemy import event

from config import settings

logger = logging.getLogger(__name__)

DB_PATH = str(settings['DB_PATH'])
DB_BACKUP_PATH = Path(str(settings['DB_BACKUP_PATH']))
if not DB_BACKUP_PATH.exists():
    DB_BACKUP_PATH.mkdir(parents=True, exist_ok=True)

RETRIEVAL_STATUS = Literal[
    'ok',
    'from_backup',
    'missing'
]

class DependentObjectsExistError(ValueError):
    """Raised when attempting to delete a component that still has dependent children."""
    pass

_engines: dict[tuple, sa.Engine] = {}

def _make_engine(db_path: str, *, writer: bool) -> sa.Engine:
    engine = sa.create_engine(
        f"sqlite+pysqlite:///{db_path}",
        connect_args={"timeout": 30.0},
        pool_size=1 if writer else 10,
        max_overflow=0 if writer else 10,
        pool_timeout=30,
    )

    @event.listens_for(engine, "connect")
    def on_connect(dbapi_conn, _):
        dbapi_conn.isolation_level = None          # we control BEGIN ourselves
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=30000")
        cur.execute("PRAGMA synchronous=NORMAL")
        if not writer:
            cur.execute("PRAGMA query_only=ON")    # readers can never write
        cur.close()

    @event.listens_for(engine, "begin")
    def on_begin(conn):
        conn.exec_driver_sql("BEGIN IMMEDIATE" if writer else "BEGIN")

    return engine

def get_engine(*, writer: bool = False, db_path: str | Path | None = None):
    """Get the sqlalchemy engine for the database."""
    db_path = str(db_path or settings['DB_PATH'])
    key = (os.getpid(), writer, db_path)           # fork-safe
    if key not in _engines:
        _engines[key] = _make_engine(db_path, writer=writer)
    return _engines[key]


def retrieve_latest_backup(
    db_path: str | Path = DB_PATH,
    backup_dir: str | Path = DB_BACKUP_PATH
) -> RETRIEVAL_STATUS:
    """Finds the most recent backup in directory and retrieves it."""
    if not isinstance(db_path, Path):
        db_path = Path(db_path)
    if not isinstance(backup_dir, Path):
        backup_dir = Path(backup_dir)

    if not backup_dir.exists():
        return 'missing'

    # Find all backup files and sort by modification time (newest last)
    backup_files = sorted(
        backup_dir.glob(f"{settings.get('DB_FILENAME_ROOT')}_*.db"),
        key = os.path.getmtime
    )

    if not backup_files:
        return 'missing'

    latest_backup = backup_files[-1]
    logger.warning('Restoring database from latest backup: %s', latest_backup.name)

    # Ensure target directory exists
    db_path.parent.mkdir(parents = True, exist_ok = True)

    # Perform safe restore using SQLite backup API
    with sqlite3.connect(latest_backup) as source:
        with sqlite3.connect(db_path) as dest:
            source.backup(dest)

    logger.warning('Database restoration complete.')
    return 'from_backup'

def retrieve_db_file(
    db_path: str | Path, 
    recovery_path: str | Path = DB_BACKUP_PATH
) -> RETRIEVAL_STATUS:
    """Check if file exists at db_path, and recover a backup if not."""
    if not isinstance(db_path, Path):
        db_path = Path(db_path)

    if not db_path.exists():
        backup_status = retrieve_latest_backup(db_path, recovery_path)
        return backup_status
    else:
        return 'ok'

def create_db(
    db_path: str
) -> bool:
    """Perform the basic database creation."""
    try:
        run_migrations()
    except sqlite3.Error as e:
        logger.exception('CRITICAL: Unable to create application database', exc_info = True)
        raise
    return True

def run_migrations():
    """Check database version and execute pending SQL migration scripts
    
    Args:
        from_none (bool) - Ignore version number and apply full migration path.
    """
    from alembic import command
    from newsegsmodelapp import APP_ROOT
    alembic_cfg = AlembicConfig(APP_ROOT.parent / 'alembic.ini')
    command.upgrade(alembic_cfg, 'head')

def init_db(db_path: str = DB_PATH, recovery_path: str | Path = DB_BACKUP_PATH):
    """Init db.

    TODO: Add a description.

    Args:
        db_path: TODO.
        recovery_path: TODO.
    """
    db_file_status = retrieve_db_file(db_path, recovery_path)
    match db_file_status:
        case 'missing':
            db_exists = create_db(db_path)
            if not db_exists:
                raise FileNotFoundError('Unable to find or create application database.')
        case _:
            run_migrations()

@contextmanager
def write_transaction(engine: Optional[sa.Engine] = None) -> Generator[sa.Connection, None, None]:
    """Run a SQLite write transaction while holding the cross-process lock."""
    engine = engine or get_engine(writer = True)
    with engine.begin() as conn:
        yield conn

@contextmanager
def read_transaction(engine: Optional[sa.Engine] = None) -> Generator[sa.Connection, None, None]:
    """Run a SQLite read transaction while holding the cross-process lock."""
    engine = engine or get_engine()
    with engine.connect() as conn:
        yield conn

def write_with_retries(
    engine: sa.Engine, 
    stmt,
    parameters: Optional[Any] = None,
    n_retries: int = 10,
    base_sleep: float = 0.05, 
    max_sleep: float = 4.0
):
    """Execute stmt with engine, retrying on lock/operational errors 
    using exponential backoff and randomized jitter.
    """
    attempt = 0
    while True:
        try:
            with write_transaction(engine) as conn:
                if parameters is None:
                    conn.execute(stmt)
                else:
                    conn.execute(stmt, parameters)
            logger.debug("Successfully completed database write.")
            return True
        except (OperationalError, DBAPIError) as e:
            # Check if it's actually a lock or timeout error
            err_msg = str(e).lower()
            is_lock = any(k in err_msg for k in ["locked", "timeout", "deadlock", "busy"])
            
            if not is_lock or (n_retries >= 0 and attempt >= n_retries):
                raise e
            
            attempt += 1
            # Exponential backoff with random jitter (prevents thundering herd)
            sleep_time = min(max_sleep, base_sleep * (2 ** attempt)) + random.uniform(0, 0.05)
            
            logger.warning(
                f"Encountered lock/operational error (attempt {attempt}/{n_retries if n_retries >= 0 else 'inf'}): {e}. "
                f"Retrying in {sleep_time:.2f}s... SQL: {stmt}"
            )
            time.sleep(sleep_time)
