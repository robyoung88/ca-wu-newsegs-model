"""
Tests of the groups of an input on the PSA page (`components.psa_group_editor`): the summary line, the editor of every
group's parameters, and the refresh of the focussed row when its configuration moves.
"""
from types import SimpleNamespace
import unittest

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.components.group_editor import group_value_input_id, move_metamodels_to_group
from newsegsmodelapp.components.psa_group_editor import (
    _cells,
    _head,
    confidence_interval,
    count_variables_with_different_distributions_or_sds,
    create_psa_group_editor_contents,
    create_psa_sharing_summary_contents,
    mean_and_sd,
)
from newsegsmodelapp.components.variable_dash_component.vdc import create_psa_input_scalar

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, iter_components, variable_id
from .test_sharing_summary import render

# Shown on the PSA page, with a mean and an SD
CAPEX = ('gen_costs', 'wind_capex_per_kw')
CAPEX_VARID = 'gen_costs.wind_capex_per_kw.0'

def row_id(type_: str, purpose: str, row: tuple[str, str] = CAPEX, **kwargs) -> dict:
    return variable_id(type_, purpose, *row, supersection = 'psa', **kwargs)

def fake(distribution = 'normal', mean = 6.5, sd = 0.5, ci = (5.5, 7.5), uid = 'a'):
    return SimpleNamespace(
        id = uid, distribution = distribution, formatter_dp = 1, last_deterministic_value = mean, last_std = sd,
        psa_ci_lower = ci[0] if ci else None, psa_ci_upper = ci[1] if ci else None, psa_show = True,
    )

def fake_project(uids: list[str], focussed: int = 0):
    return SimpleNamespace(
        metamodels = [SimpleNamespace(variables = {CAPEX_VARID: x}) for x in uids], focussed_metamodel_index = focussed,
    )

class TestFormatting(unittest.TestCase):
    """The values of the summary line and the editor"""

    def test_two_parameters(self):
        self.assertEqual(mean_and_sd(fake()), '6.5 ± 0.5')
        self.assertEqual(confidence_interval(fake()), '5.5, 7.5')

    def test_constant(self):
        self.assertEqual(mean_and_sd(fake('constant', 3., None, None)), '3.0')

    def test_missing_sd_and_ci(self):
        self.assertEqual(mean_and_sd(fake(sd = None)), '6.5 ± -')
        self.assertEqual(confidence_interval(fake(ci = None)), '-')

    def test_summary(self):
        variables = {'a': fake(uid = 'a'), 'b': fake(mean = 8., sd = 0.8, uid = 'b')}
        text = render(create_psa_sharing_summary_contents(fake_project(['a', 'a', 'b']), CAPEX_VARID, variables))
        self.assertEqual(text, '[(1)(2) 6.5 ± 0.5] · (3) 8.0 ± 0.8')

    def test_summary_marks_different_distributions(self):
        variables = {'a': fake(uid = 'a'), 'b': fake('beta', uid = 'b')}
        text = render(create_psa_sharing_summary_contents(fake_project(['a', 'b']), CAPEX_VARID, variables))
        self.assertIn('≠ distribution', text)

    def test_no_summary_for_one_group(self):
        self.assertEqual(create_psa_sharing_summary_contents(fake_project(['a', 'a']), CAPEX_VARID, {'a': fake()}), [])

    def test_columns(self):
        labels = lambda head: [x.children for x in head]
        self.assertEqual(labels(_head([fake(), fake()], False)), ['Mean', 'SD', '95% CI', 'Group'])
        self.assertEqual(labels(_head([fake(), fake('beta')], True)), ['Distribution', 'Mean', 'SD', '95% CI', 'Group'])
        self.assertEqual(labels(_head([fake('constant')], False)), ['Value', 'Group'])

    def test_count_of_different_distributions_or_sds(self):
        proj = fake_project(['a', 'b'])
        self.assertEqual(count_variables_with_different_distributions_or_sds(proj, {'a': fake(uid = 'a'), 'b': fake(uid = 'b')}), 0)
        self.assertEqual(count_variables_with_different_distributions_or_sds(proj, {'a': fake(uid = 'a'), 'b': fake(sd = 0.9, uid = 'b')}), 1)
        self.assertEqual(count_variables_with_different_distributions_or_sds(proj, {'a': fake(uid = 'a'), 'b': fake('beta', uid = 'b')}), 1)

