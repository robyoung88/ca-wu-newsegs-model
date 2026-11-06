"""
Tests of the times of runs, recorded and compared in UTC whatever the host's timezone (#190).

The dispatcher marks as failed a run that hasn't been updated for `DEAD_CALCULATION_INTERVAL_SECONDS`. It compared
`runs.modified_at`, written in local time, with SQLite's `'now'`, in UTC. With the host ahead of UTC, as under BST, a
stuck run was marked dead an hour late; behind UTC, a working run was marked dead as soon as it started.
"""
import datetime
import os
from pathlib import Path
import tempfile
import time
import unittest

import sqlalchemy as sa

from newsegsmodelapp.backend import dispatcher, pruning
from newsegsmodelapp.backend.db import db_tables as tbls

DEAD_INTERVAL_S = 300

def utc_now() -> datetime.datetime:
    """The time in UTC, without a timezone, as SQLite records it."""
    return datetime.datetime.now(datetime.timezone.utc).replace(tzinfo = None)

class _InTimezone(unittest.TestCase):
    """Runs each test with the host's local timezone set to `timezone`."""
    timezone: str = 'UTC'

    def setUp(self):
        self._old_tz = os.environ.get('TZ')
        os.environ['TZ'] = self.timezone
        time.tzset()
        self.addCleanup(self._restore_tz)

        self._dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.addCleanup(self._dir.cleanup)
        self.engine = sa.create_engine(f'sqlite:///{Path(self._dir.name) / "runs.db"}')
        self.addCleanup(self.engine.dispose)
        tbls.create_all_tables(self.engine)

    def _restore_tz(self):
        if self._old_tz is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = self._old_tz
        time.tzset()

    def add_run(self, status: str = 'CALCULATING', **values) -> int:
        """A run written as the app writes it: `modified_at` takes its default, unless given."""
        with self.engine.begin() as conn:
            return conn.execute(tbls.runs.insert().values(status = status, **values)).inserted_primary_key[0]

    def status(self, run_id: int) -> str:
        with self.engine.connect() as conn:
            return conn.execute(sa.select(tbls.runs.c.status).where(tbls.runs.c.run_id == run_id)).scalar_one()

class _CleanupTests(_InTimezone):

    def test_local_time_differs_from_utc(self):
        # Check the timezone is in effect, so that the tests below test it
        offset = datetime.datetime.now() - utc_now()
        self.assertAlmostEqual(offset.total_seconds() / 3600, self.expected_offset_h, places = 1)

    def test_working_run_is_kept(self):
        run_id = self.add_run()
        self.assertEqual(dispatcher._cleanup_dead_jobs(self.engine, DEAD_INTERVAL_S), 0)
        self.assertEqual(self.status(run_id), 'CALCULATING')

    def test_stuck_run_is_marked_dead(self):
        stuck = self.add_run(modified_at = utc_now() - datetime.timedelta(seconds = DEAD_INTERVAL_S + 60))
        working = self.add_run(modified_at = utc_now() - datetime.timedelta(seconds = DEAD_INTERVAL_S - 60))
        self.assertEqual(dispatcher._cleanup_dead_jobs(self.engine, DEAD_INTERVAL_S), 1)
        self.assertEqual(self.status(stuck), 'FAILED')
        self.assertEqual(self.status(working), 'CALCULATING')

    def test_runs_not_calculating_are_left(self):
        run_id = self.add_run(status = 'SUCCESS', modified_at = utc_now() - datetime.timedelta(hours = 2))
        self.assertEqual(dispatcher._cleanup_dead_jobs(self.engine, DEAD_INTERVAL_S), 0)
        self.assertEqual(self.status(run_id), 'SUCCESS')

    def test_modified_at_and_created_at_agree(self):
        # created_at is filled in by SQLite (UTC), modified_at by the app: both must be in UTC
        run_id = self.add_run()
        with self.engine.connect() as conn:
            created, modified = conn.execute(
                sa.select(tbls.runs.c.created_at, tbls.runs.c.modified_at).where(tbls.runs.c.run_id == run_id)
            ).one()
        self.assertLess(abs((modified - created).total_seconds()), 5)

    def test_pruning_cutoff_is_in_utc(self):
        expected = utc_now() - datetime.timedelta(days = 1)
        self.assertLess(abs((pruning._cutoff(1) - expected).total_seconds()), 5)

class TestCleanupAheadOfUtc(_CleanupTests):
    """As under BST: local time an hour ahead of UTC"""
    timezone = 'Etc/GMT-1'
    expected_offset_h = 1

class TestCleanupBehindUtc(_CleanupTests):
    """Local time five hours behind UTC"""
    timezone = 'Etc/GMT+5'
    expected_offset_h = -5

class TestCleanupInUtc(_CleanupTests):
    timezone = 'UTC'
    expected_offset_h = 0

del _CleanupTests

if __name__ == '__main__':
    unittest.main()
