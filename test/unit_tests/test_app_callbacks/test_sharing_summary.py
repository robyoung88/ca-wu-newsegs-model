"""
Tests of how the site configuration page shows the sharing of each input across configurations: the groups of
configurations, the summary line under each input, the label of each card, and the callbacks which redraw them.
"""
from types import SimpleNamespace
import unittest
from unittest import mock

from dash import html
import numpy as np

from newsegsmodelapp.components.input_components import (
    VariableGroup,
    count_differing_variables,
    create_variable_sharing_summary_contents,
    get_variable_groups,
)

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, dispatch_callback, get_callback_spec, iter_components, variable_id

SECTION, KEY = 'gen_input', 'wind_capacity'
VARID = f'{SECTION}.{KEY}.0'
CAPEX_SECTION, CAPEX_KEY = 'gen_costs', 'wind_capex_per_kw'

def render(children) -> str:
    """Text of a summary, with configuration icons as (N), the link icon as (link), and the focussed group in [ ]"""
    out = []
    for c in children if isinstance(children, list) else [children]:
        if isinstance(c, str):
            out.append(c)
            continue
        # A component, or a component as Dash serialises it in a response
        if isinstance(c, dict):
            kind, props = c['type'], c['props']
        else:
            kind, props = type(c).__name__, {'className': getattr(c, 'className', None), 'children': getattr(c, 'children', None)}
        if kind == 'I':
            classes = props['className'].split()
            number = next((x[3] for x in classes if x.startswith('bi-') and x.endswith('-circle-fill')), None)
            out.append(f'({number})' if number else '(link)')
        elif kind == 'Span':
            text = render(props.get('children'))
            out.append(f'[{text}]' if 'focussed' in (props.get('className') or '') else text)
    return ''.join(out)

def fake_project(variables_by_config: list[dict[str, str]], focussed: int = 0):
    """A lightweight project, as far as the sharing functions use one: its configurations' variable instances, by id"""
    return SimpleNamespace(
        metamodels = [SimpleNamespace(variables = x) for x in variables_by_config],
        focussed_metamodel_index = focussed,
    )

def fake_variables(**values) -> dict:
    return {uid: SimpleNamespace(id = uid, raw_parameter_0 = v) for uid, v in values.items()}

class TestSummaryFormatting(unittest.TestCase):
    """`create_variable_sharing_summary_contents`"""

    def summary(self, uids: list[str | None], values: dict, focussed: int = 0) -> str:
        proj = fake_project([{VARID: x} if x else {} for x in uids], focussed)
        return render(create_variable_sharing_summary_contents(proj, VARID, fake_variables(**values)))

    def test_single_configuration_shows_nothing(self):
        self.assertEqual(self.summary(['a'], {'a': 6.5}), '')

    def test_all_shared_shows_link_only(self):
        self.assertEqual(self.summary(['a'] * 4, {'a': 6.5}), '(link)')

    def test_groups_with_ranges(self):
        # Three or more consecutive configurations are shortened; two are not
        self.assertEqual(
            self.summary(['a', 'a', 'b', 'c', 'c', 'c', 'c'], {'a': 6.5, 'b': 8, 'c': 12}),
            '[(1)(2) 6.5] · (3) 8 · (4)–(7) 12',
        )

    def test_non_consecutive_sharing(self):
        self.assertEqual(
            self.summary(['a', 'b', 'a', 'b', 'a'], {'a': 6.5, 'b': 8}),
            '[(1)(3)(5) 6.5] · (2)(4) 8',
        )

    def test_focussed_group_emphasised_and_order_kept(self):
        values = {'a': 6.5, 'b': 8, 'c': 12}
        uids = ['a', 'b', 'b', 'c']
        self.assertEqual(self.summary(uids, values, focussed = 0), '[(1) 6.5] · (2)(3) 8 · (4) 12')
        self.assertEqual(self.summary(uids, values, focussed = 2), '(1) 6.5 · [(2)(3) 8] · (4) 12')

    def test_equal_values_of_separate_variables(self):
        self.assertEqual(self.summary(['a', 'a', 'b'], {'a': 6.5, 'b': 6.5}), '[(1)(2) 6.5] · (3) 6.5')

    def test_missing_variable(self):
        self.assertEqual(self.summary(['a', 'a', 'a', 'a', None], {'a': 6.5}), '[(1)–(4) 6.5] · (5) –')

    def test_vector_variable(self):
        self.assertEqual(
            self.summary(['a', 'b'], {'a': np.array([1., 2., 3.]), 'b': np.array([1., 2., 4.])}),
            '[(1) 3 values] · (2) 3 values',
        )

    def test_vector_read_from_database(self):
        # Arrays are lists when read from the database; a single value is shown as a number
        self.assertEqual(
            self.summary(['a', 'b'], {'a': [1., 2., 3.], 'b': [30.]}),
            '[(1) 3 values] · (2) 30',
        )

    def test_number_format(self):
        self.assertEqual(self.summary(['a', 'b'], {'a': 5400., 'b': 0.035}), '[(1) 5,400] · (2) 0.035')

