"""Functions for database creation and management."""

import random
import time
from typing import Any, Literal, Optional
import logging
import os
import sqlite3
import warnings

from alembic.config import Config as AlembicConfig
from pathlib import Path
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

_engine: sa.Engine|None = None
_connected_db_path: str | None = None
def get_engine(db_path: str | Path | None = None):
    """Get the sqlalchemy engine for the database."""
    global _engine
    global _connected_db_path

    db_path = str(settings['DB_PATH']) if db_path is None else db_path

    if _engine is None or (_connected_db_path is not None and _connected_db_path != db_path):
        engine_url = f'sqlite+pysqlite:///{db_path}'
        print(f'Creating engine: {engine_url}')
        _engine = sa.create_engine(
            engine_url,
            echo = False,
            connect_args = {"timeout": 30.0},
            pool_size = 20,
            max_overflow = 30,
            pool_timeout = 30,
            pool_use_lifo = True,
        )
        _connected_db_path = str(db_path)

        # Enable WAL mode for concurrent multi-process access across containers
        @event.listens_for(_engine, 'connect')
        def set_sqlite_pragma(dbapi_connection, connection_record):
            # 1. Save the previous isolation level
            old_isolation = dbapi_connection.isolation_level

            # 2. Set isolation_level to None (autocommit) to execute PRAGMAs outside a transaction
            dbapi_connection.isolation_level = None

            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL;")
            cursor.execute("PRAGMA busy_timeout=30000;")
            cursor.execute("PRAGMA synchronous = NORMAL;")
            cursor.close()

            # 4. Restore the original isolation level for SQLAlchemy transaction management
            dbapi_connection.isolation_level = old_isolation

    checkout_times = {}

    @sa.event.listens_for(_engine, "checkout")
    def on_checkout(dbapi_connection, connection_record, connection_proxy):
        checkout_times[id(dbapi_connection)] = time.time()

    @sa.event.listens_for(_engine, "checkin")
    def on_checkin(dbapi_connection, connection_record):
        start_time = checkout_times.pop(id(dbapi_connection), None)
        if start_time:
            duration = time.time() - start_time
            if duration > 3.0:  # Threshold in seconds
                print(f"WARNING: Connection held for {duration:.2f} seconds")

    return _engine



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
    print(f"Restoring database from latest backup: {latest_backup.name}")

    # Ensure target directory exists
    db_path.parent.mkdir(parents = True, exist_ok = True)

    # Perform safe restore using SQLite backup API
    with sqlite3.connect(latest_backup) as source:
        with sqlite3.connect(db_path) as dest:
            source.backup(dest)

    print('Database restoration complete.')
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
        print(f'Unable to create application database: {e}')
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
    db_file_status = retrieve_db_file(db_path, recovery_path)
    match db_file_status:
        case 'missing':
            db_exists = create_db(db_path)
            if not db_exists:
                raise FileNotFoundError('Unable to find or create application database.')
        case _:
            run_migrations()

def write_with_retries(
    engine: sa.Engine, 
    stmt,
    parameters: Optional[Any] = None,
    n_retries: int = 5, 
    base_sleep: float = 0.05, 
    max_sleep: float = 2.0
):
    """Execute stmt with engine, retrying on lock/operational errors 
    using exponential backoff and randomized jitter.
    """
    attempt = 0
    while True:
        try:
            with engine.begin() as conn:
                if parameters is None:
                    conn.execute(stmt)
                else:
                    conn.execute(stmt, parameters)
            logger.info("Successfully completed database write.")
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
            
            warnings.warn(
                f"Encountered lock/operational error (attempt {attempt}/{n_retries if n_retries >= 0 else 'inf'}): {e}. "
                f"Retrying in {sleep_time:.2f}s..."
            )
            time.sleep(sleep_time)
