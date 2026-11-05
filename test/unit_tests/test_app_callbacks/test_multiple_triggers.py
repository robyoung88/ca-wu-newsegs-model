"""
Tests of callbacks with several inputs, when more than one fires in the same call (issue 153).

Dash then lists every input which fired in `ctx.triggered`, but `ctx.triggered_id` and `get_triggered_value` give only
the first. Callbacks which decided from the first alone failed, or did the wrong thing, when the others differed: in
kind (a string id with a pattern-matching one), in shape, or in what they asked for.

Each callback's handling of its triggers is tested with the combinations which can occur together; the shared helpers
in `callback_utils` are tested first. The button callbacks are also called through Dash, so that `ctx.triggered` is
Dash's own.
"""
import json
from typing import Any, cast
import unittest

from dash import html

from newsegsmodelapp.components import callback_utils
from newsegsmodelapp.components.callback_utils import Trigger, get_clicked_trigger, get_triggers, parse_prop_id
from newsegsmodelapp.components.callbacks.input_container_callbacks import input_headers_to_update
from newsegsmodelapp.components.callbacks.result_container_callbacks import (
    REFILL_INTERVAL_ID, only_project_changed, result_table_triggers,
)
from newsegsmodelapp.components.callbacks.timeseries_callbacks import ZOOM_REQUEST_ID, timeseries_triggers
from newsegsmodelapp.components.project_selector import ui_state_triggers
from newsegsmodelapp.plugins.pages.p300_psa_configuration_layout import psa_plot_triggers

from .dash_dispatch import UPDATE_URL, stringify_id

def entry(id_: str | dict, prop: str = 'data', value: Any = 1) -> dict:
    """An entry of `ctx.triggered`."""
    return {'prop_id': f'{stringify_id(id_)}.{prop}', 'value': value}

def triggers(*entries: dict) -> list[Trigger]:
    return get_triggers(list(entries))

INITIAL_CALL = {'prop_id': '.', 'value': None}

def postaction(key: str, section: str = 'tabledraw', supersection: str = 'global', subindex: int = 0) -> dict:
    return {'type': 'postaction-trigger', 'purpose': 'trigger', 'supersection': supersection, 'section': section,
            'key': key, 'subindex': subindex}

# -----------------------------------------------
# Shared helpers
# -----------------------------------------------

class TestTriggers(unittest.TestCase):

    def test_parse_prop_id(self):
        self.assertEqual(parse_prop_id('active-project-id.data'), ('active-project-id', 'data'))
        self.assertEqual(parse_prop_id('{"index":1,"type":"config-dup-btn"}.n_clicks'), ({'index': 1, 'type': 'config-dup-btn'}, 'n_clicks'))
        # A string id may contain dots; the property is after the last
        self.assertEqual(parse_prop_id('a.b.value'), ('a.b', 'value'))
        self.assertEqual(parse_prop_id('.'), (None, ''))

    def test_mixed_triggers(self):
        trigs = triggers(entry(postaction('table_finance')), entry(REFILL_INTERVAL_ID, 'n_intervals', 1))
        self.assertEqual([x.is_pattern() for x in trigs], [True, False])
        self.assertEqual(trigs[0].type, 'postaction-trigger')
        self.assertIsNone(trigs[1].type)
        self.assertEqual((trigs[1].property, trigs[1].value), ('n_intervals', 1))

    def test_initial_call_has_no_triggers(self):
        self.assertEqual(get_triggers([INITIAL_CALL]), [])

    def test_clicked_trigger(self):
        drawn = entry({'type': 'action-button-ps', 'key': 'rename-project'}, 'n_clicks', None)
        clicked = entry('delete-project-confirm-dialog', 'submit_n_clicks', 1)
        # Buttons drawn with no clicks are ignored, whatever their order or the kind of their ids
        for order in ((drawn, clicked), (clicked, drawn)):
            with self.subTest(order = order):
                self.assertEqual(cast(Trigger, get_clicked_trigger(triggers(*order))).id, 'delete-project-confirm-dialog')
        self.assertIsNone(get_clicked_trigger(triggers(drawn)))
        self.assertIsNone(get_clicked_trigger([]))
        # Two clicks at once: which was meant is unknown
        self.assertIsNone(get_clicked_trigger(triggers(clicked, entry('btn-psa-prerun', 'n_clicks', 2))))

    def test_ids_to_update(self):
        targets = [
            {'type': 'result-table', 'purpose': 'container', 'supersection': 'deterministic', 'section': 'tabledraw', 'key': k, 'subindex': 0}
            for k in ('table_generation', 'table_finance')
        ]
        def update(*entries, **kwargs):
            return callback_utils.ids_to_update(triggers(*entries), targets, 'result-table', 'container', **kwargs)
        self.assertEqual(update(entry(postaction('table_finance'))), [targets[1]])
        # A string id, with a pattern-matching one first or second, redraws everything
        self.assertEqual(update(entry(postaction('table_finance')), entry('active-project-id')), targets)
        self.assertEqual(update(entry('active-project-id'), entry(postaction('table_finance'))), targets)
        # So does an id of another shape (no section), or a type redrawing everything
        toggle = entry({'type': 'annual-horizon-toggle', 'page': 'site-config'}, 'value', True)
        self.assertEqual(update(entry(postaction('table_finance')), toggle), targets)
        self.assertEqual(
            update(entry({'type': 'other', 'section': 'tabledraw', 'key': 'table_finance'}), update_all_types = ['other']),
            targets,
        )
        self.assertEqual(update(INITIAL_CALL), targets)

