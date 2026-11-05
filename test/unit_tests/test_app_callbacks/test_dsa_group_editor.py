"""
Tests of the groups of an input on the DSA page (`components.dsa_group_editor`): the summary line, the editor of every
group's value, bound type and bounds, and keeping the DSA and optimisation rows of the focussed configuration in sync.
"""
from types import SimpleNamespace
import unittest

from newsegsmodelapp.components.dsa_group_editor import (
    count_variables_with_different_bounds,
    create_dsa_group_editor_contents,
    create_dsa_sharing_summary_contents,
    dsa_bounds_differ,
    set_dsa_bound_type,
)
from newsegsmodelapp.components.group_editor import NEW_VARIABLE, group_value_input_id, move_metamodels_to_group

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, iter_components, variable_id
from .test_sharing_summary import render

# Selected for the DSA, with an interval bound; and the generation capacity, selectable for the optimisation
CAPEX = ('gen_costs', 'wind_capex_per_kw')
CAPEX_VARID = 'gen_costs.wind_capex_per_kw.0'
WIND = ('gen_input', 'wind_capacity')
WIND_VARID = 'gen_input.wind_capacity.0'

def row_id(type_: str, purpose: str, row: tuple[str, str], supersection: str = 'dsa', **kwargs) -> dict:
    return variable_id(type_, purpose, *row, supersection = supersection, **kwargs)

def fake(type_: str, lower, upper, value = 1.) -> SimpleNamespace:
    return SimpleNamespace(dsa_bounds_type = type_, dsa_lower = lower, dsa_upper = upper, last_deterministic_value = value)

class TestBoundsDiffer(unittest.TestCase):
    """`dsa_bounds_differ`: bound types and settings, not the bounds calculated from them"""

    def test_same_relative_bounds_on_different_values(self):
        self.assertFalse(dsa_bounds_differ([fake('relative', -0.1, 0.1, 6.5), fake('relative', -0.1, 0.1, 8.)]))

    def test_different_types(self):
        self.assertTrue(dsa_bounds_differ([fake('relative', -0.1, 0.1), fake('absolute', -0.1, 0.1)]))

    def test_different_settings(self):
        self.assertTrue(dsa_bounds_differ([fake('relative', -0.1, 0.1), fake('relative', -0.2, 0.1)]))

class _DsaCase(InputChangeTestCase):
    """Three configurations; the third has a separate Variable of the variable under test"""
    n_metamodels = 3
    varid = CAPEX_VARID
    row = CAPEX

    def setUp(self):
        super().setUp()
        self.separate = self.make_independent(2, self.varid)

    def full(self, var_uid: str):
        return self.reader.variable_provider.get_full_lightweight_variable(var_uid)

    def page_of(self):
        """The DSA and optimisation pages, with the rows' editors open"""
        return self.page(('dsa', None), ('optim', None))

    def assertFocussedRowsUnchanged(self, response):
        for type_ in ('single-input-config', 'input-toggle'):
            for id_ in response.updated_ids('value'):
                if id_.get('type') == type_:
                    self.fail(f'{id_} was updated')
        self.assertFalse(response.updated_ids('className'))

class TestGroupDsaSettings(_DsaCase):
    """The DSA settings of a group other than the focussed configuration's, edited in the editor"""

    def test_bound_saved_for_its_group_only(self):
        focussed_lower = self.full(self.variable_uid(self.varid)).dsa_lower
        t0 = self.now()
        response = self.dispatch(
            group_value_input_id(self.varid, self.separate, 'dsa', 'group-dsa-bound-lower'), 0.5, self.page_of()
        )

        self.assertEqual(self.full(self.separate).dsa_lower, 0.5)
        self.assertEqual(self.full(self.variable_uid(self.varid)).dsa_lower, focussed_lower)
        self.assertEqual(self.stale_marks(t0), {(self.metamodel_ids[2], 'dsa')})
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger', self.row), 'data'), NOT_UPDATED)
        self.assertIsNot(response.get(row_id('input-group-editor', 'editor', self.row), 'children'), NOT_UPDATED)
        self.assertFocussedRowsUnchanged(response)

    def test_bound_type_recalculates_bounds(self):
        expected = self.reader.variable_provider.get_variable(self.separate)
        expected.dsa_bounds_type = 'relative'
        lower, upper = expected.distribution.dsa_auto_values(expected)

        response = self.dispatch(
            group_value_input_id(self.varid, self.separate, 'dsa', 'group-dsaboundtype'), 'relative', self.page_of()
        )

        var = self.full(self.separate)
        self.assertEqual((var.dsa_bounds_type, var.dsa_lower, var.dsa_upper), ('relative', lower, upper))
        self.assertEqual(self.full(self.variable_uid(self.varid)).dsa_bounds_type, 'interval')
        self.assertFocussedRowsUnchanged(response)

    def test_value_leaves_focussed_rows(self):
        t0 = self.now()
        response = self.dispatch(group_value_input_id(self.varid, self.separate, 'dsa'), 4321., self.page_of())
        self.assertEqual(self.full(self.separate).raw_parameter_0, 4321.)
        self.assertEqual({x[0] for x in self.stale_marks(t0)}, {self.metamodel_ids[2]})
        self.assertFocussedRowsUnchanged(response)

    def test_stale_variable_changes_nothing(self):
        page = self.page_of()
        lproj = self.provider.get_lightweight_project(self.project_id)
        move_metamodels_to_group(self.provider, lproj, self.varid, [2], self.variable_uid(self.varid))
        before = self.database_state()
        self.dispatch(group_value_input_id(self.varid, self.separate, 'dsa', 'group-dsa-bound-lower'), 0.5, page)
        self.assertNothingChanged(before)

