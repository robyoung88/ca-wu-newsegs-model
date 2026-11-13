"""
Tests that a change to a variable reaches its inputs in other supersections, and every configuration sharing it.
"""
from .base import InputChangeTestCase, cached_variant
from .dash_dispatch import variable_id

WIND = ('gen_input', 'wind_capacity')
WIND_VARID = 'gen_input.wind_capacity.0'

def parameter_id(supersection: str) -> dict:
    return variable_id('single-input-config', 'parameter', *WIND, supersection = supersection)

class TestSupersectionSync(InputChangeTestCase):
    """The inputs of a variable's focused value in the DSA and optimisation supersections follow each other"""

    def setUp(self):
        super().setUp()
        self.components = self.page(('dsa', None), ('optim', None))

    def test_dsa_to_optim(self):
        response = self.dispatch(parameter_id('dsa'), 12.5, self.components)
        self.assertEqual(response.get(parameter_id('optim'), 'value'), 12.5)
        self.assertEqual(self.stored_variable(WIND_VARID).raw_parameters[0], 12.5)

    def test_optim_to_dsa(self):
        response = self.dispatch(parameter_id('optim'), 12.5, self.components)
        self.assertEqual(response.get(parameter_id('dsa'), 'value'), 12.5)
        self.assertEqual(self.stored_variable(WIND_VARID).raw_parameters[0], 12.5)

class TestSharedVariable(InputChangeTestCase):
    """A change to a shared Variable is loaded by every configuration in its group"""
    n_metamodels = 3

    def setUp(self):
        super().setUp()
        # The first two configurations share the variable; the third has a separate instance
        self.make_independent(2, WIND_VARID)
        self.old = self.stored_variable(WIND_VARID).raw_parameters[0]

    def _loaded_values(self) -> list:
        """The value each configuration loads, from the database and through the app's provider"""
        values = [self.loaded_variable(WIND_VARID, x).raw_parameters[0] for x in range(self.n_metamodels)]
        proj = self.provider.get_project(self.project_id)
        self.assertEqual(values, [x.variables[WIND_VARID].raw_parameters[0] for x in proj.metamodels])
        return values

    def test_group_loads_change(self):
        self.dispatch(parameter_id('deterministic'), 12.5, self.page(('deterministic', 'gen_input')))
        self.assertEqual(self._loaded_values(), [12.5, 12.5, self.old])

    def test_change_made_to_focussed_configuration(self):
        self.set_focus(2)
        self.dispatch(parameter_id('deterministic'), 12.5, self.page(('deterministic', 'gen_input')))
        self.assertEqual(self._loaded_values(), [self.old, self.old, 12.5])

TestSupersectionSyncCached = cached_variant(TestSupersectionSync)
TestSharedVariableCached = cached_variant(TestSharedVariable)
