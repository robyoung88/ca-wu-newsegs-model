"""Provides functions for scheduling backups and pruning whilst app is running."""
import logging
logger = logging.getLogger(__name__)
import time

from pathlib import Path
import schedule

from newsegsmodelapp.backend.pruning import prune_old_jobs
from config import settings
DB_PATH = Path(str(settings['DB_PATH']))
DB_BACKUP_PATH = Path(str(settings['DB_BACKUP_PATH']))
RESULTS_STORE = Path(str(settings['RESULTS_STORE']))
from newsegsmodelapp.backend.constants import BACKUP_RETENTION_DAYS

from newsegsmodelapp.backend.backup import backup_now, cleanup_old_backups

def run_backup():
    """Perform a database backup."""
    backup_now(DB_PATH, DB_BACKUP_PATH)

def run_pruning():
    """Perform pruning tasks"""
    cleanup_old_backups(DB_BACKUP_PATH, BACKUP_RETENTION_DAYS)

    prune_old_jobs(DB_PATH, RESULTS_STORE)

    # For a practical app, we would also have some pruning of the 
    # configurations here.

# Scheduling
schedule.every().day.at("02:00").do(run_backup)
schedule.every().sunday.at("03:00").do(run_pruning)

if __name__ == '__main__':
    logger.info('Maintenance scheduler online.')
    while True:
        schedule.run_pending()
        time.sleep(300) # Wake every 5 minutes to check the schedule.

# TODO: Once under a docker container, have the container launch and monitor this process
