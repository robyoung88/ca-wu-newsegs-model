"""
Tests of the group editor of an input on the site configuration page (`components.group_editor`): moving configurations
between groups, editing the values of the groups other than the focussed one, and the editor itself.
"""
from dash import html

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db_staleness import PROCESSES
from newsegsmodelapp.components.group_editor import (
    NEW_VARIABLE,
    create_group_editor_contents,
    group_value_input_id,
    move_metamodels_to_group,
)
from newsegsmodelapp.components.input_components import get_variable_groups

from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import NOT_UPDATED, iter_components, variable_id

SECTION, KEY = 'gen_input', 'wind_capacity'
VARID = f'{SECTION}.{KEY}.0'
CAPEX_SECTION, CAPEX_KEY = 'gen_costs', 'wind_capex_per_kw'
CAPEX_VARID = f'{CAPEX_SECTION}.{CAPEX_KEY}.0'

def row(type_: str, purpose: str, section: str = SECTION, key: str = KEY) -> dict:
    return variable_id(type_, purpose, section, key)

def texts(children) -> list[str]:
    """The strings in a layout, as Dash serialises it in a response, or as components"""
    out = []
    for c in children if isinstance(children, list) else [children]:
        if isinstance(c, str):
            out.append(c)
        elif isinstance(c, dict):
            out.extend(texts(c.get('props', {}).get('children')))
        elif c is not None and not isinstance(c, (int, float)):
            out.extend(texts(getattr(c, 'children', None)))
    return out

class _GroupEditorCase(InputChangeTestCase):
    """Three configurations, which share every variable"""
    n_metamodels = 3

    def sharing(self, varid: str = VARID) -> list[tuple[int, ...]]:
        """The configurations sharing each Variable of the variable, from 1"""
        lproj = self.reader.get_lightweight_project(self.project_id)
        return [tuple(i + 1 for i in x.metamodel_indices) for x in get_variable_groups(lproj, varid) if x.var_uid]

    def value(self, mm_index: int, varid: str = VARID):
        return self.reader.variable_provider.get_lightweight_variable(self.variable_uid(varid, mm_index)).raw_parameter_0

    def page_with_editor(self, section: str = SECTION, varid: str = VARID) -> list:
        """The page of the section, with the editor of the variable open"""
        editor = create_group_editor_contents(varid, self.project_id, self.provider)
        return self.page(('deterministic', section)) + [
            x for x in iter_components(editor) if isinstance(getattr(x, 'id', None), dict)
        ]

    def move(self, mm_index, target, section: str = SECTION, key: str = KEY):
        return self.dispatch(
            row('group-move-request', 'move', section, key), {'mm_index': mm_index, 'target': target},
            self.page_with_editor(section, f'{section}.{key}.0'),
        )

class TestMoveMetamodelsToGroup(_GroupEditorCase):
    """`move_metamodels_to_group`"""

    def call(self, mm_indices, target, varid: str = VARID):
        lproj = self.provider.get_lightweight_project(self.project_id)
        return move_metamodels_to_group(self.provider, lproj, varid, mm_indices, target)

    def test_to_another_group(self):
        separate = self.make_independent(2, VARID)
        t0 = self.now()
        before = self.revisions()

        moves = self.call([1], separate)

        self.assertEqual(self.sharing(), [(1,), (2, 3)])
        self.assertEqual(self.loaded_variable(VARID, 1).id, separate)
        self.assertEqual((moves.moved, moves.removed, moves.created), ([1], [], []))
        # Both Variables have the same values, so nothing is stale; only the moved configuration is revised
        self.assertEqual(self.stale_marks(t0), set())
        self.assertEqual(self.revised(before)['metamodels'], {(self.metamodel_ids[1],)})

    def test_to_new_value(self):
        moves = self.call([1], NEW_VARIABLE)

        self.assertEqual(self.sharing(), [(1, 3), (2,)])
        self.assertEqual(moves.created, [self.variable_uid(VARID, 1)])
        self.assertEqual(self.value(1), self.value(0))
        self.assertIn((self.project_id, moves.created[0]), self._rows(tbls.project_variables))

    def test_alone_to_new_value_changes_nothing(self):
        self.make_independent(2, VARID)
        before = self.database_state()
        moves = self.call([2], NEW_VARIABLE)
        self.assertEqual(moves.moved, [])
        self.assertNothingChanged(before)

    def test_last_member_removes_variable(self):
        separate = self.make_independent(2, VARID)
        moves = self.call([2], self.variable_uid(VARID, 0))

        self.assertEqual(self.sharing(), [(1, 2, 3)])
        self.assertEqual(moves.removed, [separate])
        self.assertNotIn((separate,), self._rows(tbls.variable_configs))
        self.assertFalse(any(k[1] == separate for k in self._rows(tbls.project_variables)))

    def test_changed_value_marks_moved_configuration_stale(self):
        separate = self.make_independent(2, VARID)
        self.dispatch(
            group_value_input_id(VARID, separate), 99., self.page_with_editor()
        )
        t0 = self.now()

        self.call([0], separate)

        self.assertEqual(self.stale_marks(t0), {(self.metamodel_ids[0], p) for p in PROCESSES})

    def test_all_as_one_operation(self):
        first = self.variable_uid(VARID, 0)
        second = self.make_independent(1, VARID)
        third = self.make_independent(2, VARID)
        before = self.revisions()

        moves = self.call([0, 1, 2], second)

        self.assertEqual(self.sharing(), [(1, 2, 3)])
        self.assertEqual(sorted(moves.removed), sorted([first, third]))
        self.assertEqual(moves.moved, [0, 2])
        # The project is revised once
        project_revision = lambda x: x['projects'][(self.project_id,)][0]
        self.assertEqual(project_revision(self.revisions()), project_revision(before) + 1)

    def test_invalid_targets_change_nothing(self):
        before = self.database_state()
        for indices, target in (([1], 'v-not-a-variable'), ([5], NEW_VARIABLE), ([-1], NEW_VARIABLE)):
            with self.subTest(indices = indices, target = target):
                with self.assertRaises(ValueError):
                    self.call(indices, target)
        # A Variable of another variable
        with self.assertRaises(ValueError):
            self.call([1], self.variable_uid(CAPEX_VARID, 0))
        self.assertNothingChanged(before)

