"""
Tests of the app's cache of results (`CachedFromDatabaseResultProvider`), for results saved again at the same
revision of their parent (#177).

The optimisation's marginal plot is saved by a worker against the project's table config, at its current revision,
for whichever variable was last plotted. The cache kept results by that revision, so the app kept showing the plot it
had first loaded: after plotting the wind capacity and then the storage capacity, the storage capacity's plot didn't
show. Results are now cached by their file, which each result saved has of its own.
"""
from pathlib import Path
from typing import cast
from unittest import mock

from dash import html

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsComponentProvider
from newsegsmodelapp.backend.db.db_result_provider import CachedFromDatabaseResultProvider, FromDatabaseResultProvider

from .base import InputChangeTestCase

PLOT = 'plot_marginal_optim'

class TestResultSavedAgainAtTheSameRevision(InputChangeTestCase):

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
