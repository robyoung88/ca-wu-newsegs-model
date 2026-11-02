"""Constants of the backend.

Attributes:
    BACKEND_DIR: The directory of the backend package.
    BACKUP_RETENTION_DAYS: Number of days for which backups are kept.
"""
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent

BACKUP_RETENTION_DAYS = 30
