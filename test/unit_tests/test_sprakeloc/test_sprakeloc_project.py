"""
Unit tests for project plugin for sprake model type
"""
import unittest

from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

class TestSprakeLocProjectPlugin(unittest.TestCase):
    """
    Test creation of projects from the factory function plugin
    """

    def test_basic_construction(self):
        proj = PROJECT_FACTORIES['sprakeloc']()

        self.assertEqual(proj.model_type, 'sprakeloc')
        