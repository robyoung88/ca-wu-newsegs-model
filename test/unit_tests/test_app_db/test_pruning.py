"""Unit tests for newsegsmodelapp/backend/pruning"""
import os
from pathlib import Path
import tempfile
import time
import unittest

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from config import settings
from newsegsmodelapp.backend.db import db_tables as tbls


class TestPruning(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.db_path = root / 'tempdb.db'
        self.store = root / 'results_store'
        self.store.mkdir()

        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        self.engine = db.get_engine(writer = True, db_path = self.db_path)
        tbls.create_all_tables(self.engine)

        with self.engine.begin() as conn:
            conn.execute(tbls.component_configs.insert(), [{'id': 'cmp-a'}, {'id': 'cmp-b'}])
            conn.execute(tbls.projects.insert().values(id = 'prj-1', model_type = 'x', model_version = '1'))

    def tearDown(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()
        self.temp_dir.cleanup()

    def _file(self, name: str, age: float = 10 * 24 * 3600) -> str:
        path = self.store / name
        path.write_text('x')
        t = time.time() - age
        os.utime(path, (t, t))
        return str(path)

    def _result(self, result_id: int, cmp: str, rtype: str, file: str, **kw):
        with self.engine.begin() as conn:
            conn.execute(tbls.results.insert().values(
                result_id = result_id, component_config_id = cmp, result_type = rtype, result_file = file, **kw
            ))

    def _ids(self) -> set[int]:
        with self.engine.connect() as conn:
            return set(conn.execute(sa.select(tbls.results.c.result_id)).scalars())

    def _prune(self):
        from newsegsmodelapp.backend.pruning import prune_old_results
        return prune_old_results(self.store, self.engine)

    def test_superseded_rows_and_files_pruned(self):
        old = self._file('res-old.json')
        new = self._file('res-new.json')
        other = self._file('res-other.json')
        self._result(1, 'cmp-a', 'grid', old)
        self._result(2, 'cmp-a', 'grid', new)
        self._result(3, 'cmp-a', 'generation', other) # Different type: latest of its own

        report = self._prune()

        self.assertEqual(self._ids(), {2, 3})
        self.assertEqual(report.deleted_rows, 1)
        self.assertFalse(Path(old).exists())
        self.assertTrue(Path(new).exists())
        self.assertTrue(Path(other).exists())

    def test_shared_file_kept(self):
        """duplicate_result makes rows share a file; pruning the old row must not delete it."""
        shared = self._file('res-shared.json')
        self._result(1, 'cmp-a', 'grid', shared)
        self._result(2, 'cmp-a', 'grid', shared)

        self._prune()

        self.assertEqual(self._ids(), {2})
        self.assertTrue(Path(shared).exists())

    def test_missing_config_pruned(self):
        f = self._file('res-gone.json')
        self._result(1, 'cmp-missing', 'grid', f)

        self._prune()

        self.assertEqual(self._ids(), set())
        self.assertFalse(Path(f).exists())

    def test_protected_rows_kept(self):
        self._result(1, 'cmp-a', 'grid', self._file('res-1.json'), retain = True)
        self._result(2, 'cmp-a', 'grid', self._file('res-2.json'), request_id = 7)
        self._result(3, 'cmp-a', 'grid', self._file('res-3.json'))
        self._result(4, 'cmp-a', 'grid', self._file('res-4.json'))
        self._result(5, 'cmp-a', 'grid', self._file('res-5.json'))
        with self.engine.begin() as conn:
            conn.execute(tbls.requests.insert().values(
                request_id = 7, project_id = 'prj-1', status = 'DISPATCHED'
            ))
            conn.execute(
                tbls.component_configs.update()
                .where(tbls.component_configs.c.id == 'cmp-a')
                .values(last_result_id = 3)
            )

        self._prune()

        self.assertEqual(self._ids(), {1, 2, 3, 5})

    def test_snapshot_file_kept(self):
        snap = self._file('res-snap.json')
        self._result(1, 'cmp-a', 'grid', snap)
        self._result(2, 'cmp-a', 'grid', self._file('res-latest.json'))
        with self.engine.begin() as conn:
            conn.execute(tbls.snapshots.insert().values(snapshot_id = 1, project_id = 'prj-1', label = 's'))
            conn.execute(tbls.snapshot_component_configs.insert().values(snapshot_id = 1, id = 'cmp-a'))
            conn.execute(tbls.snapshot_results.insert().values(
                snapshot_id = 1, result_id = 1, component_config_id = 'cmp-a', result_type = 'grid', result_file = snap
            ))

        self._prune()

        self.assertEqual(self._ids(), {2})
        self.assertTrue(Path(snap).exists())

    def test_orphans(self):
        old_orphan = self._file('res-orphan-old.json')
        new_orphan = self._file('res-orphan-new.json', age = 60)
        unrelated = self._file('notes.txt')
        kept = self._file('res-kept.json')
        self._result(1, 'cmp-a', 'grid', kept)

        report = self._prune()

        self.assertFalse(Path(old_orphan).exists())
        self.assertTrue(Path(new_orphan).exists())
        self.assertTrue(Path(unrelated).exists())
        self.assertTrue(Path(kept).exists())
        self.assertEqual(report.deleted_orphans, [Path(old_orphan)])

    def test_compiles_for_postgres(self):
        from newsegsmodelapp.backend.pruning import _prunable_results_stmt
        sql = str(_prunable_results_stmt().compile(dialect = postgresql.dialect()))
        self.assertIn('EXISTS', sql)


if __name__ == '__main__':
    unittest.main()
