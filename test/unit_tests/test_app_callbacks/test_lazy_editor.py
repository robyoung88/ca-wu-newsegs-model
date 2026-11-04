"""
Tests of rows which build their editors when opened: `create_lazy_input_details`, and the handler of
`group-editor-toggle`, which fills the editor through the content creator registered for its row.

No production row uses these yet, so the rows are made by the tests, in a supersection of their own.
"""
from dataclasses import fields
from unittest import mock

from dash import html

from newsegsmodelapp import registers
from newsegsmodelapp.components.input_components import create_lazy_input_details
from newsegsmodelapp.components.variable_identification import VariableInstanceParameterComponentID

from .base import InputChangeTestCase
from .dash_dispatch import (
    INPUT_CHANGE_OUTPUT, NOT_UPDATED, _matches, get_callback_spec, iter_components, variable_id,
)

SUPERSECTION = 'test-lazy'
SECTION, KEY = 'gen_input', 'wind_capacity'
VARID = f'{SECTION}.{KEY}.0'
OTHER_KEY = 'pv_capacity'

def summary_id(key: str = KEY, **kwargs) -> dict:
    return variable_id('input-summary', 'group-editor-toggle', SECTION, key, supersection = SUPERSECTION, **kwargs)

def editor_id(key: str = KEY, **kwargs) -> dict:
    return variable_id('input-group-editor', 'editor', SECTION, key, supersection = SUPERSECTION, **kwargs)

def lazy_row(key: str = KEY) -> html.Details:
    param_id = VariableInstanceParameterComponentID(type = 'notype', supersection = SUPERSECTION, section = SECTION, key = key)
    return create_lazy_input_details(html.Span(key), param_id)

def page_of(*layout) -> list:
    """The components with dictionary ids in a layout"""
    return [x for x in iter_components(list(layout)) if isinstance(getattr(x, 'id', None), dict)]

class Creator:
    """A content creator which records its calls, and returns a span naming itself and the variable"""
    def __init__(self, name: str):
        self.name = name
        self.calls = []

    def __call__(self, varid, active_project_id, project_provider):
        self.calls.append((varid, active_project_id, project_provider))
        return [html.Span(f'{self.name}:{varid}')]

def span_text(children) -> str:
    """Text of the span returned by a `Creator`, as Dash serialises it"""
    return children[0]['props']['children']

