"""Tests of the default names users see: of new projects, configurations and sites, and of copies (issue 90)."""

import unittest

from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import FIRST_CONFIGURATION_NAME
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
from newsegsmodelframework.util.naming import copy_name, unique_name
import newsegsmodelframework.plugins.projects.sprake # noqa: F401 Registers the factory
import newsegsmodelframework.plugins.projects.sprakeloc # noqa: F401
import newsegsmodelframework.plugins.projects.sprakevalidation # noqa: F401

class TestCopyName(unittest.TestCase):

    def test_first_copy(self):
        self.assertEqual(copy_name('Baseline'), 'Baseline (copy)')

    def test_copies_are_numbered(self):
        self.assertEqual(copy_name('Baseline', ['Baseline', 'Baseline (copy)']), 'Baseline (copy 2)')
        self.assertEqual(
            copy_name('Baseline', ['Baseline', 'Baseline (copy)', 'Baseline (copy 2)']), 'Baseline (copy 3)'
        )

    def test_suffixes_do_not_stack(self):
        existing = ['Baseline', 'Baseline (copy)', 'Baseline (copy 2)']
        for source in existing[1:]:
            with self.subTest(source = source):
                self.assertEqual(copy_name(source, existing), 'Baseline (copy 3)')

    def test_free_number_is_taken(self):
        self.assertEqual(copy_name('Baseline (copy 2)', ['Baseline', 'Baseline (copy 2)']), 'Baseline (copy)')

    def test_only_a_final_suffix_is_replaced(self):
        self.assertEqual(copy_name('Heat (copy) pumps'), 'Heat (copy) pumps (copy)')

    def test_unique_name(self):
        self.assertEqual(unique_name('Heat pumps', ['Baseline']), 'Heat pumps')
        self.assertEqual(unique_name('Baseline', ['Baseline']), 'Baseline (copy)')

class TestSiteName(unittest.TestCase):

    def test_new_site_is_unnamed(self):
        loc = Location(53.2551, -3.4771)
        self.assertEqual(loc.name, '')
        self.assertEqual(loc.display_name, 'Site at 53.255, -3.477')

    def test_named_site(self):
        self.assertEqual(Location(53.255, -3.477, name = 'Sprake Close').display_name, 'Sprake Close')

    def test_display_name_follows_location(self):
        loc = Location(53.255, -3.477)
        loc.latlon = (52.0, -4.0)
        self.assertEqual(loc.display_name, 'Site at 52.000, -4.000')

    def test_unnamed_site_stays_unnamed(self):
        loc = Location(53.255, -3.477)
        self.assertEqual(Location(loc).name, '')
        self.assertEqual(Location.from_dict(loc.to_dict()).name, '')

class TestNewProjectNames(unittest.TestCase):

    def test_factories(self):
        for model_type, factory in PROJECT_FACTORIES.items():
            with self.subTest(model_type = model_type):
                proj = factory()
                self.assertEqual(proj.name, 'Untitled project')
                self.assertEqual(proj.metamodels[0].name, FIRST_CONFIGURATION_NAME)

class TestConfigurationNameInput(unittest.TestCase):

    def _name_input(self, metamodel):
        from newsegsmodelapp.components import configuration_selector
        row = configuration_selector.create_single_configuration_selector_row(0, metamodel)
        return next(
            x for x in row.children[0].children[0].children
            if getattr(x, 'id', None) == {'type': 'config-name-input', 'index': 0}
        )

    def test_unnamed_configuration_shows_hint(self):
        from newsegsmodelapp.components.configuration_selector import CONFIGURATION_NAME_HINT
        name_input = self._name_input(None)
        self.assertEqual(name_input.value, '')
        self.assertEqual(name_input.placeholder, CONFIGURATION_NAME_HINT)

    def test_named_configuration_shows_name(self):
        class _Named:
            name = 'Heat pumps and PV'
        self.assertEqual(self._name_input(_Named()).value, 'Heat pumps and PV')

if __name__ == '__main__':
    unittest.main()