class _PsaCase(InputChangeTestCase):
    """Three configurations; the third has a separate Variable of the CAPEX"""
    n_metamodels = 3

    def setUp(self):
        super().setUp()
        self.separate = self.make_independent(2, CAPEX_VARID)

    def full(self, var_uid: str):
        return self.reader.variable_provider.get_full_lightweight_variable(var_uid)

    def page_of(self):
        return self.page(('psa', None))

class TestGroupParameters(_PsaCase):
    """Edits of a group other than the focussed configuration's, to each parameter"""

    def check_saved(self, parameter_index: int, value: float):
        focussed = self.full(self.variable_uid(CAPEX_VARID))
        t0 = self.now()
        before = self.revisions()

        response = self.dispatch(
            group_value_input_id(CAPEX_VARID, self.separate, 'psa', parameter_index = parameter_index), value, self.page_of()
        )

        var = self.full(self.separate)
        self.assertEqual((var.raw_parameter_0, var.raw_parameter_1)[parameter_index], value)
        unchanged = self.full(self.variable_uid(CAPEX_VARID))
        self.assertEqual((unchanged.raw_parameter_0, unchanged.raw_parameter_1), (focussed.raw_parameter_0, focussed.raw_parameter_1))
        # Only the configuration using the Variable is revised and stale
        self.assertEqual(self.revised(before)['variable_configs'], {(self.separate,)})
        self.assertEqual({x[0] for x in self.stale_marks(t0)}, {self.metamodel_ids[2]})
        self.assertIn((self.metamodel_ids[2], 'psa'), self.stale_marks(t0))
        # The summary and editor are redrawn, and the focussed row isn't changed
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)
        self.assertIsNot(response.get(row_id('input-group-editor', 'editor'), 'children'), NOT_UPDATED)
        self.assertFalse([x for x in response.updated_ids('value') if x.get('type') == 'single-input-config'])
        return response

    def test_mean(self):
        self.check_saved(0, 6000.)

    def test_sd(self):
        response = self.check_saved(1, 700.)
        # The editor shows the new confidence interval of the group
        var = self.full(self.separate)
        self.assertIn(confidence_interval(var), str(response.get(row_id('input-group-editor', 'editor'), 'children')))

    def test_rejected_value_restores_input(self):
        saved = self.full(self.separate).raw_parameter_0
        before = self.database_state()
        response = self.dispatch(group_value_input_id(CAPEX_VARID, self.separate, 'psa'), -5, self.page_of())
        self.assertNothingChanged(before)
        editor = str(response.get(row_id('input-group-editor', 'editor'), 'children'))
        self.assertIn(f"'value': {saved}", editor)

    def test_stale_variable_changes_nothing(self):
        page = self.page_of()
        lproj = self.provider.get_lightweight_project(self.project_id)
        move_metamodels_to_group(self.provider, lproj, CAPEX_VARID, [2], self.variable_uid(CAPEX_VARID))
        before = self.database_state()
        self.dispatch(group_value_input_id(CAPEX_VARID, self.separate, 'psa'), 6000., page)
        self.assertNothingChanged(before)