class TestFocussedDsaSettings(_DsaCase):
    """The focussed configuration's DSA settings, through the extracted handlers"""

    def test_bound_marks_its_group_stale_and_redraws_header(self):
        t0 = self.now()
        response = self.dispatch(row_id('single-input-config', 'bound-lower', self.row), 0.5, self.page_of())
        self.assertEqual(self.full(self.variable_uid(self.varid)).dsa_lower, 0.5)
        self.assertEqual(self.stale_marks(t0), {(x, 'dsa') for x in self.metamodel_ids[:2]})
        # The header shows the Variable (it was emptied when given the metamodel)
        header = response.get(row_id('single-input-header', 'header', self.row), 'children')
        self.assertTrue(header)
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger', self.row), 'data'), NOT_UPDATED)

    def test_bound_type_feeds_only_dsa_bounds(self):
        # The optimisation row's bounds share the purposes of the DSA bounds
        response = self.dispatch(row_id('input-dropdown', 'dsaboundtype', self.row), 'relative', self.page_of())
        for id_ in response.updated_ids('value'):
            self.assertEqual(id_['supersection'], 'dsa', id_)

class TestSync(_DsaCase):
    """The focussed configuration's DSA and optimisation rows, which share its Variable"""
    varid = WIND_VARID
    row = WIND

    def test_value_from_dsa_to_optim(self):
        response = self.dispatch(row_id('single-input-config', 'parameter', self.row), 12.5, self.page_of())
        self.assertEqual(response.get(row_id('single-input-config', 'parameter', self.row, 'optim'), 'value'), 12.5)
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger', self.row), 'data'), NOT_UPDATED)

    def test_value_from_optim_to_dsa(self):
        response = self.dispatch(row_id('single-input-config', 'parameter', self.row, 'optim'), 12.5, self.page_of())
        self.assertEqual(response.get(row_id('single-input-config', 'parameter', self.row), 'value'), 12.5)

    def test_value_under_absolute_bounds_refreshes_summary(self):
        lproj = self.provider.get_lightweight_project(self.project_id)
        set_dsa_bound_type(self.provider, lproj, self.provider.variable_provider.get_variable(self.variable_uid(self.varid)), 'absolute')
        response = self.dispatch(row_id('single-input-config', 'parameter', self.row), 12.5, self.page_of())
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger', self.row), 'data'), NOT_UPDATED)

    def test_focussed_move_refreshes_every_field(self):
        # The separate Variable has other DSA and optimisation settings
        lproj = self.provider.get_lightweight_project(self.project_id)
        var = self.provider.variable_provider.get_variable(self.separate)
        set_dsa_bound_type(self.provider, lproj, var, 'absolute')
        var.set_parameters([77.] + list(var.raw_parameters[1:]))
        var.optim_min, var.optim_max, var.optim_plot_intervals = 5., 95., 7
        var.optim_selected = not self.full(self.variable_uid(self.varid)).optim_selected
        var.dsa_selected = not self.full(self.variable_uid(self.varid)).dsa_selected
        self.provider.variable_provider.upsert_variable(var, force = True)
        target = self.full(self.separate)

        response = self.dispatch(row_id('group-move-request', 'move', self.row), {'mm_index': 0, 'target': self.separate}, self.page_of())

        get = lambda type_, purpose, supersection, prop: response.get(row_id(type_, purpose, self.row, supersection), prop)
        # DSA: the value and bounds of the focussed row, the toggle, the header and the trigger (styling and bounds)
        self.assertEqual(get('single-input-config', 'parameter', 'dsa', 'value'), 77.)
        self.assertEqual(get('input-toggle', 'dsa-active', 'dsa', 'value'), target.dsa_selected)
        self.assertIsNot(get('single-input-header', 'header', 'dsa', 'children'), NOT_UPDATED)
        self.assertIsNot(get('input-group-config-update-trigger', 'trigger', 'dsa', 'data'), NOT_UPDATED)
        # The editor is redrawn with the new bound type in the focussed row
        editor = response.get(row_id('input-group-editor', 'editor', self.row), 'children')
        self.assertIn("'value': 'absolute'", str(editor))
        # Optimisation: value, toggle, styling, bounds and N plot
        self.assertEqual(get('single-input-config', 'parameter', 'optim', 'value'), 77.)
        self.assertEqual(get('input-toggle', 'toggle-optim-active', 'optim', 'value'), target.optim_selected)
        self.assertIn('optim-input-single-value-block', get('input-component', 'container', 'optim', 'className'))
        self.assertEqual(get('single-input-config', 'bound-lower', 'optim', 'value'), 5.)
        self.assertEqual(get('single-input-config', 'bound-upper', 'optim', 'value'), 95.)
        self.assertEqual(get('single-input-config', 'plot-intervals', 'optim', 'value'), 7)

    def test_other_configuration_move_leaves_focussed_rows(self):
        response = self.dispatch(row_id('group-move-request', 'move', self.row), {'mm_index': 1, 'target': NEW_VARIABLE}, self.page_of())
        self.assertFocussedRowsUnchanged(response)
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger', self.row), 'data'), NOT_UPDATED)

