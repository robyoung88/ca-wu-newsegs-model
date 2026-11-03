"""A scheduled backup service"""
import logging
logger = logging.getLogger(__name__)

import sqlite3
import time
import os
import re
from datetime import datetime

from pathlib import Path

from config import settings
DB_PATH = str(settings['DB_PATH'])
DB_BACKUP_PATH = str(settings['DB_BACKUP_PATH'])
from newsegsmodelapp.backend.constants import BACKUP_RETENTION_DAYS

def cleanup_old_backups(
    backup_path: str | Path = DB_BACKUP_PATH,
    retention_days: int = BACKUP_RETENTION_DAYS
):
    """Deletes any backup files older than the retention period"""
    now = time.time()
    cutoff_seconds = retention_days * 86400 # seconds per day

    if not isinstance(backup_path, Path):
        backup_path = Path(backup_path)

    if not backup_path.exists():
        return

    pattern = re.compile(re.escape(str(settings['DB_FILENAME_ROOT'])) + r'_.*\.db')
    for file in backup_path.iterdir():
        match = pattern.match(file.name)
        if match:
            if os.path.getmtime(file) < (now - cutoff_seconds):
                try:
                    os.remove(file)
                    logger.info('Pruned old backup: %s', file.name)
                except Exception as e:
                    logger.warning('Failed to delete old backup: %s', file.name, exc_info = True)

def backup_now(
    db_path: str | Path = DB_PATH,
    backup_path: str | Path = DB_BACKUP_PATH
):
    """Write the current app database to backup immediately"""
    if not isinstance(backup_path, Path):
        backup_path = Path(backup_path)
    
    backup_path.mkdir(parents = True, exist_ok = True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_fn = f'{settings['DB_FILENAME_ROOT']}_{timestamp}.db'
    backup_file_path = backup_path / backup_fn

    try:
        # Perform safe SQLite backup
        with sqlite3.connect(db_path) as source:
            with sqlite3.connect(backup_file_path) as dest:
                source.backup(dest)
        logger.info('Database backed up to: %s', backup_file_path)

    except Exception as e:
        logger.error('CRITICAL ERROR during database backup: ', exc_info = True)
