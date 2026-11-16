"""
Tests of the packaging of results for download (`export.build_download` and `export.sheet_names`): the files, their
names and their contents, for one or several configurations, as csv or xlsx.
"""
import base64
import io
import unittest
import zipfile

import pandas as pd

from newsegsmodelapp.components import export

def _content(download: dict) -> bytes:
    """The bytes of the data of a `dcc.Download`."""
    if download.get('base64'):
        return base64.b64decode(download['content'])
    return download['content'].encode('utf-8')

def _dsa_frame(scale: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame({
        'variable': ['a', 'a', 'b', 'b'],
        'bound': ['low', 'high', 'low', 'high'],
        'npv': [1.0 * scale, 2.0 * scale, 3.0 * scale, 4.0 * scale],
    }).set_index(['variable', 'bound'])

class _Configuration:
    """Stands in for a metamodel, which `build_download` writes as json"""
    def __init__(self, name: str):
        self.name = name

    def to_dict_repr(self):
        return {'class': 'NewsegsMetaModel', 'name': self.name}

class TestSheetNames(unittest.TestCase):
    def test_valid_names_are_kept(self):
        self.assertEqual(export.sheet_names(['Baseline', 'Wind']), ['Baseline', 'Wind'])

    def test_invalid_characters_are_replaced(self):
        self.assertEqual(export.sheet_names(['a/b:c*d?e[f]g\\h']), ['a_b_c_d_e_f_g_h'])

    def test_long_names_are_cut_to_31_characters(self):
        (name,) = export.sheet_names(['x' * 40])
        self.assertEqual(name, 'x' * 31)

    def test_duplicates_are_numbered_ignoring_case(self):
        self.assertEqual(
            export.sheet_names(['Baseline', 'baseline', 'Baseline']),
            ['Baseline', 'baseline (2)', 'Baseline (3)'],
        )

    def test_numbered_long_names_stay_within_31_characters(self):
        names = export.sheet_names(['y' * 40, 'y' * 40])
        self.assertEqual(names[1], 'y' * 27 + ' (2)')
        self.assertTrue(all(len(x) <= 31 for x in names))

    def test_empty_name(self):
        self.assertEqual(export.sheet_names(['']), ['Sheet'])

class TestBuildDownload(unittest.TestCase):
    def test_one_configuration_csv(self):
        download = export.build_download('dsa', [('Baseline', _dsa_frame())], 'csv', 'Project')
        self.assertEqual(download['filename'], 'Baseline-dsa-results.csv')
        df = pd.read_csv(io.BytesIO(_content(download)))
        self.assertEqual(list(df.columns), ['variable', 'bound', 'npv'])
        self.assertEqual(df['npv'].tolist(), [1.0, 2.0, 3.0, 4.0])

    def test_one_configuration_xlsx(self):
        download = export.build_download('psa', [('Baseline', _dsa_frame())], 'xlsx', 'Project')
        self.assertEqual(download['filename'], 'Baseline-psa-results.xlsx')
        sheets = pd.read_excel(io.BytesIO(_content(download)), sheet_name = None)
        self.assertEqual(list(sheets), ['Baseline'])
        # Unmerged: every row has its labels, so the results can be uploaded again
        self.assertEqual(sheets['Baseline']['variable'].tolist(), ['a', 'a', 'b', 'b'])

    def test_several_configurations_csv_is_a_zip_of_a_file_per_configuration(self):
        download = export.build_download(
            'dsa', [('Baseline', _dsa_frame()), ('Wind', _dsa_frame(2))], 'csv', 'My project'
        )
        self.assertEqual(download['filename'], 'My project-dsa-results.zip')
        with zipfile.ZipFile(io.BytesIO(_content(download))) as archive:
            self.assertEqual(archive.namelist(), ['Baseline-dsa-results.csv', 'Wind-dsa-results.csv'])
            wind = pd.read_csv(archive.open('Wind-dsa-results.csv'))
        self.assertEqual(wind['npv'].tolist(), [2.0, 4.0, 6.0, 8.0])

    def test_several_configurations_xlsx_is_a_workbook_with_a_sheet_per_configuration(self):
        download = export.build_download(
            'det', [('Baseline', _dsa_frame()), ('Wind', _dsa_frame(2))], 'xlsx', 'My project'
        )
        self.assertEqual(download['filename'], 'My project-det-results.xlsx')
        sheets = pd.read_excel(io.BytesIO(_content(download)), sheet_name = None)
        self.assertEqual(list(sheets), ['Baseline', 'Wind'])
        self.assertEqual(sheets['Wind']['npv'].tolist(), [2.0, 4.0, 6.0, 8.0])

    def test_configurations_with_the_same_name_get_files_and_sheets_of_their_own(self):
        results = [('Baseline', _dsa_frame()), ('Baseline', _dsa_frame(2))]
        download = export.build_download('dsa', results, 'csv', 'Project')
        with zipfile.ZipFile(io.BytesIO(_content(download))) as archive:
            self.assertEqual(archive.namelist(), ['Baseline-dsa-results.csv', 'Baseline (2)-dsa-results.csv'])
        download = export.build_download('dsa', results, 'xlsx', 'Project')
        sheets = pd.read_excel(io.BytesIO(_content(download)), sheet_name = None)
        self.assertEqual(list(sheets), ['Baseline', 'Baseline (2)'])

    def test_configurations_are_included_as_json_in_a_zip(self):
        download = export.build_download(
            'dsa', [('Baseline', _dsa_frame())], 'xlsx', 'Project',
            configurations = [_Configuration('Baseline')], # pyright: ignore[reportArgumentType]
        )
        self.assertEqual(download['filename'], 'Baseline-dsa-results.zip')
        with zipfile.ZipFile(io.BytesIO(_content(download))) as archive:
            # Named as the DSA and PSA uploads look for them
            self.assertEqual(archive.namelist(), ['Baseline-dsa-results.xlsx', 'Baseline-config.json'])
            self.assertIn(b'"name": "Baseline"', archive.read('Baseline-config.json'))

    def test_time_zones_are_removed_for_xlsx(self):
        index = pd.date_range('2026-01-01', periods = 3, freq = 'h', tz = 'UTC')
        df = pd.DataFrame({'when': index, 'value': [1, 2, 3]}, index = index)
        download = export.build_download('det', [('Baseline', df)], 'xlsx', 'Project')
        sheet = pd.read_excel(io.BytesIO(_content(download)), index_col = 0)
        self.assertEqual(sheet['value'].tolist(), [1, 2, 3])
        self.assertEqual(sheet.index[0], pd.Timestamp('2026-01-01 00:00'))

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            export.build_download('dsa', [('Baseline', _dsa_frame())], 'pdf', 'Project') # pyright: ignore[reportArgumentType]

    def test_no_results(self):
        with self.assertRaises(ValueError):
            export.build_download('dsa', [], 'csv', 'Project')

if __name__ == '__main__':
    unittest.main()