# -----------------------------------------------
# Result containers and tables
# -----------------------------------------------

class TestResultTriggers(unittest.TestCase):

    def test_refill_interval_reset_with_a_postaction_trigger(self):
        # The interval is reset to 0 on a change of project; a post-action trigger in the same call is still acted on,
        # whichever is first
        finance = entry(postaction('table_finance'))
        reset = entry(REFILL_INTERVAL_ID, 'n_intervals', 0)
        for order in ((reset, finance), (finance, reset)):
            with self.subTest(order = order):
                self.assertEqual(result_table_triggers(list(order)), [finance])

    def test_refill_interval(self):
        tick = entry(REFILL_INTERVAL_ID, 'n_intervals', 1)
        self.assertEqual(result_table_triggers([tick]), [tick])
        self.assertIsNone(result_table_triggers([entry(REFILL_INTERVAL_ID, 'n_intervals', 0)]))
        self.assertEqual(result_table_triggers([INITIAL_CALL]), [])

    def test_only_project_changed(self):
        project = entry('active-project-id')
        self.assertTrue(only_project_changed(triggers(project)))
        # With a change of page or layout, before or after it, every container is redrawn
        for other in (entry('url', 'pathname', '/sprake/site-config'), entry('layout-update-trigger')):
            for order in ((project, other), (other, project)):
                with self.subTest(order = order):
                    self.assertFalse(only_project_changed(triggers(*order)))
        self.assertFalse(only_project_changed([]))

# -----------------------------------------------
# Input headers
# -----------------------------------------------

HEADERS = [
    {'type': 'input-section-header', 'supersection': 'deterministic', 'section': 'gen_input'},
    {'type': 'input-section-header', 'supersection': 'deterministic', 'section': 'cs_input'},
]

def config_update(section: str, supersection: str = 'deterministic') -> dict:
    return {'type': 'input-group-config-update-trigger', 'supersection': supersection, 'purpose': 'trigger',
            'section': section, 'key': 'wind_capacity', 'subindex': 0, 'parameter_index': 0, 'vector_location': 0}

class TestInputHeaderTriggers(unittest.TestCase):

    def test_section_update(self):
        self.assertEqual(input_headers_to_update(triggers(entry(config_update('gen_input'), value = 5)), HEADERS), ([HEADERS[0]], False))

    def test_project_change_with_a_section_update(self):
        # The project change rebuilds everything, whether it is first or second
        project = entry('active-project-id', value = 'proj-1')
        section = entry(config_update('gen_input'), value = 5)
        for order in ((project, section), (section, project)):
            with self.subTest(order = order):
                self.assertEqual(input_headers_to_update(triggers(*order), HEADERS), (HEADERS, True))

    def test_project_change_with_triggers_after_hydration(self):
        # The update triggers fire with no value after hydration; they no longer hide a change of project
        project = entry('active-project-id', value = 'proj-1')
        hydrated = entry(config_update('gen_input'), value = None)
        self.assertEqual(input_headers_to_update(triggers(hydrated, project), HEADERS), (HEADERS, True))
        self.assertEqual(input_headers_to_update(triggers(hydrated), HEADERS), ([], False))

    def test_several_sections(self):
        trigs = triggers(entry(config_update('cs_input'), value = 1), entry(config_update('gen_input'), value = 2))
        self.assertEqual(input_headers_to_update(trigs, HEADERS), (HEADERS, False))

    def test_section_without_header(self):
        trigs = triggers(entry(config_update('optim_input', supersection = 'optim'), value = 1))
        self.assertEqual(input_headers_to_update(trigs, HEADERS), ([], False))

