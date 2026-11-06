"""
Tests of the app's cache of results (`CachedFromDatabaseResultProvider`), for results saved again at the same
revision of their parent (#177).

The optimisation's marginal plot is saved by a worker against the project's table config, for whichever variable was
last plotted, so a later plot of another variable is saved at the same revision. Two defects showed an earlier plot:

- the cache kept results by the revision, so the app kept the plot it first loaded. Results are now cached by their
  file, which each result saved has of its own;
- the plot was saved at the revision of the project in the worker's memory, which running the model across the margin
  increments, not the revision stored. The app looks the plot up by the stored revision, so it found an older plot.
  It's now saved at the stored revision.
"""
import json
from contextlib import contextmanager
from pathlib import Path
from typing import cast
from unittest import mock

from dash import html

from newsegsmodelapp.backend.db.db_component_provider import (
    CachedFromDatabaseNewsegsProjectProvider, FromDatabaseNewsegsComponentProvider,
)
from newsegsmodelapp.backend.db.db_result_provider import CachedFromDatabaseResultProvider, FromDatabaseResultProvider
from newsegsmodelapp.plugins.models.aaa_default.processes.output import aaa_default_tables
from newsegsmodelapp.registers import RunRequest, TableDrawRequest

from .base import InputChangeTestCase

PLOT = 'plot_marginal_optim'

class _ResultsTestCase(InputChangeTestCase):
    """A worker's results provider, which saves results, and the app's cached one, which reads them"""

    def setUp(self):
        super().setUp()
        from newsegsmodelapp.backend import db
        store = Path(self._db_dir.name) / 'results'
        # The worker saves the results, and the app reads them through its cache
        self.worker = FromDatabaseResultProvider(db.get_engine, store)
        self.app_results = CachedFromDatabaseResultProvider(db.get_engine, store)
        lproj = self.provider.get_lightweight_project(self.project_id)
        component_provider = cast(FromDatabaseNewsegsComponentProvider, self.provider._component_provider)
        self.table_config = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)

class TestStaleResult(_ResultsTestCase):
    """With no result at the revision asked for, the most recent earlier result is returned (#195)"""

    TABLE = 'table_finance_so_benefits_ann'

    def save(self, label: str, revision: int):
        self.worker.upsert_result(self.TABLE, self.table_config, html.Div(label), revision = revision)

    def shown(self) -> tuple[str, int]:
        res, rev = self.app_results.get_result(self.TABLE, self.table_config)
        return res.children, rev

    def test_most_recent_earlier_revision(self):
        r = self.table_config.revision
        self.save('two configurations', r - 3)
        self.save('three configurations, first', r - 1)
        self.save('three configurations', r - 1)
        # Saved at a revision of the project in a worker's memory, above the stored one (as in #177)
        self.save('ahead', r + 2)
        self.assertEqual(self.shown(), ('three configurations', r - 1))

        # The result at the revision asked for, once there is one
        self.save('current', r)
        self.assertEqual(self.shown(), ('current', r))

    def test_only_later_revisions(self):
        # As before: the latest result of the earliest revision
        r = self.table_config.revision
        self.save('ahead by 2', r + 2)
        self.save('ahead by 1', r + 1)
        self.assertEqual(self.shown(), ('ahead by 1', r + 1))

    def test_revision_given(self):
        r = self.table_config.revision
        self.save('earlier', r - 2)
        self.save('later', r)
        res, rev = self.app_results.get_result(self.TABLE, self.table_config, revision = r - 1)
        self.assertEqual((res.children, rev), ('earlier', r - 2))

