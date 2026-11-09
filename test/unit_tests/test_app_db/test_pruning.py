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


class _PruningBase(unittest.TestCase):
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


class TestPruneResults(_PruningBase):

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
        self._result(2, 'cmp-a', 'grid', self._file('res-a.json'))

        self._prune()

        self.assertEqual(self._ids(), {2})
        self.assertFalse(Path(f).exists())

    def test_largest_id_kept(self):
        """SQLite reuses the largest rowid if it is deleted."""
        self._result(1, 'cmp-missing', 'grid', self._file('res-gone.json'))

        self._prune()

        self.assertEqual(self._ids(), {1})

    def test_protected_rows_kept(self):
        self._result(1, 'cmp-a', 'grid', self._file('res-1.json'), retain = True)
        self._result(2, 'cmp-a', 'grid', self._file('res-2.json'), request_id = 7)
        self._result(3, 'cmp-a', 'grid', self._file('res-3.json'))
        self._result(4, 'cmp-a', 'grid', self._file('res-4.json'))
        self._result(5, 'cmp-a', 'grid', self._file('res-5.json'))
        with self.engine.begin() as conn:
            conn.execute(tbls.requests.insert().values(
                request_id = 7, project_id = 'prj-1', status = 'PROCESSING'
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
        from newsegsmodelapp.backend import pruning
        cutoff = pruning._cutoff(7)
        for stmt in (
            pruning._prunable_results_stmt(),
            pruning._prunable_requests_stmt(cutoff),
            pruning._prunable_runs_stmt(cutoff),
        ):
            self.assertIn('SELECT', str(stmt.compile(dialect = postgresql.dialect())))


class TestPruneConfigurations(_PruningBase):
    def _rows(self, table: sa.Table) -> set:
        with self.engine.connect() as conn:
            return set(conn.execute(sa.select(table.c[table.primary_key.columns.keys()[0]])).scalars())

    def setUp(self):
        super().setUp()
        t = tbls
        with self.engine.begin() as conn:
            conn.execute(t.component_configs.insert(), [{'id': x} for x in (
                'cmp-grid', 'cmp-tbl', 'cmp-ptbl', 'cmp-orphan-grid', 'cmp-loose', 'cmp-kept'
            )])
            conn.execute(t.component_configs.update().where(t.component_configs.c.id == 'cmp-kept').values(retain = True))
            conn.execute(t.em_configs.insert(), [
                {'id': 'm-live', 'grid_config_id': 'cmp-grid'},
                {'id': 'm-orphan', 'grid_config_id': 'cmp-orphan-grid'},
            ])
            conn.execute(t.fm_configs.insert(), [{'id': 'f-live'}, {'id': 'f-orphan'}])
            conn.execute(t.metamodels.insert(), [
                {'id': 'metam-live', 'em_config_id': 'm-live', 'fm_config_id': 'f-live', 'table_config_id': 'cmp-tbl'},
                {'id': 'metam-orphan', 'em_config_id': 'm-orphan', 'fm_config_id': 'f-orphan', 'table_config_id': None},
            ])
            conn.execute(t.projects.update().where(t.projects.c.id == 'prj-1').values(table_config_id = 'cmp-ptbl'))
            conn.execute(t.project_metamodels.insert().values(project_id = 'prj-1', metamodel_id = 'metam-live'))
            conn.execute(t.variable_configs.insert(), [{'id': x} for x in ('v-proj', 'v-mm', 'v-orphan-mm', 'v-loose')])
            conn.execute(t.project_variables.insert().values(project_id = 'prj-1', variable_config_id = 'v-proj'))
            conn.execute(t.metamodel_variables.insert(), [
                {'metamodel_id': 'metam-live', 'variable_config_id': 'v-mm'},
                {'metamodel_id': 'metam-orphan', 'variable_config_id': 'v-orphan-mm'},
            ])
            conn.execute(t.process_staleness.insert(), [
                {'metamodel_id': 'metam-live', 'process': 'dsa'},
                {'metamodel_id': 'metam-orphan', 'process': 'dsa'},
            ])

    def test_orphans_pruned_through_the_tree(self):
        from newsegsmodelapp.backend.pruning import prune_orphan_configurations
        self._result(1, 'cmp-orphan-grid', 'grid', self._file('res-1.json'))
        self._result(2, 'cmp-grid', 'grid', self._file('res-2.json'))

        prune_orphan_configurations(self.engine)

        self.assertEqual(self._rows(tbls.metamodels), {'metam-live'})
        self.assertEqual(self._rows(tbls.em_configs), {'m-live'})
        self.assertEqual(self._rows(tbls.fm_configs), {'f-live'})
        # cmp-a and cmp-b come from the base setUp and are unreferenced
        self.assertEqual(self._rows(tbls.component_configs), {'cmp-grid', 'cmp-tbl', 'cmp-ptbl', 'cmp-kept'})
        self.assertEqual(self._rows(tbls.variable_configs), {'v-proj', 'v-mm'})
        self.assertEqual(self._rows(tbls.process_staleness), {'metam-live'})
        self.assertEqual(self._ids(), {2})

    def test_skipped_while_request_active(self):
        from newsegsmodelapp.backend.pruning import prune_orphan_configurations
        with self.engine.begin() as conn:
            conn.execute(tbls.requests.insert().values(request_id = 1, project_id = 'prj-1', status = 'PROCESSING'))

        self.assertEqual(prune_orphan_configurations(self.engine), {})
        self.assertIn('metam-orphan', self._rows(tbls.metamodels))


class TestPruneRequests(_PruningBase):
    OLD = 30
    NEW = 1

    def _request(self, request_id: int, status: str, trigger: int = -1, project: str = 'prj-1',
                 run_age: float | None = OLD, run_status: str = 'COMPLETED', run_id: int | None = None):
        import datetime
        run_id = request_id * 10 if run_id is None else run_id
        with self.engine.begin() as conn:
            conn.execute(tbls.requests.insert().values(
                request_id = request_id, project_id = project, status = status,
                trigger_request_id = trigger, run_id = run_id if run_age is not None else None,
            ))
            if run_age is not None:
                t = tbls.utc_now() - datetime.timedelta(days = run_age)
                conn.execute(tbls.runs.insert().values(
                    run_id = run_id, request_id = request_id, status = run_status, created_at = t, modified_at = t
                ))

    def _requests(self) -> set[int]:
        with self.engine.connect() as conn:
            return set(conn.execute(sa.select(tbls.requests.c.request_id)).scalars())

    def _runs(self) -> set[int]:
        with self.engine.connect() as conn:
            return set(conn.execute(sa.select(tbls.runs.c.run_id)).scalars())

    def test_requests(self):
        from newsegsmodelapp.backend.pruning import prune_old_requests
        with self.engine.begin() as conn:
            conn.execute(tbls.projects.insert().values(id = 'prj-gone', model_type = 'x', model_version = '1'))
        self._request(1, 'FAILED')                         # pruned
        self._request(2, 'CANCELLED', run_age = None)       # pruned: no run, but later requests are old
        self._request(3, 'FULFILLED')                       # kept: results name it
        self._request(4, 'FULFILLED', trigger = 3)          # kept: chain root 3 has results
        self._request(5, 'FULFILLED')                       # pruned: no results
        self._request(6, 'FAILED', run_age = self.NEW)      # kept: too recent
        self._request(7, 'FULFILLED')                       # kept: chain has an active request
        self._request(8, 'PROCESSING', trigger = 7)         # kept: active
        self._request(9, 'FAILED')                          # kept: largest id
        self._result(1, 'cmp-a', 'grid', self._file('res-1.json'), request_id = 3)

        n = prune_old_requests(self.engine)

        self.assertEqual(self._requests(), {3, 4, 6, 7, 8, 9})
        self.assertEqual(n, 3)
        self.assertNotIn(10, self._runs())

    def test_runs(self):
        from newsegsmodelapp.backend.pruning import prune_old_runs
        import datetime
        self._request(1, 'FULFILLED', run_id = 12)
        self._request(2, 'AWAITING DISPATCH', run_age = None)
        t = tbls.utc_now() - datetime.timedelta(days = self.OLD)
        with self.engine.begin() as conn:
            conn.execute(tbls.runs.insert(), [
                {'run_id': 11, 'request_id': 1, 'status': 'FAILED', 'created_at': t, 'modified_at': t},  # superseded: pruned
                {'run_id': 21, 'request_id': 2, 'status': 'FAILED', 'created_at': t, 'modified_at': t},  # failed retry: pruned
                {'run_id': 22, 'request_id': 2, 'status': 'CALCULATING', 'created_at': t, 'modified_at': t},  # reclaimable: kept
                {'run_id': 31, 'request_id': 99, 'status': 'SUCCESS', 'created_at': t, 'modified_at': t},  # request gone: pruned
                {'run_id': 40, 'request_id': 99, 'status': 'SUCCESS', 'created_at': t, 'modified_at': t},  # largest id: kept
            ])

        prune_old_runs(self.engine)

        self.assertEqual(self._runs(), {12, 22, 40})


class TestPruneAll(_PruningBase):
    def test_runs(self):
        from newsegsmodelapp.backend.pruning import prune_all
        prune_all(self.store, self.engine)


if __name__ == '__main__':
    unittest.main()
