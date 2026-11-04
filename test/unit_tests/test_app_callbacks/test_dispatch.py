"""
Tests of how `react_to_input_change` dispatches a change: to the handler of its purpose, or to no update at all.
"""
from unittest import mock

from dash import dcc
from dash.exceptions import PreventUpdate

from newsegsmodelapp import registers

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import variable_id

SECTION, KEY = 'gen_input', 'wind_capacity'
VARID = f'{SECTION}.{KEY}.0'

PROBE = 'test-probe'

def probe_id(purpose: str = PROBE, **kwargs) -> dict:
    """Id of an input with a purpose of its own, in the row of the wind capacity"""
    return variable_id('single-input-config', purpose, SECTION, KEY, **kwargs)

class Probe:
    """A handler which records its calls, and sets the triggers of the row to its name"""
    def __init__(self, name: str):
        self.name = name
        self.calls = []

    def __call__(self, triggered_id, input_ids, header_ids, trigger_ids, calling_dict, active_project_id, project_provider, return_dict):
        self.calls.append(dict(
            triggered_id = triggered_id,
            input_ids = input_ids,
            trigger_ids = trigger_ids,
            active_project_id = active_project_id,
            project_provider = project_provider,
        ))
        for idx in range(len(trigger_ids)):
            return_dict['trigger_data'][idx] = self.name
        return return_dict

class TestDispatch(InputChangeTestCase):
    """Dispatch of a change to a handler, or to no update"""

    def setUp(self):
        super().setUp()
        self.components = self.page(('deterministic', SECTION)) + [dcc.Input(id = probe_id())]

    def _register(self, *model_types: str) -> dict[str, Probe]:
        """Register a probe handler for each model type, for the duration of the test"""
        probes = {x: Probe(x) for x in model_types}
        patcher = mock.patch.dict(
            registers.INPUT_HANDLERS,
            {(PROBE, 'single-input-config', x): probe for x, probe in probes.items()},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return probes

    def _trigger_data(self, response) -> list:
        return [
            response.get(variable_id('input-group-config-update-trigger', 'trigger', SECTION, KEY), 'data')
        ]

    def test_registered_purpose_reaches_handler(self):
        probe = self._register('default')['default']
        response = self.dispatch(probe_id(), 1., self.components)

        self.assertEqual(len(probe.calls), 1)
        call = probe.calls[0]
        self.assertEqual(call['triggered_id'], probe_id())
        self.assertEqual(call['active_project_id'], self.project_id)
        self.assertIs(call['project_provider'], self.provider)
        self.assertIn(probe_id(), call['input_ids'])
        self.assertIn(variable_id('single-input-config', 'parameter', SECTION, KEY), call['input_ids'])
        self.assertEqual(call['trigger_ids'], [variable_id('input-group-config-update-trigger', 'trigger', SECTION, KEY)])

        self.assertEqual(self._trigger_data(response), ['default'])

    def test_default_handler_used_without_handler_for_model_type(self):
        # A handler of another model type is not used
        probes = self._register('default', 'sprakeloc')
        response = self.dispatch(probe_id(), 1., self.components, model_type = 'sprake')

        self.assertEqual(len(probes['default'].calls), 1)
        self.assertEqual(len(probes['sprakeloc'].calls), 0)
        self.assertEqual(self._trigger_data(response), ['default'])

    def test_model_specific_handler_takes_priority(self):
        probes = self._register('default', 'sprake')
        response = self.dispatch(probe_id(), 1., self.components, model_type = 'sprake')

        self.assertEqual(len(probes['sprake'].calls), 1)
        self.assertEqual(len(probes['default'].calls), 0)
        self.assertEqual(self._trigger_data(response), ['sprake'])

    def test_handler_preventing_update_makes_no_update(self):
        patcher = mock.patch.dict(
            registers.INPUT_HANDLERS,
            {(PROBE, 'single-input-config', 'default'): mock.Mock(side_effect = PreventUpdate)},
        )
        patcher.start()
        self.addCleanup(patcher.stop)

        response = self.dispatch(probe_id(), 1., self.components)
        self.assertFalse(response.updated)

    def test_unknown_purpose_makes_no_update(self):
        components = self.components + [dcc.Input(id = probe_id('no-such-purpose'))]
        before = self.database_state()

        with self.assertLogs('newsegsmodelapp.components.callbacks.input_container_callbacks', 'ERROR'):
            response = self.dispatch(probe_id('no-such-purpose'), 1., components)

        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

    def test_several_triggered_inputs_make_no_update(self):
        before = self.database_state()
        response = self.dispatch(
            variable_id('single-input-config', 'parameter', SECTION, KEY), 12.5, self.components,
            also_triggered = [(variable_id('input-action-button', 'value-reset', SECTION, KEY), 1)],
        )
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

    def test_no_active_project_makes_no_update(self):
        before = self.database_state()
        response = self.dispatch(
            variable_id('single-input-config', 'parameter', SECTION, KEY), 12.5, self.components,
            project_id = None,
        )
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

    def test_other_rows_not_affected(self):
        # The same key in another section, and another subindex of the same key
        others = [
            variable_id('single-input-config', 'parameter', 'stor_input', KEY),
            variable_id('single-input-config', 'parameter', SECTION, KEY, subindex = 1),
        ]
        components = self.components + [dcc.Input(id = x, value = 3.) for x in others]
        before = self.revisions()

        response = self.dispatch(variable_id('single-input-config', 'parameter', SECTION, KEY), 12.5, components)

        self.assertTrue(response.updated)
        for id_ in response.updated_ids():
            self.assertEqual((id_['section'], id_['key'], id_['subindex']), (SECTION, KEY, 0))
        self.assertTrue(any(x['key'] == 'pv_capacity' for x in (c.id for c in components)))

        var_uid = self.variable_uid(VARID)
        self.assertEqual(self.revised(before)['variable_configs'], {(var_uid,)})

TestDispatchCached = cached_variant(TestDispatch)
