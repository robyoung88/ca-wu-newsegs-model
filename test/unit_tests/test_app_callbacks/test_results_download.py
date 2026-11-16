"""
Tests of the download of results: the dialog of each type of result (deterministic, DSA and PSA) opens from its buttons,
and downloads the results of the configuration or of all configurations, as csv or xlsx, with feedback on the
configurations without results.

The app holds the callbacks of `results_download`, and a result provider on a temporary store. The requests are posted
to `/_dash-update-component`, as the browser makes them (see `dash_dispatch`).
"""
import base64
import io
from pathlib import Path
from typing import Any, cast
import zipfile

from dash import html
import pandas as pd

from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.components import results_download as rd
from newsegsmodelapp.dash_extension import NewsegsDash

from .base import InputChangeTestCase, _Unused
from .dash_dispatch import DEPENDENCIES_URL, CallbackResponse, CallbackSpec, dispatch_callback, iter_components, stringify_id

def _content(download: dict) -> bytes:
    if download.get('base64'):
        return base64.b64decode(download['content'])
    return download['content'].encode('utf-8')

def _dsa_frame(scale: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({
        'variable': ['a', 'a'], 'bound': ['low', 'high'], 'npv': [1.0 * scale, 2.0 * scale],
    }).set_index(['variable', 'bound'])

class ResultsDownloadTestCase(InputChangeTestCase):
    """A project of three configurations, and an app holding the callbacks of the download dialogs."""
    n_metamodels = 3

    def setUp(self):
        super().setUp()
        from newsegsmodelapp.backend import db
        self.results = FromDatabaseResultProvider(db.get_engine, Path(self._db_dir.name) / 'results')
        self.app = NewsegsDash(
            __name__,
            project_provider = self.provider,
            results_provider = self.results,
            request_handler = cast(Any, _Unused()),
            suppress_callback_exceptions = True,
        )
        self.app.layout = html.Div()
        rd.add_results_download_callbacks(self.app)
        self.app.server.config['TESTING'] = True
        self.client = self.app.server.test_client()

        proj = self.reader.get_project(self.project_id)
        self.names = ['Baseline', 'Wind', 'Solar']
        for mm, name in zip(proj.metamodels, self.names):
            self.reader.metamodel_provider.set_component_metadata(mm.id, 'label', name)
        self.provider.invalidate_cache_for_component(self.project_id)

    # -------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------

    def store_result(self, result_type: str, mm_index: int, frame: pd.DataFrame):
        mm = self.reader.get_project(self.project_id).metamodels[mm_index]
        self.results.upsert_result(f'{result_type}_single_metamodel', mm.table_config, frame)

    def page(self, result_type: str, targets: tuple[str, ...] = (rd.FOCUSSED,), **values) -> list:
        """The components of the dialog, and the buttons which open it, with the option values given."""
        components = [
            c for c in iter_components(
                rd.create_results_download_components(result_type)
                + [rd.create_results_download_button(result_type, target) for target in targets]
            )
            if getattr(c, 'id', None) is not None
        ]
        props = {
            'scope': ('results-download-scope', 'value'),
            'format_option': ('results-download-format', 'value'),
            'include': ('results-download-include', 'value'),
            'target': ('results-download-target', 'data'),
        }
        for name, value in values.items():
            type_, prop = props[name]
            component = next(c for c in components if c.id == rd.component_id(type_, result_type))
            setattr(component, prop, value)
        return components

    def spec(self, result_type: str) -> CallbackSpec:
        target = stringify_id(rd.component_id('results-download', result_type))
        for dep in self.client.get(DEPENDENCIES_URL).get_json():
            spec = CallbackSpec.from_dependency(dep)
            if any(stringify_id(id_) == target for id_, _ in spec.outputs):
                return spec
        raise LookupError(f'No callback outputs {target}')

    def click(self, result_type: str, trigger: dict, page: list) -> CallbackResponse:
        return dispatch_callback(
            self.client, self.spec(result_type), trigger, 1, page,
            stores = {'active-project-id': self.project_id},
        )

    def ok(self, result_type: str, **values) -> CallbackResponse:
        page = self.page(result_type, **values)
        return self.click(result_type, rd.component_id('results-download-ok', result_type), page)

    def get(self, response: CallbackResponse, type_: str, result_type: str, prop: str):
        return response.get(rd.component_id(type_, result_type), prop)

    def download(self, response: CallbackResponse, result_type: str) -> dict:
        download = self.get(response, 'results-download', result_type, 'data')
        self.assertIsInstance(download, dict, 'Nothing was downloaded')
        return download

    def feedback(self, response: CallbackResponse, result_type: str) -> str | None:
        if self.get(response, 'results-download-feedback', result_type, 'is_open') is not True:
            return None
        return self.get(response, 'results-download-feedback', result_type, 'children')

class TestOpening(ResultsDownloadTestCase):
    def test_each_type_opens_from_its_header_button(self):
        for result_type in rd.RESULT_TYPES:
            with self.subTest(result_type = result_type):
                page = self.page(result_type)
                response = self.click(result_type, rd.open_button_id(result_type), page)
                self.assertIs(self.get(response, 'results-download-modal', result_type, 'is_open'), True)
                self.assertEqual(self.get(response, 'results-download-target', result_type, 'data'), rd.FOCUSSED)
                options = self.get(response, 'results-download-scope', result_type, 'options')
                self.assertEqual(options[0]['label'], 'This configuration (Baseline)')

    def test_a_configurations_button_targets_it(self):
        mm_id = self.metamodel_ids[1]
        page = self.page('det', targets = (rd.FOCUSSED, mm_id), scope = rd.SCOPE_ALL)
        response = self.click('det', rd.open_button_id('det', mm_id), page)
        self.assertIs(self.get(response, 'results-download-modal', 'det', 'is_open'), True)
        self.assertEqual(self.get(response, 'results-download-target', 'det', 'data'), mm_id)
        self.assertEqual(self.get(response, 'results-download-scope', 'det', 'value'), rd.SCOPE_ONE)
        options = self.get(response, 'results-download-scope', 'det', 'options')
        self.assertEqual(options[0]['label'], 'This configuration (Wind)')

    def test_buttons_drawn_without_clicks_do_nothing(self):
        page = self.page('det')
        response = dispatch_callback(
            self.client, self.spec('det'), rd.open_button_id('det'), None, page,
            stores = {'active-project-id': self.project_id},
        )
        self.assertFalse(response.updated)

    def test_cancel_closes(self):
        page = self.page('psa')
        response = self.click('psa', rd.component_id('results-download-cancel', 'psa'), page)
        self.assertIs(self.get(response, 'results-download-modal', 'psa', 'is_open'), False)
        self.assertIsNone(self.feedback(response, 'psa'))

class TestDownload(ResultsDownloadTestCase):
    def test_focussed_configuration_csv(self):
        self.store_result('dsa', 0, _dsa_frame())
        response = self.ok('dsa')
        self.assertIs(self.get(response, 'results-download-modal', 'dsa', 'is_open'), False)
        download = self.download(response, 'dsa')
        self.assertEqual(download['filename'], 'Baseline-dsa-results.csv')
        self.assertEqual(pd.read_csv(io.BytesIO(_content(download)))['npv'].tolist(), [1.0, 2.0])
        self.assertIsNone(self.feedback(response, 'dsa'))

    def test_psa_downloads(self):
        # The PSA dialog did not open, and its download asked for the results of the project, which is not supported
        self.store_result('psa', 0, pd.DataFrame({'npv': [1.0, 2.0, 3.0]}))
        download = self.download(self.ok('psa', format_option = 'xlsx'), 'psa')
        self.assertEqual(download['filename'], 'Baseline-psa-results.xlsx')
        sheets = pd.read_excel(io.BytesIO(_content(download)), sheet_name = None)
        self.assertEqual(sheets['Baseline']['npv'].tolist(), [1.0, 2.0, 3.0])

    def test_targeted_configuration(self):
        self.store_result('dsa', 0, _dsa_frame())
        self.store_result('dsa', 2, _dsa_frame(3))
        download = self.download(self.ok('dsa', target = self.metamodel_ids[2]), 'dsa')
        self.assertEqual(download['filename'], 'Solar-dsa-results.csv')
        self.assertEqual(pd.read_csv(io.BytesIO(_content(download)))['npv'].tolist(), [3.0, 6.0])

    def test_all_configurations_xlsx_has_a_sheet_per_configuration(self):
        for i in range(3):
            self.store_result('dsa', i, _dsa_frame(i + 1))
        download = self.download(self.ok('dsa', scope = rd.SCOPE_ALL, format_option = 'xlsx'), 'dsa')
        self.assertTrue(download['filename'].endswith('-dsa-results.xlsx'))
        sheets = pd.read_excel(io.BytesIO(_content(download)), sheet_name = None)
        self.assertEqual(list(sheets), self.names)
        self.assertEqual(sheets['Solar']['npv'].tolist(), [3.0, 6.0])

    def test_all_configurations_csv_is_a_file_per_configuration(self):
        for i in range(3):
            self.store_result('psa', i, pd.DataFrame({'npv': [float(i)]}))
        download = self.download(self.ok('psa', scope = rd.SCOPE_ALL), 'psa')
        with zipfile.ZipFile(io.BytesIO(_content(download))) as archive:
            self.assertEqual(archive.namelist(), [f'{x}-psa-results.csv' for x in self.names])

    def test_configurations_without_results_are_left_out_and_named(self):
        self.store_result('dsa', 1, _dsa_frame())
        response = self.ok('dsa', scope = rd.SCOPE_ALL, format_option = 'xlsx')
        sheets = pd.read_excel(io.BytesIO(_content(self.download(response, 'dsa'))), sheet_name = None)
        self.assertEqual(list(sheets), ['Wind'])
        self.assertEqual(
            self.feedback(response, 'dsa'),
            'Configurations without DSA results were left out: Baseline, Solar.',
        )

    def test_without_results_nothing_is_downloaded(self):
        response = self.ok('dsa')
        self.assertNotIsInstance(self.get(response, 'results-download', 'dsa', 'data'), dict)
        self.assertEqual(self.feedback(response, 'dsa'), 'Baseline has no DSA results to download.')
        response = self.ok('dsa', scope = rd.SCOPE_ALL)
        self.assertEqual(self.feedback(response, 'dsa'), 'No configuration has DSA results to download.')

    def test_deterministic_without_results_reports_rather_than_failing(self):
        response = self.ok('det')
        self.assertNotIsInstance(self.get(response, 'results-download', 'det', 'data'), dict)
        self.assertEqual(self.feedback(response, 'det'), 'Baseline has no deterministic results to download.')

    def test_removed_configuration(self):
        target = self.metamodel_ids[2]
        self.remove_configuration(2)
        self.provider.invalidate_cache_for_component(self.project_id)
        response = self.ok('dsa', target = target)
        self.assertEqual(self.feedback(response, 'dsa'), 'The configuration has been removed from the project.')

    def test_configurations_included_as_json(self):
        self.store_result('dsa', 0, _dsa_frame())
        download = self.download(self.ok('dsa', include = [rd.INCLUDE_CONFIGURATION]), 'dsa')
        self.assertEqual(download['filename'], 'Baseline-dsa-results.zip')
        with zipfile.ZipFile(io.BytesIO(_content(download))) as archive:
            self.assertEqual(archive.namelist(), ['Baseline-dsa-results.csv', 'Baseline-config.json'])
