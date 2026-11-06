"""
Tests of the input handlers that plug-ins register with `register_input_handler`, dispatched by `react_to_input_change`.
"""
import json

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db_staleness import PROCESSES
from newsegsmodelapp.components import staleness

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, variable_id

WIND = ('gen_input', 'wind_capacity')
WIND_VARID = 'gen_input.wind_capacity.0'
# Has a Gamma distribution, which rejects a negative mean, and is selected for the PSA
CAPEX = ('gen_costs', 'wind_capex_per_kw')
CAPEX_VARID = 'gen_costs.wind_capex_per_kw.0'

def row_id(type_: str, purpose: str, row: tuple[str, str], supersection: str = 'deterministic', **kwargs) -> dict:
    return variable_id(type_, purpose, *row, supersection = supersection, **kwargs)

class TestParameter(InputChangeTestCase):
    """`parameter` of a `single-input-config`: a change to a parameter of a variable"""
    n_metamodels = 2

    def setUp(self):
        super().setUp()
        self.components = self.page(('deterministic', 'gen_input'), ('dsa', None), ('optim', None))
        self.trigger = row_id('single-input-config', 'parameter', WIND)

    def test_value_saved(self):
        t0 = self.now()
        before = self.revisions()
        response = self.dispatch(self.trigger, 12.5, self.components)

        # Saved, for every configuration sharing the variable
        for mm_index in range(self.n_metamodels):
            self.assertEqual(self.loaded_variable(WIND_VARID, mm_index).raw_parameters[0], 12.5)

        # The inputs of every supersection are given the value
        for supersection in ('deterministic', 'dsa', 'optim'):
            self.assertEqual(
                response.get(row_id('single-input-config', 'parameter', WIND, supersection), 'value'), 12.5
            )

        # The headers that have a content creator are drawn again
        self.assertIsNot(response.get(row_id('single-input-header', 'header', WIND, 'dsa'), 'children'), NOT_UPDATED)

        # The deterministic value and the DSA bounds (relative to it) have changed; the optimisation is not signalled
        for supersection, fired in (('deterministic', True), ('dsa', True), ('optim', False)):
            data = response.get(row_id('input-group-config-update-trigger', 'trigger', WIND, supersection), 'data')
            self.assertEqual(data is not NOT_UPDATED, fired, supersection)

        lproj = self.reader.get_lightweight_project(self.project_id)
        revised = self.revised(before)
        self.assertEqual(revised['variable_configs'], {(self.variable_uid(WIND_VARID),)})
        self.assertEqual(revised['metamodels'], {(x,) for x in self.metamodel_ids})
        self.assertEqual(revised['projects'], {(self.project_id,)})
        self.assertEqual(
            revised['component_configs'],
            {(lproj.table_config.id,)} | {
                (x,) for mm in lproj.metamodels
                for x in (mm.table_config.id, mm.model.table_config.id, mm.finance.table_config.id)
            },
        )

        # A change of the deterministic value makes every process of the group stale
        self.assertEqual(self.stale_marks(t0), {(mm, p) for mm in self.metamodel_ids for p in PROCESSES})

    def test_independent_configuration_not_marked_stale(self):
        self.make_independent(1, WIND_VARID)
        t0 = self.now()

        self.dispatch(self.trigger, 12.5, self.components)

        self.assertEqual(self.loaded_variable(WIND_VARID, 0).raw_parameters[0], 12.5)
        self.assertNotEqual(self.loaded_variable(WIND_VARID, 1).raw_parameters[0], 12.5)
        self.assertEqual(self.stale_marks(t0), {(self.metamodel_ids[0], p) for p in PROCESSES})

    def test_rejected_value(self):
        # The PSA inputs include the second parameter (the standard deviation)
        components = self.page(('deterministic', 'gen_costs'), ('psa', None))
        saved = self.stored_variable(CAPEX_VARID).raw_parameters
        before = self.database_state()

        response = self.dispatch(row_id('single-input-config', 'parameter', CAPEX), -5., components)

        # The inputs are returned to the saved parameters
        for supersection, parameter_index in (('deterministic', 0), ('psa', 0), ('psa', 1)):
            self.assertEqual(
                response.get(
                    row_id('single-input-config', 'parameter', CAPEX, supersection, parameter_index = parameter_index),
                    'value',
                ),
                saved[parameter_index],
            )
        self.assertNothingChanged(before)

        # The variable is intact for the next change, including any held by a cache
        self.dispatch(row_id('single-input-config', 'parameter', CAPEX, 'psa', parameter_index = 1), 1000., components)
        self.assertEqual(self.stored_variable(CAPEX_VARID).raw_parameters, (saved[0], 1000.))

