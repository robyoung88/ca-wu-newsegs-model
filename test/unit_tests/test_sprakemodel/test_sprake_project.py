"""
Unit tests for project plugin for sprake model type
"""
import unittest

from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

class TestSprakeProjectPlugin(unittest.TestCase):
    """
    Test creation of projects from the factory function plugin
    """

    def test_basic_construction(self):
        proj = PROJECT_FACTORIES['sprake']()

        self.assertEqual(proj.model_type, 'sprake')
        