class TestCardLabelCount(unittest.TestCase):
    """`count_differing_variables`"""

    def test_counts_variables_with_several_groups(self):
        proj = fake_project([
            {'s.a.0': 'a1', 's.b.0': 'b1', 's.c.0': 'c1'},
            {'s.a.0': 'a1', 's.b.0': 'b2', 's.c.0': 'c1'},
            {'s.a.0': 'a1', 's.b.0': 'b1'},
        ])
        # b has two instances, c is missing from a configuration
        self.assertEqual(count_differing_variables(proj, ['s.a.0', 's.b.0', 's.c.0']), 2)
        self.assertEqual(count_differing_variables(proj, ['s.a.0']), 0)

class TestVariableGroups(InputChangeTestCase):
    """`get_variable_groups`, on a project with four configurations"""
    n_metamodels = 4

    def groups(self) -> list[VariableGroup]:
        return get_variable_groups(self.reader.get_lightweight_project(self.project_id), VARID)

    def share(self, mm_index: int, var_uid: str):
        """Give a configuration an existing instance of the variable"""
        lproj = self.reader.get_lightweight_project(self.project_id)
        lmm = lproj.metamodels[mm_index]
        lmm.variables[VARID] = var_uid
        self.reader.metamodel_provider.refresh_metamodel_variable_junction(
            lmm, [self.reader.variable_provider.get_lightweight_variable(var_uid)]
        )

    def test_all_shared(self):
        self.assertEqual(self.groups(), [VariableGroup(self.variable_uid(VARID), (0, 1, 2, 3))])

    def test_all_independent(self):
        uids = [self.variable_uid(VARID)] + [self.make_independent(x, VARID) for x in (1, 2, 3)]
        self.assertEqual(self.groups(), [VariableGroup(uid, (idx,)) for idx, uid in enumerate(uids)])

    def test_non_consecutive_groups(self):
        first = self.variable_uid(VARID)
        second = self.make_independent(1, VARID)
        self.share(3, second)
        self.assertEqual(self.groups(), [VariableGroup(first, (0, 2)), VariableGroup(second, (1, 3))])

    def test_order_independent_of_focus(self):
        self.make_independent(2, VARID)
        before = self.groups()
        self.set_focus(2)
        self.assertEqual(self.groups(), before)

    def test_missing_variable(self):
        lproj = self.reader.get_lightweight_project(self.project_id)
        del lproj.metamodels[1].variables[VARID]
        self.assertEqual(
            get_variable_groups(lproj, VARID),
            [VariableGroup(self.variable_uid(VARID), (0, 2, 3)), VariableGroup(None, (1,))],
        )

def summary_id(section: str = SECTION, key: str = KEY) -> dict:
    return variable_id('input-action-button', 'variable-status-toggle', section, key)

def refresh_id(section: str = SECTION, key: str = KEY) -> dict:
    return variable_id('variable-summary-refresh-trigger', 'trigger', section, key)

def label_id(section: str = SECTION) -> dict:
    return {'type': 'input-card-label', 'supersection': 'deterministic', 'section': section}