class TestValueReset(InputChangeTestCase):
    """`value-reset` of an `input-action-button`: resetting a parameter to its default"""

    def test_value_restored(self):
        components = self.page(('deterministic', 'gen_input'))
        default = self.stored_variable(WIND_VARID)._default_parameters[0]
        self.dispatch(row_id('single-input-config', 'parameter', WIND), default + 10., components)
        t0 = self.now()

        response = self.dispatch(row_id('input-action-button', 'value-reset', WIND), 1, components)

        self.assertEqual(self.stored_variable(WIND_VARID).raw_parameters[0], default)
        self.assertEqual(response.get(row_id('single-input-config', 'parameter', WIND), 'value'), default)
        self.assertEqual(self.stale_marks(t0), {(self.metamodel_ids[0], p) for p in PROCESSES})

    def test_initial_call_makes_no_update(self):
        components = self.page(('deterministic', 'gen_input'))
        before = self.database_state()
        response = self.dispatch(row_id('input-action-button', 'value-reset', WIND), None, components)
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

class TestValueSetDefault(InputChangeTestCase):
    """`value-set-default` of an `input-action-button`: making the current value of a parameter its default"""

    def test_default_updated(self):
        components = self.page(('deterministic', 'gen_input'))
        self.dispatch(row_id('single-input-config', 'parameter', WIND), 12.5, components)
        t0 = self.now()

        response = self.dispatch(row_id('input-action-button', 'value-set-default', WIND), 1, components)

        self.assertFalse(response.updated)
        self.assertEqual(self.stored_variable(WIND_VARID)._default_parameters[0], 12.5)
        self.assertEqual(self.loaded_variable(WIND_VARID)._default_parameters[0], 12.5)
        self.assertEqual(self.stale_marks(t0), set())

        # A reset now returns to it
        self.dispatch(row_id('single-input-config', 'parameter', WIND), 20., components)
        self.dispatch(row_id('input-action-button', 'value-reset', WIND), 2, components)
        self.assertEqual(self.stored_variable(WIND_VARID).raw_parameters[0], 12.5)

class TestToggleOptimActive(InputChangeTestCase):
    """`toggle-optim-active` of an `input-toggle`: selecting a variable for the optimisation"""
    n_metamodels = 3

    def setUp(self):
        super().setUp()
        # The third configuration has a separate instance of the variable
        self.make_independent(2, WIND_VARID)
        self.components = self.page(('optim', None))
        self.toggle = row_id('input-toggle', 'toggle-optim-active', WIND, 'optim')

    def test_only_that_variable_changes(self):
        selected = self.stored_variable(WIND_VARID).optim_selected
        variables = self._rows(tbls.variable_configs)
        uid = self.variable_uid(WIND_VARID)
        t0 = self.now()

        response = self.dispatch(self.toggle, not selected, self.components)

        self.assertEqual(self.stored_variable(WIND_VARID).optim_selected, not selected)
        self.assertEqual(self.loaded_variable(WIND_VARID, 1).optim_selected, not selected)
        # Not synced onto the separate instance, as DSA and PSA selections are
        self.assertEqual(self.loaded_variable(WIND_VARID, 2).optim_selected, selected)
        after = self._rows(tbls.variable_configs)
        self.assertEqual({k for k in after if after[k] != variables[k]}, {(uid,)})

        self.assertEqual(self.stale_marks(t0), {(x, 'optim') for x in self.metamodel_ids[:2]})
        self.assertIsNot(response.get(row_id('input-group-config-update-trigger', 'trigger', WIND, 'optim'), 'data'), NOT_UPDATED)

    def test_selection_reaches_a_worker(self):
        # A worker which has run the project holds it in its cache; the optimisation runs there
        worker = self.worker_provider()
        selected = self.stored_variable(WIND_VARID).optim_selected
        self.dispatch(self.toggle, not selected, self.components)
        self.assertEqual(
            worker.get_project(self.project_id).metamodels[0].variables[WIND_VARID].optim_selected, not selected
        )

    def test_unchanged_makes_no_update(self):
        selected = self.stored_variable(WIND_VARID).optim_selected
        before = self.database_state()
        response = self.dispatch(self.toggle, selected, self.components)
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)