class TestFocussedRow(_PsaCase):
    """The focussed configuration's row"""

    def test_rejected_value_restores_input(self):
        saved = self.full(self.variable_uid(CAPEX_VARID)).raw_parameter_1
        response = self.dispatch(row_id('single-input-config', 'parameter', parameter_index = 1), -5, self.page_of())
        self.assertEqual(response.get(row_id('single-input-config', 'parameter', parameter_index = 1), 'value'), saved)

    def test_edit_refreshes_summary(self):
        response = self.dispatch(row_id('single-input-config', 'parameter', parameter_index = 1), 700., self.page_of())
        self.assertIsNot(response.get(row_id('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)

    def test_focussed_move_refreshes_row(self):
        # The separate Variable has other parameters, set in the editor, and another selection
        for index, value in ((0, 6000.), (1, 900.)):
            self.dispatch(group_value_input_id(CAPEX_VARID, self.separate, 'psa', parameter_index = index), value, self.page_of())
        var = self.provider.variable_provider.get_variable(self.separate)
        var.psa_selected = not self.full(self.variable_uid(CAPEX_VARID)).psa_selected
        self.provider.variable_provider.upsert_variable(var, force = True)

        response = self.dispatch(row_id('group-move-request', 'move'), {'mm_index': 0, 'target': self.separate}, self.page_of())

        self.assertEqual(self.variable_uid(CAPEX_VARID), self.separate)
        self.assertEqual(response.get(row_id('single-input-config', 'parameter'), 'value'), 6000.)
        self.assertEqual(response.get(row_id('single-input-config', 'parameter', parameter_index = 1), 'value'), 900.)
        self.assertEqual(response.get(row_id('input-toggle', 'psa-active'), 'value'), var.psa_selected)
        self.assertIsNot(response.get(row_id('single-input-header', 'header'), 'children'), NOT_UPDATED)
        # The trigger redraws the row's styling; the editor shows the distribution and the new parameters
        self.assertIsNot(response.get(row_id('input-group-config-update-trigger', 'trigger'), 'data'), NOT_UPDATED)
        editor = str(response.get(row_id('input-group-editor', 'editor'), 'children'))
        self.assertIn('Distribution:', editor)
        self.assertIn("'value': 6000", editor)

class TestEditor(_PsaCase):
    """The editor, and the inputs of a constant"""

    def test_rows(self):
        editor = create_psa_group_editor_contents(CAPEX_VARID, self.project_id, self.provider)
        ids = [x.id for x in iter_components(editor) if isinstance(getattr(x, 'id', None), dict)]
        self.assertIn(row_id('single-input-config', 'parameter', parameter_index = 1), ids)
        self.assertIn(group_value_input_id(CAPEX_VARID, self.separate, 'psa', parameter_index = 1), ids)
        # The distribution once, above the rows
        self.assertEqual(str(editor).count('Distribution:'), 1)

    def test_single_configuration_has_focussed_row_only(self):
        for mm_index in (2, 1):
            self.remove_configuration(mm_index)
        editor = create_psa_group_editor_contents(CAPEX_VARID, self.project_id, self.provider)
        types = {x.id['type'] for x in iter_components(editor) if isinstance(getattr(x, 'id', None), dict)}
        self.assertEqual(types, {'single-input-config'})

    def test_constant(self):
        # Hidden on the page by the shipped defaults, but drawn if shown
        lproj = self.reader.get_lightweight_project(self.project_id)
        variables = self.reader.variable_provider.get_full_lightweight_variable(list(lproj.metamodels[0].variables.values()))
        constant = next(x for x in variables if x.distribution in ('constant', 'numeric_constant'))
        varid = f'{constant.interface_section}.{constant.interface_key}.{constant.interface_subindex}'

        cells = _cells(varid, constant, True, False)
        self.assertEqual(len(cells), 1)  # A value, and no confidence interval
        self.assertIn('Value', str(cells))
        self.assertEqual(mean_and_sd(constant).count('±'), 0)
        self.assertTrue(create_psa_input_scalar(constant))

    def test_project_settings_unaffected(self):
        components = self.page(('psa', 'psa-settings'))
        self.assertTrue(any(x.id.get('purpose') == 'psa-settings' for x in components))
        self.assertFalse(any(x.id.get('type') == 'input-summary' for x in components))

TestGroupParametersCached = cached_variant(TestGroupParameters)
TestFocussedRowCached = cached_variant(TestFocussedRow)
TestEditorCached = cached_variant(TestEditor)