class TestSharingCallbacks(InputChangeTestCase):
    """Rendering, and the callbacks which redraw the summary and the card label, with three configurations"""
    n_metamodels = 3

    def stored_value(self, mm_index: int = 0):
        """The value shown in the input of the wind capacity, as stored for a configuration"""
        return self.reader.variable_provider.get_lightweight_variable(self.variable_uid(VARID, mm_index)).raw_parameter_0

    def page_of(self, section: str = SECTION) -> list:
        return self.page(('deterministic', section)) + [html.Span(id = label_id(section))]

    def summary_of(self, components, section: str = SECTION, key: str = KEY) -> str:
        return render(next(x for x in components if x.id == summary_id(section, key)).children)

    def redraw_summary(self, components, section: str = SECTION, key: str = KEY) -> str:
        spec = get_callback_spec(self.client, 'input-action-button', 'children')
        response = dispatch_callback(
            self.client, spec, refresh_id(section, key), 1, components, stores = {'active-project-id': self.project_id}
        )
        return render(response.get(summary_id(section, key), 'children'))

    def redraw_label(self, components, section: str = SECTION):
        spec = get_callback_spec(self.client, 'input-card-label', 'children')
        response = dispatch_callback(
            self.client, spec, refresh_id(section), 1, components, stores = {'active-project-id': self.project_id}
        )
        return response.get(label_id(section), 'children')

    def test_rendered_summary(self):
        self.assertEqual(self.summary_of(self.page_of()), '(link)')
        self.make_independent(2, VARID)
        value = self.stored_value()
        self.assertEqual(self.summary_of(self.page_of()), f'[(1)(2) {value:,.6g}] · (3) {value:,.6g}')

    def test_single_configuration_renders_nothing(self):
        for mm_index in (2, 1):
            self.remove_configuration(mm_index)
        self.assertEqual(self.summary_of(self.page_of()), '')

    def test_hydration_fetches_variables_once(self):
        self.make_independent(2, VARID)
        provider = self.provider.variable_provider
        with mock.patch.object(provider, 'get_lightweight_variable', wraps = provider.get_lightweight_variable) as fetch:
            self.page_of()
        self.assertEqual(fetch.call_count, 1)

    def test_saved_value_signals_refresh_and_redraws(self):
        self.make_independent(2, VARID)
        components = self.page_of()
        response = self.dispatch(variable_id('single-input-config', 'parameter', SECTION, KEY), 12.5, components)
        self.assertIsNot(response.get(refresh_id(), 'data'), NOT_UPDATED)

        other = self.stored_value(2)
        self.assertEqual(self.redraw_summary(components), f'[(1)(2) 12.5] · (3) {other:,.6g}')

    def test_rejected_value_does_not_signal_refresh(self):
        components = self.page_of(CAPEX_SECTION)
        response = self.dispatch(
            variable_id('single-input-config', 'parameter', CAPEX_SECTION, CAPEX_KEY), -5, components
        )
        self.assertIs(response.get(refresh_id(CAPEX_SECTION, CAPEX_KEY), 'data'), NOT_UPDATED)

    def test_cycling_sharing_signals_refresh_and_redraws(self):
        components = self.page_of()
        response = self.dispatch(summary_id(), 1, components)
        self.assertIsNot(response.get(refresh_id(), 'data'), NOT_UPDATED)

        value = f'{self.stored_value():,.6g}'
        self.assertEqual(self.redraw_summary(components), f'[(1) {value}] · (2)(3) {value}')
        self.assertEqual(self.redraw_label(components), '1 differ')

    def test_card_label(self):
        components = self.page_of()
        self.assertIsNone(self.redraw_label(components))

        self.make_independent(1, VARID)
        self.make_independent(2, f'{SECTION}.pv_capacity.0')
        self.assertEqual(self.redraw_label(components), '2 differ')

    def test_card_label_outside_collapsible_inputs(self):
        from newsegsmodelapp.components.layouts.input_card import create_input_card
        card = create_input_card('deterministic', SECTION, ['Generation'])
        details = next(x for x in iter_components(card) if isinstance(x, html.Details))
        self.assertIn(label_id(), [getattr(x, 'id', None) for x in iter_components(card)])
        self.assertNotIn(label_id(), [getattr(x, 'id', None) for x in iter_components(details)])

TestVariableGroupsCached = cached_variant(TestVariableGroups)
TestSharingCallbacksCached = cached_variant(TestSharingCallbacks)
