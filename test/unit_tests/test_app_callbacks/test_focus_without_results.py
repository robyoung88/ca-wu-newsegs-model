"""
Tests of switching the focus to a configuration without results (#187), through the callbacks of the result tables and
figures as Dash dispatches them.

A change of focus keeps the project and its revision, so a table was taken to be already drawn if the revision recorded
when it was drawn happened to match the project's. A figure was left as it was whenever there was no result for it.
"""
from pathlib import Path
from typing import cast
from unittest import mock

from dash import dcc, html
import plotly.graph_objects as go

from newsegsmodelapp import registers
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsComponentProvider
from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.components.callbacks.result_container_callbacks import (
    EMPTY_FIGURE, REFILL_INTERVAL_ID, add_result_container_callbacks,
)
from newsegsmodelapp.dash_extension import NewsegsDash

from .base import InputChangeTestCase
from .dash_dispatch import NOT_UPDATED, dispatch_callback, get_callback_spec

# Drawn by a table getter, from the focussed configuration's results
CONFIG_TABLE = 'table_dsa_metamodel'
# Drawn by the conventional lookup, from the project's results
PROJECT_TABLE = 'table_net'
# Saved on the project, of which there is one, and shown for the configuration which it names
OPTIM_TABLE = 'table_postopt_metamodel'
OPTIM_FIGURE = 'table_optim_metamodel'
RENDERED = (
    'data-rendered-project-id', 'data-rendered-project-table-revision', 'data-rendered-ann-hori-state',
    'data-rendered-metamodel-id', 'data-is-stale',
)
FIGURE_ID = {'type': 'result-figure', 'purpose': 'container', 'supersection': 'dsa', 'section': 'tabledraw', 'key': CONFIG_TABLE, 'subindex': 1}
FIGURE_TRIGGER_ID = {'type': 'postaction-trigger', 'purpose': 'trigger', 'supersection': 'global', 'section': 'tabledraw', 'key': CONFIG_TABLE, 'subindex': 0}

def table_id(key: str) -> dict:
    return {'type': 'result-table', 'purpose': 'container', 'supersection': 'dsa', 'section': 'tabledraw', 'key': key, 'subindex': 0}

