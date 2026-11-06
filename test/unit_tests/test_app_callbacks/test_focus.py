"""
Tests of the focussed configuration of a project loaded in full (#180).

Focussing a configuration updates only the project's row (`focussed_metamodel_id`). The full project took its focus
from its payload, the index saved the last time the whole project was saved, so it could focus another configuration
than the lightweight project. The PSA plot uses the full project, so it showed "No PSA Run" for a configuration with
results, while the table, which uses the lightweight project, showed them.
"""
from .base import InputChangeTestCase, cached_variant

class TestFocusOfTheFullProject(InputChangeTestCase):
    n_metamodels = 3

    def focus_of_full_project(self, provider = None) -> str:
        return (provider or self.reader).get_project(self.project_id).get_focussed_metamodel().id

    def test_full_project_follows_the_focus(self):
        for mm_index in (2, 1, 0, 2):
            with self.subTest(mm_index = mm_index):
                self.set_focus(mm_index)
                self.assertEqual(self.focus_of_full_project(), self.metamodel_ids[mm_index])
                self.assertEqual(self.reader.get_lightweight_project(self.project_id).focussed_metamodel_id, self.metamodel_ids[mm_index])

    def test_cached_project_follows_the_focus(self):
        # A provider which holds the project in its cache, as the app's and the workers' do
        worker = self.worker_provider()
        self.set_focus(2)
        self.assertEqual(self.focus_of_full_project(worker), self.metamodel_ids[2])

    def test_saving_the_project_keeps_the_focus(self):
        self.set_focus(2)
        proj = self.reader.get_project(self.project_id)
        self.reader.upsert_component(proj)
        self.assertEqual(self.reader.get_lightweight_project(self.project_id).focussed_metamodel_id, self.metamodel_ids[2])
        self.assertEqual(self.focus_of_full_project(), self.metamodel_ids[2])

TestFocusOfTheFullProjectCached = cached_variant(TestFocusOfTheFullProject)