class TestMoveHandler(_GroupEditorCase):
    """Moves requested through the row's `group-move-request` store"""

    def test_focussed_configuration_updates_main_input(self):
        separate = self.make_independent(2, VARID)
        self.dispatch(group_value_input_id(VARID, separate), 99., self.page_with_editor())

        response = self.move(0, separate)

        self.assertEqual(self.sharing(), [(1, 3), (2,)])
        self.assertEqual(response.get(row('single-input-config', 'parameter'), 'value'), 99.)
        self.assertIsNot(response.get(row('input-group-config-update-trigger', 'trigger'), 'data'), NOT_UPDATED)
        self.assertIsNot(response.get(row('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)
        self.assertIsNot(response.get(row('input-group-editor', 'editor'), 'children'), NOT_UPDATED)

    def test_other_configuration_leaves_main_input(self):
        response = self.move(2, NEW_VARIABLE)

        self.assertEqual(self.sharing(), [(1, 2), (3,)])
        self.assertIs(response.get(row('single-input-config', 'parameter'), 'value'), NOT_UPDATED)
        self.assertIs(response.get(row('input-group-config-update-trigger', 'trigger'), 'data'), NOT_UPDATED)
        self.assertIsNot(response.get(row('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)
        # Only this row's editor is redrawn
        self.assertEqual(
            [x for x in response.updated_ids('children') if x.get('type') == 'input-group-editor'],
            [row('input-group-editor', 'editor')],
        )

    def test_use_for_all(self):
        self.make_independent(1, VARID)
        third = self.make_independent(2, VARID)
        self.move('all', third)
        self.assertEqual(self.sharing(), [(1, 2, 3)])
        self.assertEqual(self.variable_uid(VARID, 0), third)

    def test_stale_target_changes_nothing(self):
        before = self.database_state()
        response = self.move(1, 'v-removed-in-another-tab')
        self.assertNothingChanged(before)
        # The editor is drawn again, as the project now is
        self.assertIsNot(response.get(row('input-group-editor', 'editor'), 'children'), NOT_UPDATED)
        self.assertIs(response.get(row('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)

    def test_selection_without_move_makes_no_update(self):
        response = self.dispatch(row('group-move-request', 'move'), None, self.page_with_editor())
        self.assertFalse(response.updated)

class TestGroupValues(_GroupEditorCase):
    """Values of the groups other than the focussed one, edited in the editor"""

    def test_saved_without_changing_focus(self):
        separate = self.make_independent(2, VARID)
        focussed_value = self.value(0)
        t0 = self.now()
        before = self.revisions()

        response = self.dispatch(group_value_input_id(VARID, separate), 12.5, self.page_with_editor())

        self.assertEqual(self.value(2), 12.5)
        self.assertEqual(self.value(0), focussed_value)
        self.assertIs(response.get(row('single-input-config', 'parameter'), 'value'), NOT_UPDATED)
        self.assertIsNot(response.get(row('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)

        # Only the configuration using the Variable is stale and revised
        marks = self.stale_marks(t0)
        self.assertTrue(marks)
        self.assertEqual({x[0] for x in marks}, {self.metamodel_ids[2]})
        self.assertEqual(self.revised(before)['variable_configs'], {(separate,)})

    def test_shared_group_marks_all_its_configurations(self):
        # The second and third configurations share a Variable apart from the focussed first
        self.make_independent(0, VARID)
        group = self.variable_uid(VARID, 1)
        t0 = self.now()
        self.dispatch(group_value_input_id(VARID, group), 12.5, self.page_with_editor())
        self.assertEqual({x[0] for x in self.stale_marks(t0)}, set(self.metamodel_ids[1:]))

    def test_rejected_value_restores_input(self):
        separate = self.make_independent(2, CAPEX_VARID)
        saved = self.value(2, CAPEX_VARID)
        before = self.database_state()

        response = self.dispatch(
            group_value_input_id(CAPEX_VARID, separate), -5, self.page_with_editor(CAPEX_SECTION, CAPEX_VARID)
        )

        self.assertNothingChanged(before)
        editor = response.get(row('input-group-editor', 'editor', CAPEX_SECTION, CAPEX_KEY), 'children')
        values = [
            x['props'].get('value') for x in _walk(editor)
            if isinstance(x, dict) and isinstance(x.get('props', {}).get('id'), dict)
            and x['props']['id'].get('var_uid') == separate
        ]
        self.assertEqual(values, [saved])

    def test_stale_variable_changes_nothing(self):
        separate = self.make_independent(2, VARID)
        page = self.page_with_editor()
        # Another tab moves the configuration back, which removes the Variable
        lproj = self.provider.get_lightweight_project(self.project_id)
        move_metamodels_to_group(self.provider, lproj, VARID, [2], self.variable_uid(VARID, 0))
        before = self.database_state()

        response = self.dispatch(group_value_input_id(VARID, separate), 12.5, page)

        self.assertNothingChanged(before)
        self.assertIs(response.get(row('variable-summary-refresh-trigger', 'trigger'), 'data'), NOT_UPDATED)

def _walk(layout):
    if isinstance(layout, list):
        for x in layout:
            yield from _walk(x)
    elif isinstance(layout, dict):
        yield layout
        yield from _walk(layout.get('props', {}).get('children'))

class TestEditor(_GroupEditorCase):
    """The editor and its row"""

    def editor(self):
        return create_group_editor_contents(VARID, self.project_id, self.provider)[0]

    def rows(self):
        return [x for x in iter_components(self.editor()) if 'group-editor-row' in (getattr(x, 'className', '') or '')]

    def test_rows(self):
        separate = self.make_independent(1, VARID)
        rows = self.rows()

        # A row for each group, by lowest configuration, then a new value
        self.assertEqual(
            [x.to_plotly_json()['props']['data-var-uid'] for x in rows],
            [self.variable_uid(VARID, 0), separate, NEW_VARIABLE],
        )
        icons = lambda r: [x.to_plotly_json()['props']['data-mm-index'] for x in iter_components(r) if isinstance(x, html.Button) and 'group-editor-icon' in x.className]
        self.assertEqual([icons(x) for x in rows], [['0', '2'], ['1'], []])

        # The focussed group is edited in the main input; the others have an input
        self.assertIn('(edit above)', ''.join(texts(rows[0])))
        inputs = [x.id for x in iter_components(rows) if isinstance(getattr(x, 'id', None), dict)]
        self.assertEqual(inputs, [group_value_input_id(VARID, separate)])

        # The focussed configuration is ringed
        focussed = [x for x in iter_components(rows) if isinstance(x, html.Button) and 'focussed' in x.className]
        self.assertEqual([x.to_plotly_json()['props']['data-mm-index'] for x in focussed], ['0'])

    def test_use_for_all_only_with_several_groups(self):
        has_all = lambda: any(isinstance(x, html.Button) and 'group-editor-all' in x.className for x in iter_components(self.rows()))
        self.assertFalse(has_all())
        self.make_independent(1, VARID)
        self.assertTrue(has_all())

    def test_buttons_are_labelled(self):
        self.make_independent(1, VARID)
        for x in iter_components(self.rows()):
            if isinstance(x, html.Button):
                self.assertTrue(x.to_plotly_json()['props'].get('aria-label'), x.className)

    def test_opening_row_builds_editor(self):
        response = self.dispatch(row('input-summary', 'group-editor-toggle'), 1, self.page(('deterministic', SECTION)))
        editor = response.get(row('input-group-editor', 'editor'), 'children')
        self.assertIn('New Variable', texts(editor))

    def test_single_configuration_has_no_editor(self):
        for mm_index in (2, 1):
            self.remove_configuration(mm_index)
        types = {x.id['type'] for x in self.page(('deterministic', SECTION))}
        self.assertNotIn('input-summary', types)
        self.assertNotIn('group-move-request', types)

TestMoveMetamodelsToGroupCached = cached_variant(TestMoveMetamodelsToGroup)
TestMoveHandlerCached = cached_variant(TestMoveHandler)
TestGroupValuesCached = cached_variant(TestGroupValues)
TestEditorCached = cached_variant(TestEditor)