class TestFocusWithoutResults(InputChangeTestCase):
    n_metamodels = 2

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

        self.lproj = self.provider.get_lightweight_project(self.project_id)
        self.components = cast(FromDatabaseNewsegsComponentProvider, self.provider._component_provider)
        self.revision = self.lproj.table_config.revision
        # What the page holds of each table: nothing drawn yet
        self.rendered = {x: {y: None for y in RENDERED} for x in (CONFIG_TABLE, PROJECT_TABLE, OPTIM_TABLE)}
        self.stores = {'active-project-id': self.project_id, 'app-state': '{"model_type": "sprake"}'}

    def focus(self, mm_index: int):
        """Focus a configuration, as `set_focussed_config` does: the project and its revisions are unchanged"""
        self.provider.set_component_metadata(
            self.project_id, 'focussed_metamodel_id', self.metamodel_ids[mm_index], increment_revision = False
        )

    def save_for_configuration(self, mm_index: int, label: str):
        """Save the table of a configuration, as of the revision of the project: the case which looked already drawn"""
        config = self.components.get_lightweight_dataholding_component(self.lproj.metamodels[mm_index].table_config.id)
        self.results.upsert_result(CONFIG_TABLE, config, html.Div(label), revision = self.revision)

    def refill(self, key: str, trigger: str | dict = REFILL_INTERVAL_ID):
        """The tick of the refill interval which follows a change of focus, or another trigger; returns the table, if redrawn"""
        components = [html.Div(id = table_id(key), **self.rendered[key])]
        if isinstance(trigger, dict):
            components.append(html.Div(id = trigger))
        response = dispatch_callback(
            self.client, get_callback_spec(self.client, 'result-table', 'children'),
            trigger = trigger, value = 1,
            components = components,
            stores = self.stores,
        )
        children = response.get(table_id(key), 'children')
        for x in RENDERED:
            value = response.get(table_id(key), x)
            if value is not NOT_UPDATED:
                self.rendered[key][x] = value
        if children is NOT_UPDATED or children == []:
            return children
        return children['props']['children']

    def test_table_cleared_on_focus_without_results(self):
        self.save_for_configuration(0, 'first')
        self.assertEqual(self.refill(CONFIG_TABLE), 'first')

        self.focus(1)
        self.assertEqual(self.refill(CONFIG_TABLE), [])

    def test_table_drawn_again_on_focus_back(self):
        self.save_for_configuration(0, 'first')
        self.refill(CONFIG_TABLE)
        self.focus(1)
        self.refill(CONFIG_TABLE)

        self.focus(0)
        self.assertEqual(self.refill(CONFIG_TABLE), 'first')

    def test_table_replaced_on_focus_with_results(self):
        self.save_for_configuration(0, 'first')
        self.save_for_configuration(1, 'second')
        self.refill(CONFIG_TABLE)

        self.focus(1)
        self.assertEqual(self.refill(CONFIG_TABLE), 'second')

    def test_table_of_focussed_configuration_not_redrawn(self):
        self.save_for_configuration(0, 'first')
        self.refill(CONFIG_TABLE)
        self.assertEqual(self.refill(CONFIG_TABLE), NOT_UPDATED)

    def test_table_saved_again_at_the_same_revision_is_redrawn(self):
        # A DSA run again, e.g. with other bounds, saves its table at the revision of the one drawn (#206)
        self.save_for_configuration(0, 'first')
        self.assertEqual(self.refill(CONFIG_TABLE), 'first')

        self.save_for_configuration(0, 'run again')
        self.assertEqual(self.refill(CONFIG_TABLE, FIGURE_TRIGGER_ID), 'run again')

    def test_project_table_not_redrawn_on_focus(self):
        # Read from the project, so the same whichever configuration is focussed
        config = self.components.get_lightweight_dataholding_component(self.lproj.table_config.id)
        self.results.upsert_result(PROJECT_TABLE + '_ann', config, html.Div('project'), revision = self.revision)
        self.assertEqual(self.refill(PROJECT_TABLE), 'project')

        self.focus(1)
        self.assertEqual(self.refill(PROJECT_TABLE), NOT_UPDATED)

    def save_optimisation(self, result: dict):
        """Save the result of an optimisation and its feedback, as of the revision of the project"""
        config = self.components.get_lightweight_dataholding_component(self.lproj.table_config.id)
        self.results.upsert_result('optimisation_result', config, result, revision = self.revision)
        self.results.upsert_result(OPTIM_TABLE, config, html.Div('optimised'), revision = self.revision)

    def test_optimisation_table_only_for_its_configuration(self):
        self.save_optimisation({'metamodel_id': self.metamodel_ids[0], 'new_metamodel_id': None})
        self.assertEqual(self.refill(OPTIM_TABLE), 'optimised')

        self.focus(1)
        self.assertEqual(self.refill(OPTIM_TABLE), [])

        self.focus(0)
        self.assertEqual(self.refill(OPTIM_TABLE), 'optimised')

    def test_optimisation_table_shown_for_its_optimised_copy(self):
        # A successful optimisation focusses the copy it adds
        self.save_optimisation({'metamodel_id': self.metamodel_ids[0], 'new_metamodel_id': self.metamodel_ids[1]})
        self.focus(1)
        self.assertEqual(self.refill(OPTIM_TABLE), 'optimised')

    def test_optimisation_table_saved_without_configuration_always_shown(self):
        self.save_optimisation({'status': 'success'})
        self.focus(1)
        self.assertEqual(self.refill(OPTIM_TABLE), 'optimised')

    def _marginal_plot(self):
        """The marginal plot shown after its post-action trigger"""
        figure_id = {**FIGURE_ID, 'supersection': 'optim', 'key': OPTIM_FIGURE, 'subindex': 0}
        trigger = {**FIGURE_TRIGGER_ID, 'key': OPTIM_FIGURE}
        response = dispatch_callback(
            self.client, get_callback_spec(self.client, 'result-figure', 'figure'),
            trigger = trigger, value = 1,
            components = [dcc.Graph(id = figure_id), html.Div(id = trigger)],
            stores = self.stores,
        )
        return response.get(figure_id, 'figure')

    def save_marginal_plot(self, meta: dict | None):
        config = self.components.get_lightweight_dataholding_component(self.lproj.table_config.id)
        figure = go.Figure(layout = {'meta': meta, 'title': {'text': 'margin'}})
        self.results.upsert_result('plot_marginal_optim', config, figure, revision = self.revision)

    def test_marginal_plot_only_for_its_configuration(self):
        self.save_marginal_plot({'metamodel_id': self.metamodel_ids[0]})
        self.assertEqual(self._marginal_plot()['layout']['title']['text'], 'margin')

        self.focus(1)
        self.assertEqual(self._marginal_plot(), EMPTY_FIGURE)

    def test_marginal_plot_saved_without_configuration_always_shown(self):
        self.save_marginal_plot(None)
        self.focus(1)
        self.assertEqual(self._marginal_plot()['layout']['title']['text'], 'margin')

    def _figure_with_getter_result(self, result):
        """The figure returned when the getter of the figure gives a result"""
        getter = mock.Mock(return_value = (result, None if result is None else self.revision))
        with mock.patch.dict(registers.TABLE_GETTER_REGISTER, {(CONFIG_TABLE, 'default'): getter}):
            response = dispatch_callback(
                self.client, get_callback_spec(self.client, 'result-figure', 'figure'),
                trigger = FIGURE_TRIGGER_ID, value = 1,
                components = [dcc.Graph(id = FIGURE_ID), html.Div(id = FIGURE_TRIGGER_ID)],
                stores = self.stores,
            )
        return response.get(FIGURE_ID, 'figure')

    def test_figure_cleared_without_result(self):
        self.assertEqual(self._figure_with_getter_result(None), EMPTY_FIGURE)

    def test_figure_drawn_with_result(self):
        figure = {'data': [{'x': [1], 'y': [2]}], 'layout': {}}
        self.assertEqual(self._figure_with_getter_result(figure), figure)
