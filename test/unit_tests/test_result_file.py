import tempfile
import unittest
from pathlib import Path
import pandas as pd

from newsegsmodelapp.components.result_file import save_result, load_result, register_saver, register_loader, UnsupportedFileExtensionError

# Define custom class at top level (module scope) for pickling support
class CustomOutput:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, CustomOutput) and self.value == other.value
    

class TestResultStoreSaveAndLoad(unittest.TestCase):

    def setUp(self):
        """Create a temporary directory for test output files."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        self.temp_dir.cleanup()

    # -------------------------------------------------------------------------
    # Tests for DataFrame / Series (Parquet)
    # -------------------------------------------------------------------------
    def test_save_and_load_dataframe(self):
        df = pd.DataFrame({"col1": [1, 2, 3], "col2": ["a", "b", "c"]})
        root_file = self.test_dir / "data_frame_test"

        # Test Save
        saved_path = save_result(df, str(root_file))
        self.assertTrue(saved_path.endswith(".parquet"))
        self.assertTrue(Path(saved_path).exists())

        # Test Load
        loaded_df = load_result(saved_path)
        self.assertIsInstance(loaded_df, pd.DataFrame)
        pd.testing.assert_frame_equal(df, loaded_df)

    def test_save_and_load_series(self):
        series = pd.Series([10, 20, 30], name="test_series")
        root_file = self.test_dir / "series_test"

        saved_path = save_result(series, str(root_file))
        self.assertTrue(Path(saved_path).exists())

        # Test Load
        loaded_df = load_result(saved_path)
        self.assertIsInstance(loaded_df, pd.DataFrame)
        self.assertEqual(loaded_df["test_series"].tolist(), [10, 20, 30])

    # -------------------------------------------------------------------------
    # Tests for Built-in Structures (JSON & Text)
    # -------------------------------------------------------------------------
    def test_save_and_load_json_structures(self):
        data = {"name": "Experiment 1", "metrics": [1.0, 2.5, 3.8]}
        root_file = self.test_dir / "json_test"

        saved_path = save_result(data, str(root_file))
        self.assertTrue(saved_path.endswith(".json"))

        loaded_data = load_result(saved_path)
        self.assertEqual(data, loaded_data)

    def test_save_and_load_string_text(self):
        text_content = "Hello, World!\nUnit testing result store."
        root_file = self.test_dir / "text_test"

        saved_path = save_result(text_content, str(root_file))
        self.assertTrue(saved_path.endswith(".txt"))

        loaded_text = load_result(saved_path)
        self.assertEqual(text_content, loaded_text)

    # -------------------------------------------------------------------------
    # Tests for Fallback (Pickle)
    # -------------------------------------------------------------------------
    def test_save_and_load_fallback_custom_object(self):

        custom_obj = CustomOutput(42)
        root_file = self.test_dir / "custom_obj_test"

        # Should fall back to pickle (.pkl)
        saved_path = save_result(custom_obj, str(root_file))
        self.assertTrue(saved_path.endswith(".pkl") or saved_path.endswith(".pickle"))

        loaded_obj = load_result(saved_path)
        self.assertEqual(custom_obj, loaded_obj)

    # -------------------------------------------------------------------------
    # Tests for Error Handling & Custom Registration
    # -------------------------------------------------------------------------
    def test_load_non_existent_file_raises_error(self):
        non_existent_path = self.test_dir / "does_not_exist.parquet"
        with self.assertRaises(FileNotFoundError):
            load_result(non_existent_path)

    def test_load_unsupported_extension_raises_error(self):
        unsupported_file = self.test_dir / "invalid_file.unknown"
        unsupported_file.write_text("dummy data")

        with self.assertRaises(UnsupportedFileExtensionError):
            load_result(unsupported_file)

    def test_dynamic_saver_and_loader_registration(self):
        class CustomReport:
            def __init__(self, text):
                self.text = text

        # 1. Register dynamic saver
        @register_saver(CustomReport)
        def _save_report(report: CustomReport, root_filename: str) -> str:
            filepath = f"{root_filename}.rpt"
            with open(filepath, "w") as f:
                f.write(report.text)
            return filepath

        # 2. Register dynamic loader
        @register_loader(".rpt")
        def _load_report(filepath: Path) -> CustomReport:
            return CustomReport(filepath.read_text())

        # 3. Test combined custom pipeline
        report = CustomReport("Confidential Report Content")
        root_file = self.test_dir / "report_test"

        saved_path = save_result(report, str(root_file))
        self.assertTrue(saved_path.endswith(".rpt"))

        loaded_report = load_result(saved_path)
        self.assertIsInstance(loaded_report, CustomReport)
        self.assertEqual(loaded_report.text, "Confidential Report Content")