# -----------------------------------------------
# Timeseries
# -----------------------------------------------

class TestTimeseriesTriggers(unittest.TestCase):

    def test_results_with_a_zoom(self):
        results = entry(postaction('table_generation'))
        zoom = entry(ZOOM_REQUEST_ID, value = {'range': ['2024-01-01', '2024-01-02']})
        for order in ((results, zoom), (zoom, results)):
            with self.subTest(order = order):
                self.assertEqual(timeseries_triggers(triggers(*order)), (True, True))

    def test_single_triggers(self):
        self.assertEqual(timeseries_triggers(triggers(entry('active-project-id'))), (False, False))
        self.assertEqual(timeseries_triggers(triggers(entry(ZOOM_REQUEST_ID))), (False, True))
        manual = {**postaction('timeseriesupdate'), 'purpose': 'manualtrigger'}
        self.assertEqual(timeseries_triggers(triggers(entry(manual), entry('active-project-id'))), (False, False))

# -----------------------------------------------
# Project selector
# -----------------------------------------------

class TestUiStateTriggers(unittest.TestCase):

    def test_project_and_app_state_on_a_change_of_page(self):
        # Either first: the header and snapshots follow the project, and the project list the app state
        project, state = entry('active-project-id'), entry('app-state')
        for order in ((project, state), (state, project)):
            with self.subTest(order = order):
                self.assertEqual(ui_state_triggers(triggers(*order)), {'active-project-id', 'app-state'})

    def test_project_change_resets_inputs(self):
        trigs = triggers(
            entry('select-load-snapshot', 'value', 3), entry('active-project-id'),
            entry('input-project-name', 'value', 'Old name'),
        )
        self.assertEqual(ui_state_triggers(trigs), {'active-project-id'})
        # The app state resets only the project inputs
        trigs = triggers(entry('app-state'), entry('select-load-project', 'value', 'p'), entry('input-snapshot-name', 'value', 'S'))
        self.assertEqual(ui_state_triggers(trigs), {'app-state', 'input-snapshot-name'})

    def test_inputs_together(self):
        trigs = triggers(entry('select-load-snapshot', 'value', 3), entry('input-snapshot-name', 'value', 'Before'))
        self.assertEqual(ui_state_triggers(trigs), {'select-load-snapshot', 'input-snapshot-name'})

# -----------------------------------------------
# PSA plot
# -----------------------------------------------

PLOT_TYPE = {'type': 'result-table-option', 'purpose': 'plot-type', 'supersection': 'psa', 'section': 'tabledraw',
             'key': 'table_psa_metamodel', 'subindex': 1}
PLOT_CONTROL = {'type': 'psa-graph-plot-control', 'page': 'psa', 'key': 'psa-primary-plot-ceac-statistic'}

class TestPsaPlotTriggers(unittest.TestCase):

    def test_control_with_a_plot_type(self):
        # A change of plot type redraws, and gives the type, whichever is first
        control = entry(PLOT_CONTROL, 'value', 'npv')
        plot_type = entry(PLOT_TYPE, 'value', 'ceac')
        for order in ((control, plot_type), (plot_type, control)):
            with self.subTest(order = order):
                self.assertEqual(psa_plot_triggers(triggers(*order)), (True, 'ceac'))

    def test_control_with_the_project(self):
        trigs = triggers(entry(PLOT_CONTROL, 'value', 'npv'), entry('active-project-id'))
        self.assertEqual(psa_plot_triggers(trigs), (True, None))

    def test_results_and_controls_update_the_plot(self):
        self.assertEqual(psa_plot_triggers(triggers(entry(postaction('table_psa_metamodel', supersection = 'psa')))), (False, None))
        self.assertEqual(psa_plot_triggers(triggers(entry(PLOT_CONTROL, 'value', 'npv'))), (False, None))

# -----------------------------------------------
# Button callbacks, through Dash
# -----------------------------------------------