class TestResultSavedAgainAtTheSameRevision(_ResultsTestCase):

    def shown(self, allow_stale: bool = True) -> str:
        res, rev = self.app_results.get_result(PLOT, self.table_config, allow_stale)
        self.assertEqual(rev, self.table_config.revision)
        return res.children

    def test_latest_result_is_shown(self):
        self.worker.upsert_result(PLOT, self.table_config, html.Div('wind_capacity'))
        self.assertEqual(self.shown(), 'wind_capacity')

        # Saved again for another variable, at the same revision of the table config
        self.worker.upsert_result(PLOT, self.table_config, html.Div('storage_capacity'))
        self.assertEqual(self.shown(), 'storage_capacity')
        self.assertEqual(self.shown(allow_stale = False), 'storage_capacity')

        self.worker.upsert_result(PLOT, self.table_config, html.Div('wind_capacity'))
        self.assertEqual(self.shown(), 'wind_capacity')

    def test_result_is_loaded_once(self):
        self.worker.upsert_result(PLOT, self.table_config, html.Div('wind_capacity'))
        with mock.patch.object(self.app_results, '_load_result_file', wraps = self.app_results._load_result_file) as load:
            for _ in range(3):
                self.assertEqual(self.shown(), 'wind_capacity')
            self.assertEqual(load.call_count, 1)

            # A new result is loaded, once
            self.worker.upsert_result(PLOT, self.table_config, html.Div('storage_capacity'))
            for _ in range(2):
                self.assertEqual(self.shown(), 'storage_capacity')
            self.assertEqual(load.call_count, 2)

    def test_no_result(self):
        self.assertEqual(self.app_results.get_result(PLOT, self.table_config), (None, None))

    def test_request_result_saved_by_worker_is_found_after_a_miss(self):
        result_type = 'request_result_test'
        request = RunRequest(request_id = 83)
        self.assertEqual(
            self.app_results.get_request_result(result_type, request.request_id, self.table_config),
            (None, None),
        )

        self.worker.upsert_result(result_type, self.table_config, html.Div('result'), request = request)

        result, revision = self.app_results.get_request_result(
            result_type, request.request_id, self.table_config
        )
        self.assertEqual(result.children, 'result')
        self.assertEqual(revision, self.table_config.revision)

    def test_request_result_rows_are_read_before_connection_returns_to_pool(self):
        transaction_open = False
        expected_revision = self.table_config.revision

        class Result:
            def mappings(self):
                if not transaction_open:
                    raise AssertionError('Result rows were accessed after the read transaction ended')
                return self

            def all(self):
                if not transaction_open:
                    raise AssertionError('Result rows were accessed after the read transaction ended')
                return [{
                    'result_file': 'result-file',
                    'component_config_revision': expected_revision,
                }]

        class Connection:
            def execute(self, _stmt):
                return Result()

        @contextmanager
        def read_transaction(_engine):
            nonlocal transaction_open
            transaction_open = True
            try:
                yield Connection()
            finally:
                transaction_open = False

        with (
            mock.patch('newsegsmodelapp.backend.db.db_result_provider.read_transaction', read_transaction),
            mock.patch(
                'newsegsmodelapp.backend.db.db_result_provider.load_result',
                return_value = html.Div('result'),
            ),
        ):
            result, revision = self.app_results.get_request_result('request_result_test', 83, self.table_config)

        self.assertEqual(result.children, 'result')
        self.assertEqual(revision, self.table_config.revision)

class TestMarginalPlotDraw(_ResultsTestCase):
    """The draw procedure of the marginal plot, run as a worker runs it, and read back as the app reads it."""

    def draw(self, varid: str):
        request = TableDrawRequest(
            request_type = 'table_optim_metamodel', project_id = self.project_id, model_type = 'sprake',
            payload = json.dumps({'metamodel_id': self.metamodel_ids[0], 'varid': varid}),
        )
        variable = self.worker_projects.get_project(self.project_id).metamodels[0].variables[varid]
        status = aaa_default_tables._trigger_plot_marginal_optim(
            request, self.worker_projects, self.worker, 1, lambda *args: None, lambda: False,
        )
        self.assertEqual(status, 'ok')
        return variable.name

    def setUp(self):
        super().setUp()
        from newsegsmodelapp.backend import db
        # The worker holds the project in its cache, as after an earlier run
        self.worker_projects = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)
        self.worker_projects.get_project(self.project_id)

    def shown_label(self) -> str:
        fig, rev = self.app_results.get_result(PLOT, self.table_config)
        self.assertEqual(rev, self.table_config.revision)
        return fig.layout.xaxis.title.text

    def test_each_plot_is_shown(self):
        for varid in ('gen_input.wind_capacity.0', 'gen_input.pv_capacity.0', 'gen_input.wind_capacity.0'):
            with self.subTest(varid = varid):
                label = self.draw(varid)
                self.assertEqual(self.shown_label(), label)
        # The stored revision is unchanged by drawing
        self.assertEqual(self.reader.get_lightweight_project(self.project_id).table_config.revision, self.table_config.revision)
