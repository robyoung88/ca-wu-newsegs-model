"""
Tests of `update_input_header_contents`, which draws the headers of the input sections (issue 158).

Not every section has a header: those of DSA, optimisation and PSA have no content creator. Their headers used to be
reported as errors, with a traceback, on every load of their pages; they are now left as they are.
"""
import json
import logging

from dash import dcc, html

from newsegsmodelapp.components.callbacks import input_container_callbacks

from .base import MODEL_TYPE, InputChangeTestCase
from .dash_dispatch import NOT_UPDATED, dispatch_callback, get_callback_spec

def _header(supersection: str, section: str) -> dict:
    return {'type': 'input-section-header', 'supersection': supersection, 'section': section}

def _interval(supersection: str, section: str) -> dict:
    return {'type': 'input-container-hydration-interval', 'supersection': supersection, 'section': section}

WITH_CREATOR = ('deterministic', 'gen_input')
WITHOUT_CREATOR = ('dsa', 'dsa')

class TestInputSectionHeaders(InputChangeTestCase):

    def _draw_headers(self, sections):
        components = []
        for supersection, section in sections:
            components.append(html.Div(id = _header(supersection, section)))
            components.append(dcc.Interval(id = _interval(supersection, section), n_intervals = 1))
        spec = get_callback_spec(self.client, 'input-section-header', 'children')
        return dispatch_callback(
            self.client, spec, 'layout-update-trigger', 1, components,
            stores = {'active-project-id': self.project_id, 'app-state': json.dumps({'model_type': MODEL_TYPE})},
        )

    def test_header_without_creator_is_left_as_it_is(self):
        with self.assertNoLogs(input_container_callbacks.logger, logging.ERROR):
            response = self._draw_headers([WITH_CREATOR, WITHOUT_CREATOR])
        # The header with a creator is drawn in the same call, and both containers are rebuilt
        self.assertIsNot(response.get(_header(*WITH_CREATOR), 'children'), NOT_UPDATED)
        self.assertIs(response.get(_header(*WITHOUT_CREATOR), 'children'), NOT_UPDATED)
        for section in (WITH_CREATOR, WITHOUT_CREATOR):
            self.assertEqual(response.get(_interval(*section), 'n_intervals'), 0)

    def test_missing_creator_is_logged_at_debug_level(self):
        with self.assertLogs(input_container_callbacks.logger, logging.DEBUG) as logs:
            self._draw_headers([WITHOUT_CREATOR])
        missing = [x for x in logs.records if 'creator not found' in x.getMessage()]
        self.assertEqual([x.levelno for x in missing], [logging.DEBUG])
        self.assertIn('dsa.dsa.' + MODEL_TYPE, missing[0].getMessage())

    def test_only_headers_without_creators(self):
        with self.assertNoLogs(input_container_callbacks.logger, logging.ERROR):
            response = self._draw_headers([WITHOUT_CREATOR, ('optim', 'optim')])
        self.assertIs(response.get(_header(*WITHOUT_CREATOR), 'children'), NOT_UPDATED)
        self.assertEqual(response.get(_interval(*WITHOUT_CREATOR), 'n_intervals'), 0)
