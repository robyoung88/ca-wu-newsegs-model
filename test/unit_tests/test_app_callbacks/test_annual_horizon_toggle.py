"""
Tests of the per year / to horizon toggle (#149): toggling it redraws the result tables through the
callback of the result containers, as Dash dispatches it.

The toggle's id has neither a `subindex` nor a `supersection`, and the callback failed with
`KeyError: 'subindex'` when it handled it as the id of a result. It chooses what to redraw with
`ids_to_update`, which redraws every table for the toggle (see `test_result_container_triggers`, which
also covers the headers callback).
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
from .dash_dispatch import dispatch_callback, get_callback_spec

TOGGLE_ID = {'type': 'annual-horizon-toggle', 'page': 'site-config'}
KEYS = ('table_generation', 'table_net')
RENDERED = ('data-rendered-project-id', 'data-rendered-project-table-revision', 'data-rendered-ann-hori-state', 'data-is-stale')

def _table_id(key: str) -> dict:
    return {'type': 'result-table', 'purpose': 'container', 'supersection': 'deterministic', 'section': 'tabledraw', 'key': key, 'subindex': 0}

class TestAnnualHorizonToggle(InputChangeTestCase):

    def setUp(self):
        super().setUp()
        from newsegsmodelapp.backend import db
        results = FromDatabaseResultProvider(db.get_engine, Path(self._db_dir.name) / 'results')
        self.app = NewsegsDash(
            __name__,
            project_provider = self.provider,
            results_provider = results,
            request_handler = None, # pyright: ignore[reportArgumentType]
            suppress_callback_exceptions = True,
        )
        self.app.layout = html.Div()
        add_result_container_callbacks(self.app)
        self.app.server.config['TESTING'] = True
        self.client = self.app.server.test_client()

        # The per year and to horizon versions of the tables, saved as the table draws save them
        lproj = self.provider.get_lightweight_project(self.project_id)
        component_provider = cast(FromDatabaseNewsegsComponentProvider, self.provider._component_provider)
        table_config = component_provider.get_lightweight_dataholding_component(lproj.table_config.id)
        for key in KEYS:
            results.upsert_result(key + '_ann', table_config, html.Div(f'{key} per year'))
            results.upsert_result(key + '_hori', table_config, html.Div(f'{key} to horizon'))

        # A results page: the tables, the toggle, and the trigger of a post-action
        self.components = [daq.ToggleSwitch(id = TOGGLE_ID, value = False)]
        self.components += [html.Div(id = _table_id(key), **{x: None for x in RENDERED}) for key in KEYS]
        self.postaction = {
            'type': 'postaction-trigger', 'purpose': 'trigger',
            'supersection': 'global', 'section': 'tabledraw', 'key': 'table_net', 'subindex': 0,
        }
        self.components.append(html.Div(id = self.postaction))

    def toggle(self, value: bool, also_triggered = ()):
        spec = get_callback_spec(self.client, 'result-table', 'children')
        return dispatch_callback(
            self.client, spec, trigger = TOGGLE_ID, value = value, components = self.components,
            stores = {'active-project-id': self.project_id, 'app-state': '{"model_type": "sprake"}'},
            also_triggered = also_triggered,
        )

    def assert_tables(self, response, version: str):
        for key in KEYS:
            children = response.get(_table_id(key), 'children')
            self.assertEqual(children['props']['children'], f'{key} {version}')

    def test_to_horizon(self):
        self.assert_tables(self.toggle(True), 'to horizon')

    def test_per_year(self):
        self.assert_tables(self.toggle(False), 'per year')

    def test_with_another_trigger(self):
        # Every table is redrawn, not only the one the other trigger is for
        self.assert_tables(self.toggle(True, also_triggered = [(self.postaction, 1)]), 'to horizon')