class TestButtonCallbacks(unittest.TestCase):
    """The callbacks of dialogs and buttons, called as the browser calls them, with several of their inputs at once."""

    @classmethod
    def setUpClass(cls):
        import newsegsmodelframework.register_plugins  # noqa: F401
        import newsegsmodelapp.register_plugins  # noqa: F401
        from newsegsmodelapp.dash_extension import NewsegsDash
        from newsegsmodelapp.plugins.pages import p000_model_selection_layout, p200_dsa_configuration_layout, p300_psa_configuration_layout

        unused = cast(Any, None)
        cls.app = NewsegsDash(
            __name__, project_provider = unused, results_provider = unused, request_handler = unused,
            suppress_callback_exceptions = True,
        )
        cls.app.layout = html.Div()
        p200_dsa_configuration_layout.add_dsa_run_callbacks(cls.app)
        p200_dsa_configuration_layout.add_optim_run_callbacks(cls.app)
        p300_psa_configuration_layout.add_psa_run_callbacks(cls.app)
        p000_model_selection_layout.assign_callbacks(cls.app)
        cls.app.server.config['TESTING'] = True
        cls.client = cls.app.server.test_client()

    def _call(self, output: str, inputs: list[tuple[str | dict, str, Any]], changed: list[int]):
        """Call the callback with an output, with the values of its inputs, of which those at `changed` fired."""
        deps = self.client.get('/_dash-dependencies').get_json()
        # A grouped output is registered as several (`..<id>.<prop>..`), even if it is one
        dep = next(x for x in deps if x['output'] in (output, f'..{output}..'))
        single = {'id': output.rsplit('.', 1)[0], 'property': output.rsplit('.', 1)[1]}
        payload = {
            'output': dep['output'],
            'outputs': single if dep['output'] == output else [single],
            'inputs': [
                {'id': id_, 'property': prop, 'value': value} for id_, prop, value in inputs
            ],
            'state': [{'id': x['id'], 'property': x['property'], 'value': None} for x in dep['state']],
            'changedPropIds': [f'{stringify_id(inputs[i][0])}.{inputs[i][1]}' for i in changed],
        }
        response = self.client.post(UPDATE_URL, json = payload)
        if response.status_code == 204:
            return None
        self.assertEqual(response.status_code, 200, response.data)
        return response.get_json()['response']

    def _modal(self, output: str, buttons: list[str], values: list[Any], changed: list[int]):
        response = self._call(output, [(b, 'n_clicks', v) for b, v in zip(buttons, values)], changed)
        if response is None:
            return None
        id_, prop = output.rsplit('.', 1)
        return response[id_][prop]

    def test_dsa_run_confirm(self):
        buttons = ['btn-action-dsa-run-metamodel', 'btn-dsa-confirm-abort', 'btn-dsa-prerun']
        output = 'modal-dsa-confirm.is_open'
        # The prerun button clicked as the others are drawn opens the dialog, though not first
        self.assertTrue(self._modal(output, buttons, [None, None, 1], [0, 1, 2]))
        self.assertFalse(self._modal(output, buttons, [1, None, None], [0, 2]))
        self.assertIsNone(self._modal(output, buttons, [None, None, None], [0, 1, 2]))

    def test_optim_run_confirm(self):
        buttons = ['btn-action-optim-run-metamodel', 'btn-optim-confirm-abort', 'btn-optim-prerun']
        output = 'modal-optim-confirm.is_open'
        self.assertTrue(self._modal(output, buttons, [None, None, 1], [0, 2]))
        # Drawn with no clicks: the dialog is left as it is, where it used to be closed
        self.assertIsNone(self._modal(output, buttons, [None, None, None], [0, 1, 2]))

    def test_psa_run_confirm(self):
        buttons = ['btn-action-psa-run-metamodel', 'btn-psa-confirm-abort', 'btn-psa-prerun']
        output = 'modal-psa-confirm.is_open'
        self.assertTrue(self._modal(output, buttons, [None, None, 2], [1, 2]))

    def test_model_selection(self):
        ids = [{'label': x, 'type': 'btn-model-type-selector'} for x in ('sprake', 'sprakeloc')]
        output = 'url.pathname'
        deps = self.client.get('/_dash-dependencies').get_json()
        dep = next(x for x in deps if x['output'] == output)
        def call(values, changed):
            payload = {
                'output': dep['output'],
                'outputs': {'id': 'url', 'property': 'pathname'},
                'inputs': [[{'id': id_, 'property': 'n_clicks', 'value': v} for id_, v in zip(ids, values)]],
                'state': [],
                'changedPropIds': [f'{json.dumps(ids[i], sort_keys = True, separators = (",", ":"))}.n_clicks' for i in changed],
            }
            response = self.client.post(UPDATE_URL, json = payload)
            return None if response.status_code == 204 else response.get_json()['response']['url']['pathname']
        self.assertEqual(call([None, 1], [0, 1]), '/sprakeloc/landing')
        self.assertEqual(call([1, None], [0]), '/sprake/landing')
        self.assertIsNone(call([None, None], [0, 1]))

if __name__ == '__main__':
    unittest.main()
