"""Functions for database creation and management."""

from typing import Literal
import os
import sqlite3

from alembic import command
from alembic.config import Config as AlembicConfig
from pathlib import Path
import sqlalchemy
from sqlalchemy import event

from config import settings
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

_engine: sqlalchemy.Engine|None = None
_connected_db_path: str | None = None
def get_engine(db_path: str | Path = DB_PATH):
    """Get the sqlalchemy engine for the database."""
    global _engine
    global _connected_db_path
    if _engine is None or (_connected_db_path is not None and _connected_db_path is not db_path):
        _engine = sqlalchemy.create_engine(
            f'sqlite+pysqlite:///{db_path}',
            #connect_args = {'autocommit': False},
            echo = False
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
            cursor.execute("PRAGMA busy_timeout=5000;")
            cursor.close()

            # 4. Restore the original isolation level for SQLAlchemy transaction management
            dbapi_connection.isolation_level = old_isolation

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
    alembic_cfg = AlembicConfig('alembic.ini')
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
