"""
Tests of the purposes that `react_to_input_change` handles itself: the DSA bounds, bound type and selection, and the
optimisation bounds and plot resolution.
"""
import json

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, variable_id

# Selected for the DSA, with bounds relative to its value
CAPEX = ('gen_costs', 'wind_capex_per_kw')
CAPEX_VARID = 'gen_costs.wind_capex_per_kw.0'
# Selectable for the optimisation
WIND = ('gen_input', 'wind_capacity')
WIND_VARID = 'gen_input.wind_capacity.0'

def row_id(type_: str, purpose: str, row: tuple[str, str], supersection: str, **kwargs) -> dict:
    return variable_id(type_, purpose, *row, supersection = supersection, **kwargs)

class _SharedAndSeparate(InputChangeTestCase):
    """Three configurations: the first two share the variable, the third has a separate instance"""
    n_metamodels = 3
    varid: str

    def setUp(self):
        super().setUp()
        self.make_independent(2, self.varid)

    @property
    def group(self) -> list[str]:
        """Ids of the configurations sharing the variable of the focussed one"""
        return self.metamodel_ids[:2]

class TestDsaBounds(_SharedAndSeparate):
    """`bound-lower` and `bound-upper` in the `dsa` supersection"""
    varid = CAPEX_VARID

    def setUp(self):
        super().setUp()
        self.components = self.page(('dsa', None))

    def _check_saved(self, purpose: str, attribute: str):
        new = getattr(self.stored_variable(CAPEX_VARID), attribute) * 0.5
        separate = getattr(self.loaded_variable(CAPEX_VARID, 2), attribute)
        t0 = self.now()
        before = self.revisions()
        lproj = self.reader.get_lightweight_project(self.project_id)

        response = self.dispatch(row_id('single-input-config', purpose, CAPEX, 'dsa'), new, self.components)

        for mm_index in range(2):
            self.assertEqual(getattr(self.loaded_variable(CAPEX_VARID, mm_index), attribute), new)
        self.assertEqual(getattr(self.loaded_variable(CAPEX_VARID, 2), attribute), separate)

        self.assertIsNot(response.get(row_id('single-input-header', 'header', CAPEX, 'dsa'), 'children'), NOT_UPDATED)
        self.assertIsNot(response.get(row_id('input-group-config-update-trigger', 'trigger', CAPEX, 'dsa'), 'data'), NOT_UPDATED)

        revised = self.revised(before)
        self.assertEqual(revised['projects'], {(self.project_id,)})
        self.assertIn((lproj.table_config.id,), revised['component_configs'])
        self.assertEqual(self.stale_marks(t0), {(x, 'dsa') for x in self.group})

    def test_lower_saved(self):
        # An interval has only the one bound: its confidence
        self.assertEqual(self.stored_variable(CAPEX_VARID).dsa_bounds_type, 'interval')
        self._check_saved('bound-lower', 'dsa_lower')

    def test_upper_saved(self):
        # Relative bounds have both inputs
        self.dispatch(row_id('input-dropdown', 'dsaboundtype', CAPEX, 'dsa'), 'relative', self.components)
        self.components = self.page(('dsa', None))
        self._check_saved('bound-upper', 'dsa_upper')

    def test_unchanged_makes_no_update(self):
        before = self.database_state()
        response = self.dispatch(
            row_id('single-input-config', 'bound-lower', CAPEX, 'dsa'), self.stored_variable(CAPEX_VARID).dsa_lower,
            self.components,
        )
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

class TestDsaBoundType(_SharedAndSeparate):
    """`dsaboundtype`: the kind of DSA bound"""
    varid = CAPEX_VARID

    def test_type_saved_and_bounds_recalculated(self):
        components = self.page(('dsa', None))
        trigger = row_id('input-dropdown', 'dsaboundtype', CAPEX, 'dsa')
        dropdown = next(x for x in components if x.id == trigger)
        options = [x['value'] if isinstance(x, dict) else x for x in dropdown.options]
        new_type = next(x for x in options if x != dropdown.value)

        expected = self.stored_variable(CAPEX_VARID)
        expected.dsa_bounds_type = new_type
        lower, upper = expected.distribution.dsa_auto_values(expected)
        t0 = self.now()

        response = self.dispatch(trigger, new_type, components)

        for mm_index in range(2):
            var = self.loaded_variable(CAPEX_VARID, mm_index)
            self.assertEqual((var.dsa_bounds_type, var.dsa_lower, var.dsa_upper), (new_type, lower, upper))
        self.assertEqual(self.loaded_variable(CAPEX_VARID, 2).dsa_bounds_type, dropdown.value)

        # The bound inputs on the page are given the new bounds (an interval has no upper input; the bounds container
        # is drawn again for the new type by another callback)
        component_ids = [x.id for x in components]
        for purpose, value in (('bound-lower', lower), ('bound-upper', upper)):
            bound_id = row_id('single-input-config', purpose, CAPEX, 'dsa')
            expected = value if bound_id in component_ids else NOT_UPDATED
            self.assertEqual(response.get(bound_id, 'value'), expected, purpose)
        self.assertIsNot(response.get(row_id('single-input-header', 'header', CAPEX, 'dsa'), 'children'), NOT_UPDATED)
        data = response.get(row_id('input-group-config-update-trigger', 'trigger', CAPEX, 'dsa'), 'data')
        self.assertEqual(json.loads(data)['message'], 'dsa_bounds_modified')

        self.assertEqual(self.stale_marks(t0), {(x, 'dsa') for x in self.group})