class TestLazyEditor(InputChangeTestCase):
    """`group-editor-toggle` of an `input-summary`"""

    def setUp(self):
        super().setUp()
        self.components = page_of(lazy_row(), lazy_row(OTHER_KEY))

    def _register(self, *model_types: str, section: str = SECTION) -> dict[str, Creator]:
        """Register a creator for each model type, for the duration of the test"""
        creators = {x: Creator(x) for x in model_types}
        patcher = mock.patch.dict(
            registers.INPUT_EDITOR_CONTENT_CREATORS,
            # The register keys every section as 'ALL'
            {(SUPERSECTION, section or 'ALL', x): creator for x, creator in creators.items()},
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        return creators

    def test_opened_row_built(self):
        creator = self._register('default')['default']
        before = self.database_state()

        response = self.dispatch(summary_id(), 1, self.components)

        self.assertEqual(creator.calls, [(VARID, self.project_id, self.provider)])
        self.assertEqual(span_text(response.get(editor_id(), 'children')), f'default:{VARID}')
        # Only the editor is updated
        self.assertEqual(response.updated_ids(), [editor_id()])
        self.assertNothingChanged(before)

    def test_closed_row_not_built(self):
        creator = self._register('default')['default']
        response = self.dispatch(summary_id(), 2, self.components)
        self.assertFalse(response.updated)
        self.assertEqual(creator.calls, [])

    def test_unclicked_row_not_built(self):
        creator = self._register('default')['default']
        response = self.dispatch(summary_id(), None, self.components)
        self.assertFalse(response.updated)
        self.assertEqual(creator.calls, [])

    def test_reopened_row_built_again(self):
        creator = self._register('default')['default']
        for n_clicks in (1, 2, 3):
            response = self.dispatch(summary_id(), n_clicks, self.components)
        self.assertEqual(len(creator.calls), 2)
        self.assertEqual(span_text(response.get(editor_id(), 'children')), f'default:{VARID}')

    def test_other_row_not_affected(self):
        self._register('default', section = None)
        response = self.dispatch(summary_id(), 1, self.components)
        self.assertIs(response.get(editor_id(OTHER_KEY), 'children'), NOT_UPDATED)

        response = self.dispatch(summary_id(OTHER_KEY), 1, self.components)
        self.assertEqual(span_text(response.get(editor_id(OTHER_KEY), 'children')), f'default:{SECTION}.{OTHER_KEY}.0')
        self.assertIs(response.get(editor_id(), 'children'), NOT_UPDATED)

    def test_without_creator_makes_no_update(self):
        before = self.database_state()
        with self.assertLogs('newsegsmodelapp.components.input_components', 'WARNING'):
            response = self.dispatch(summary_id(), 1, self.components)
        self.assertFalse(response.updated)
        self.assertNothingChanged(before)

    def test_without_editor_makes_no_update(self):
        creator = self._register('default')['default']
        components = [x for x in self.components if x.id != editor_id()]
        with self.assertLogs('newsegsmodelapp.components.input_components', 'WARNING'):
            response = self.dispatch(summary_id(), 1, components)
        self.assertFalse(response.updated)
        self.assertEqual(creator.calls, [])

    def test_model_specific_creator_takes_priority(self):
        creators = self._register('default', 'sprake')
        response = self.dispatch(summary_id(), 1, self.components, model_type = 'sprake')
        self.assertEqual(span_text(response.get(editor_id(), 'children')), f'sprake:{VARID}')
        self.assertEqual(creators['default'].calls, [])

    def test_default_creator_used_without_creator_for_model_type(self):
        creators = self._register('default', 'sprakeloc')
        response = self.dispatch(summary_id(), 1, self.components, model_type = 'sprake')
        self.assertEqual(span_text(response.get(editor_id(), 'children')), f'default:{VARID}')
        self.assertEqual(creators['sprakeloc'].calls, [])

class TestCallback(InputChangeTestCase):
    """The summary, editor and their ids in `react_to_input_change`"""

    def test_in_dependencies(self):
        spec = get_callback_spec(self.client, *INPUT_CHANGE_OUTPUT)
        self.assertIn('input-summary', [x['type'] for x, prop in spec.inputs if prop == 'n_clicks'])
        self.assertIn('input-group-editor', [x['type'] for x, prop in spec.outputs if prop == 'children'])
        self.assertIn('input-group-editor', [x['type'] for x, prop in spec.state if prop == 'id'])

    def test_parameter_edit_unchanged(self):
        # Without lazy rows, as every row is now
        components = self.page(('deterministic', SECTION))
        trigger = variable_id('single-input-config', 'parameter', SECTION, KEY)
        response = self.dispatch(trigger, 12.5, components)
        self.assertEqual(response.get(trigger, 'value'), 12.5)
        self.assertEqual(self.loaded_variable(VARID).parameters[0], 12.5)

    def test_existing_handler_leaves_editor(self):
        # A lazy row in the same row as an edited parameter
        param_id = VariableInstanceParameterComponentID(type = 'notype', section = SECTION, key = KEY)
        components = self.page(('deterministic', SECTION)) + page_of(create_lazy_input_details('', param_id))
        response = self.dispatch(variable_id('single-input-config', 'parameter', SECTION, KEY), 12.5, components)

        self.assertTrue(response.updated)
        self.assertIs(response.get(variable_id('input-group-editor', 'editor', SECTION, KEY), 'children'), NOT_UPDATED)
        self.assertIs(response.get(variable_id('single-input-config', 'editor-anchor', SECTION, KEY), 'value'), NOT_UPDATED)

class TestHelper(InputChangeTestCase):
    """`create_lazy_input_details`"""

    def test_ids_match_callback(self):
        spec = get_callback_spec(self.client, *INPUT_CHANGE_OUTPUT)
        summary = summary_id()
        row = lazy_row()
        found = {x.id['type']: x.id for x in page_of(row)}

        keys = {x.name for x in fields(VariableInstanceParameterComponentID)}
        self.assertEqual(found, {
            'input-summary': summary,
            'input-group-editor': editor_id(),
            'single-input-config': variable_id('single-input-config', 'editor-anchor', SECTION, KEY, supersection = SUPERSECTION),
        })
        for id_ in found.values():
            self.assertEqual(set(id_), keys)

        patterns = [x for x, _ in spec.inputs + spec.outputs + spec.state if isinstance(x, dict)]
        self.assertTrue(any(_matches(x, found['input-summary'], summary) for x in patterns if x['type'] == 'input-summary'))
        self.assertTrue(any(_matches(x, found['input-group-editor'], summary) for x in patterns if x['type'] == 'input-group-editor'))

    def test_row_matches_first_output(self):
        # The Dash renderer only calls the callback for a row with a component matching its first output
        spec = get_callback_spec(self.client, *INPUT_CHANGE_OUTPUT)
        first_output = spec.outputs[0][0]
        self.assertTrue(any(_matches(first_output, x.id, summary_id()) for x in page_of(lazy_row())))

    def test_editor_starts_empty(self):
        row = lazy_row()
        self.assertIsInstance(row, html.Details)
        summary, editor, _anchor = row.children
        self.assertIsInstance(summary, html.Summary)
        self.assertEqual(editor.children, [])