class TestSummaryAndEditor(_DsaCase):
    """The summary line, the editor, and the count for the run dialog"""

    def summary(self):
        lproj = self.reader.get_lightweight_project(self.project_id)
        uids = {x.variables[self.varid] for x in lproj.metamodels}
        variables = {x.id: x for x in self.reader.variable_provider.get_full_lightweight_variable(list(uids))}
        return render(create_dsa_sharing_summary_contents(lproj, self.varid, variables)), lproj, variables

    def test_summary_shows_values_and_bounds(self):
        text, _, _ = self.summary()
        self.assertEqual(text.count('['), 3)  # the focussed group, and two groups' bounds
        self.assertNotIn('≠ bounds', text)

    def test_summary_marks_different_settings(self):
        lproj = self.provider.get_lightweight_project(self.project_id)
        set_dsa_bound_type(self.provider, lproj, self.provider.variable_provider.get_variable(self.separate), 'relative')
        text, lproj, variables = self.summary()
        self.assertIn('≠ bounds', text)
        self.assertEqual(count_variables_with_different_bounds(lproj, variables), 1)

    def test_one_group_no_summary(self):
        lproj = self.provider.get_lightweight_project(self.project_id)
        move_metamodels_to_group(self.provider, lproj, self.varid, [2], self.variable_uid(self.varid))
        text, lproj, variables = self.summary()
        self.assertEqual(text, '')
        self.assertEqual(count_variables_with_different_bounds(lproj, variables), 0)

    def test_editor_rows(self):
        editor = create_dsa_group_editor_contents(self.varid, self.project_id, self.provider)
        ids = [x.id for x in iter_components(editor) if isinstance(getattr(x, 'id', None), dict)]
        # The focussed row keeps its usual ids; the other group's inputs carry its Variable
        self.assertIn(row_id('single-input-config', 'parameter', self.row), ids)
        self.assertIn(row_id('input-dropdown', 'dsaboundtype', self.row), ids)
        self.assertIn(group_value_input_id(self.varid, self.separate, 'dsa', 'group-dsaboundtype'), ids)
        self.assertNotIn(group_value_input_id(self.varid, self.variable_uid(self.varid), 'dsa'), ids)

    def test_single_configuration_editor_has_focussed_row_only(self):
        for mm_index in (2, 1):
            self.remove_configuration(mm_index)
        editor = create_dsa_group_editor_contents(self.varid, self.project_id, self.provider)
        types = {x.id['type'] for x in iter_components(editor) if isinstance(getattr(x, 'id', None), dict)}
        self.assertIn('single-input-config', types)
        self.assertNotIn('group-value-input', types)
        self.assertNotIn('group-editor-icon', str(editor))

TestGroupDsaSettingsCached = cached_variant(TestGroupDsaSettings)
TestFocussedDsaSettingsCached = cached_variant(TestFocussedDsaSettings)
TestSyncCached = cached_variant(TestSync)
TestSummaryAndEditorCached = cached_variant(TestSummaryAndEditor)