class TestDsaActive(_SharedAndSeparate):
    """`dsa-active`: selecting a variable for the DSA"""
    varid = CAPEX_VARID

    def test_selection_synced(self):
        components = self.page(('dsa', None))
        selected = self.stored_variable(CAPEX_VARID).dsa_selected
        t0 = self.now()

        response = self.dispatch(row_id('input-toggle', 'dsa-active', CAPEX, 'dsa'), not selected, components)

        # Synced onto the separate instance, so that a DSA of the project varies the same variables
        for mm_index in range(self.n_metamodels):
            self.assertEqual(self.loaded_variable(CAPEX_VARID, mm_index).dsa_selected, not selected, mm_index)
        self.assertEqual(self.stale_marks(t0), {(x, 'dsa') for x in self.metamodel_ids})

        data = response.get(row_id('input-group-config-update-trigger', 'trigger', CAPEX, 'dsa'), 'data')
        self.assertEqual(json.loads(data)['message'], 'dsa_selection_status_modified')

    def test_unchanged_makes_no_update(self):
        components = self.page(('dsa', None))
        before = self.database_state()
        response = self.dispatch(
            row_id('input-toggle', 'dsa-active', CAPEX, 'dsa'), self.stored_variable(CAPEX_VARID).dsa_selected, components
        )
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

class TestOptimSettings(_SharedAndSeparate):
    """`bound-lower`, `bound-upper` and `plot-intervals` in the `optim` supersection"""
    varid = WIND_VARID

    def setUp(self):
        super().setUp()
        self.components = self.page(('optim', None))

    def _check_bound(self, purpose: str, attribute: str, new: float):
        old = getattr(self.stored_variable(WIND_VARID), attribute)
        t0 = self.now()

        response = self.dispatch(row_id('single-input-config', purpose, WIND, 'optim'), new, self.components)

        # Saved on the Variable, so shared by its group
        for mm_index in range(2):
            self.assertEqual(getattr(self.loaded_variable(WIND_VARID, mm_index), attribute), new)
        self.assertEqual(getattr(self.loaded_variable(WIND_VARID, 2), attribute), old)

        # Marks the optimisation stale only for the configurations using the Variable
        self.assertEqual(self.stale_marks(t0), {(x, 'optim') for x in self.group})
        self.assertIsNot(response.get(row_id('input-group-config-update-trigger', 'trigger', WIND, 'optim'), 'data'), NOT_UPDATED)
        return response

    def test_lower_saved(self):
        self._check_bound('bound-lower', 'optim_min', 5.)

    def test_upper_saved(self):
        self._check_bound('bound-upper', 'optim_max', 500.)

    def test_emptied_bound_unset(self):
        self._check_bound('bound-lower', 'optim_min', 5.)
        self.dispatch(row_id('single-input-config', 'bound-lower', WIND, 'optim'), None, self.components)

        var = self.loaded_variable(WIND_VARID)
        self.assertIsNone(var.optim_min)
        self.assertEqual(var.get_optim_bounds()[0], var.interface_min)

    def test_unchanged_bound_makes_no_update(self):
        before = self.database_state()
        response = self.dispatch(
            row_id('single-input-config', 'bound-upper', WIND, 'optim'), self.stored_variable(WIND_VARID).optim_max,
            self.components,
        )
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

    def test_plot_intervals_saved(self):
        old = self.stored_variable(WIND_VARID).optim_plot_intervals
        t0 = self.now()

        response = self.dispatch(row_id('single-input-config', 'plot-intervals', WIND, 'optim'), old + 3, self.components)

        for mm_index in range(2):
            self.assertEqual(self.loaded_variable(WIND_VARID, mm_index).optim_plot_intervals, old + 3)
        self.assertEqual(self.loaded_variable(WIND_VARID, 2).optim_plot_intervals, old)

        # The resolution only affects the marginal plot: nothing is stale, and no input group is signalled
        self.assertEqual(self.stale_marks(t0), set())
        self.assertFalse(response.updated)

    def test_emptied_plot_intervals_makes_no_update(self):
        before = self.database_state()
        response = self.dispatch(row_id('single-input-config', 'plot-intervals', WIND, 'optim'), None, self.components)
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

TestDsaBoundsCached = cached_variant(TestDsaBounds)
TestDsaBoundTypeCached = cached_variant(TestDsaBoundType)
TestDsaActiveCached = cached_variant(TestDsaActive)
TestOptimSettingsCached = cached_variant(TestOptimSettings)
