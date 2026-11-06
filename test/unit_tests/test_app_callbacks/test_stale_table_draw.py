"""
Tests of a result table drawn stale, then saved at the current revision (#195), through the callback of the result
tables as Dash dispatches it.

A table draw that can't make its table yet (it ends `missing`) still sets its post-action trigger, so the page draws
the table before it exists, from an earlier revision. The callback recorded that draw as of the project's current
revision, so when the table was then saved at that revision, its trigger was skipped as already drawn, and the page
kept the stale table.
"""
from pathlib import Path
from typing import cast

from dash import html
import dash_daq as daq

from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsComponentProvider
from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.components.callbacks.result_container_callbacks import add_result_container_callbacks
from newsegsmodelapp.dash_extension import NewsegsDash

from .base import InputChangeTestCase
from .dash_dispatch import NOT_UPDATED, dispatch_callback, get_callback_spec

TOGGLE_ID = {'type': 'annual-horizon-toggle', 'page': 'site-config'}
KEY = 'table_net'
TABLE_ID = {'type': 'result-table', 'purpose': 'container', 'supersection': 'deterministic', 'section': 'tabledraw', 'key': KEY, 'subindex': 0}
POSTACTION_ID = {'type': 'postaction-trigger', 'purpose': 'trigger', 'supersection': 'global', 'section': 'tabledraw', 'key': KEY, 'subindex': 0}
RENDERED = ('data-rendered-project-id', 'data-rendered-project-table-revision', 'data-rendered-ann-hori-state', 'data-is-stale')

class TestStaleTableDraw(InputChangeTestCase):

    def setUp(self):
        super().setUp()
        from newsegsmodelapp.backend import db
        self.results = FromDatabaseResultProvider(db.get_engine, Path(self._db_dir.name) / 'results')
        self.app = NewsegsDash(
            __name__,
            project_provider = self.provider,
            results_provider = self.results,
            request_handler = None, # pyright: ignore[reportArgumentType]
            suppress_callback_exceptions = True,
        )
        self.app.layout = html.Div()
        add_result_container_callbacks(self.app)
        self.app.server.config['TESTING'] = True
        self.client = self.app.server.test_client()

        lproj = self.provider.get_lightweight_project(self.project_id)
        component_provider = cast(FromDatabaseNewsegsComponentProvider, self.provider._component_provider)
        self.table_config = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)
        self.revision = self.table_config.revision
        # What the page holds of the table: nothing drawn yet
        self.rendered = {x: None for x in RENDERED}
        self.n_triggers = 0

    def save(self, label: str, revision: int):
        self.results.upsert_result(KEY + '_ann', self.table_config, html.Div(label), revision = revision)

    def draw(self):
        """A post-action trigger of the table, as when a table draw completes; returns the table shown, if redrawn"""
        self.n_triggers += 1
        spec = get_callback_spec(self.client, 'result-table', 'children')
        response = dispatch_callback(
            self.client, spec, trigger = POSTACTION_ID, value = self.n_triggers,
            components = [
                daq.ToggleSwitch(id = TOGGLE_ID, value = False),
                html.Div(id = TABLE_ID, **self.rendered),
                html.Div(id = POSTACTION_ID),
            ],
            stores = {'active-project-id': self.project_id, 'app-state': '{"model_type": "sprake"}'},
        )
        children = response.get(TABLE_ID, 'children')
        for x in RENDERED:
            value = response.get(TABLE_ID, x)
            if value is not NOT_UPDATED:
                self.rendered[x] = value
        return NOT_UPDATED if children is NOT_UPDATED else children['props']['children']

    def test_table_saved_after_a_stale_draw_is_shown(self):
        # Drawn before the table of this run exists: the earlier one is shown, as stale
        self.save('two configurations', self.revision - 1)
        self.assertEqual(self.draw(), 'two configurations')
        self.assertTrue(self.rendered['data-is-stale'])

        # The table is saved at the current revision, and its trigger fires
        self.save('three configurations', self.revision)
        self.assertEqual(self.draw(), 'three configurations')
        self.assertFalse(self.rendered['data-is-stale'])

    def test_up_to_date_table_not_redrawn(self):
        self.save('three configurations', self.revision)
        self.assertEqual(self.draw(), 'three configurations')
        self.assertEqual(self.draw(), NOT_UPDATED)

    def test_stale_table_redrawn_until_current(self):
        # A table still stale is drawn again on each trigger, which is cheap, until the current one is saved
        self.save('two configurations', self.revision - 1)
        self.assertEqual(self.draw(), 'two configurations')
        self.assertEqual(self.draw(), 'two configurations')
