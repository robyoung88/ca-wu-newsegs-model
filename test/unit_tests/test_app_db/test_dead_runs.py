"""
Unit tests of the dispatcher's cleanup of dead runs: a run calculating whose progress has not been updated for
`DEAD_CALCULATION_INTERVAL_SECONDS` is marked failed, and an update of its progress, such as a wait for environmental
data reported again (#183), keeps it alive.
"""
import os
from pathlib import Path
import tempfile
import unittest

import sqlalchemy as sa

from newsegsmodelapp.backend import dispatcher
from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db_jobs import update_calculation_progress

from config import settings


class TestDeadRuns(unittest.TestCase):

    def setUp(self):
        self.db_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.db_dir.name) / 'tempdb.db'
        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        self.addCleanup(self._cleanup)
        self.engine = db.get_engine(writer = True)
        tbls.create_all_tables(self.engine)

    def _cleanup(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()
        self.db_dir.cleanup()

    def _run_last_updated(self, minutes_ago: int) -> int:
        # As the cleanup compares with SQLite's time
        with self.engine.begin() as conn:
            run_id = conn.execute(sa.insert(tbls.runs).values(status = 'CALCULATING')).inserted_primary_key[0] # pyright: ignore[reportOptionalSubscript]
            conn.execute(
                sa.update(tbls.runs)
                .where(tbls.runs.c.run_id == run_id)
                .values(modified_at = sa.text(f"datetime('now', '-{minutes_ago} minutes')"))
            )
        return run_id

    def _status(self, run_id: int) -> str:
        with self.engine.connect() as conn:
            return conn.execute(sa.select(tbls.runs.c.status).where(tbls.runs.c.run_id == run_id)).scalar_one()

    def test_run_without_progress_marked_failed(self):
        dead, alive = self._run_last_updated(6), self._run_last_updated(1)
        self.assertEqual(dispatcher._cleanup_dead_jobs(self.engine, dispatcher.DEAD_CALCULATION_INTERVAL_SECONDS), 1)
        self.assertEqual((self._status(dead), self._status(alive)), ('FAILED', 'CALCULATING'))

    def test_progress_keeps_a_run_alive(self):
        run_id = self._run_last_updated(6)
        # The same progress, as when a wait is reported again
        update_calculation_progress(self.engine, run_id, 1.5, 22, 'Point 2 of 21: Awaiting environmental data: wind speeds')
        self.assertEqual(dispatcher._cleanup_dead_jobs(self.engine, dispatcher.DEAD_CALCULATION_INTERVAL_SECONDS), 0)
        self.assertEqual(self._status(run_id), 'CALCULATING')


if __name__ == '__main__':
    unittest.main()
