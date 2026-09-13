"""
Unit tests for constructor registry
"""
import unittest

from test.unit_tests.common import setup_test_env
setup_test_env()

from newsegsmodelframework.core.constructors import registers

class TestRegisters(unittest.TestCase):

    def test_component_register(self):
        compreg = registers.get_newsegscomponent_register()
        # Don't know how long this should be any more, need to think of a better way to test
        # self.assertEqual(
        #     len(compreg),
        #     2+2+3+2+9
        # )
    
    def test_environment_register(self):
        envreg = registers.get_environment_register()

        self.assertEqual(
            len(envreg),
            4
        )

    def test_generator_register(self):
        genreg = registers.get_generator_register()

        self.assertEqual(
            len(genreg),
            5
        )

    def test_location_register(self):
        locreg = registers.get_location_register()

        self.assertEqual(
            len(locreg),
            3
        )
    
    def test_module_register(self):
        modreg = registers.get_newsegsmodule_register()

        self.assertEqual(
            len(modreg),
            3
        )

    def test_timespan_register(self):
        tsreg = registers.get_timespan_register()

        self.assertEqual(
            len(tsreg),
            3
        )