class TestPsaActive(InputChangeTestCase):
    """`psa-active`, of any type: selecting a variable for the PSA"""
    n_metamodels = 3

    def setUp(self):
        super().setUp()
        # The first two configurations share the variable; the third has a separate instance
        self.make_independent(2, CAPEX_VARID)
        self.components = self.page(('psa', None))
        self.toggle = row_id('input-toggle', 'psa-active', CAPEX, 'psa')

    def test_selection_synced(self):
        selected = self.stored_variable(CAPEX_VARID).psa_selected
        t0 = self.now()

        response = self.dispatch(self.toggle, not selected, self.components)

        for mm_index in range(self.n_metamodels):
            self.assertEqual(self.loaded_variable(CAPEX_VARID, mm_index).psa_selected, not selected, mm_index)
        self.assertEqual(self.stale_marks(t0), {(x, 'psa') for x in self.metamodel_ids})

        data = response.get(row_id('input-group-config-update-trigger', 'trigger', CAPEX, 'psa'), 'data')
        self.assertEqual(json.loads(data)['message'], 'psa_selection_status_modified')

    def test_unchanged_makes_no_update(self):
        selected = self.stored_variable(CAPEX_VARID).psa_selected
        before = self.database_state()
        response = self.dispatch(self.toggle, selected, self.components)
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

class TestPsaSettings(InputChangeTestCase):
    """`psa-settings`, of any type: the settings of the project's PSA"""
    n_metamodels = 2

    def setUp(self):
        super().setUp()
        self.components = self.page(('psa', 'psa-settings'))

    def _setting_id(self, key: str) -> dict:
        return variable_id('single-input-config', 'psa-settings', 'psa-settings', key, supersection = 'psa')

    def _psa_config(self):
        lproj = self.reader.get_lightweight_project(self.project_id)
        return self.reader._component_provider.get_component(lproj.psa_config.id)

    def _check_saved(self, key: str, value, sent = None):
        t0 = self.now()
        before = self.revisions()
        lproj = self.reader.get_lightweight_project(self.project_id)

        response = self.dispatch(self._setting_id(key), value if sent is None else sent, self.components)

        self.assertEqual(getattr(self._psa_config(), key), value)
        self.assertEqual(response.get(self._setting_id(key), 'value'), value)
        self.assertIsNot(
            response.get(variable_id('input-group-config-update-trigger', 'trigger', 'psa-settings', key, supersection = 'psa'), 'data'),
            NOT_UPDATED,
        )
        revised = self.revised(before)
        self.assertEqual(revised['projects'], {(self.project_id,)})
        self.assertIn((lproj.table_config.id,), revised['component_configs'])
        self.assertEqual(self.stale_marks(t0), {(x, 'psa') for x in self.metamodel_ids})

    def test_samples_saved(self):
        self._check_saved('samples', 500)

    def test_samples_clamped(self):
        self._check_saved('samples', 10, sent = 3)

    def test_seed_saved(self):
        self._check_saved('seed', 1234)

    def test_return_draws_saved(self):
        self._check_saved('return_draws', not self._psa_config().return_draws)

    def test_unchanged_makes_no_update(self):
        before = self.database_state()
        response = self.dispatch(self._setting_id('samples'), self._psa_config().samples, self.components)
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

TestParameterCached = cached_variant(TestParameter)
TestValueResetCached = cached_variant(TestValueReset)
TestValueSetDefaultCached = cached_variant(TestValueSetDefault)
TestToggleOptimActiveCached = cached_variant(TestToggleOptimActive)
TestPsaActiveCached = cached_variant(TestPsaActive)
TestPsaSettingsCached = cached_variant(TestPsaSettings)
