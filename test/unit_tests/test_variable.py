"""
Unit tests for newsegsbrowser/variable.
"""
import unittest

import numpy as np
import numpy.testing as nptest

from unit_tests.common import setup_test_env
setup_test_env()

from src.newsegsbrowser import variable

class TestParameterisations(unittest.TestCase):

    def test_constant_parameterisations(self):
        """
        Combine testing the specifics of the constant parameterisations with the behaviour of the Singleton
        """
        parameterisation_1 = variable.ConstantParameterisationDefault()
        self.assertEqual(
            parameterisation_1.names,
            ('value', )
        )
        self.assertEqual(
            parameterisation_1.types,
            ('scalar',)
        )
        self.assertEqual(
            parameterisation_1.defaults,
            (1., )
        )
        self.assertEqual(
            parameterisation_1.generator('A string'),
            ('A string', )
        )

        parameterisation_2 = variable.ConstantParameterisationDefault()
        parameterisation_2.defaults = (2., )
        # Check singleton behaviour
        self.assertEqual(
            parameterisation_1.defaults,
            (2., )
        )

        dist = variable.ConstantDistribution()
        self.assertEqual(
            dist.parameterisations[0].defaults,
            (2., )
        )

        dummyvar = variable.Variable('dummy')

        self.assertEqual(
            dist.n_values(dummyvar),
            1
        )

        with self.assertRaises(TypeError):
            dist.value_validation(dummyvar, 1, 2)
        
        with self.assertRaises(TypeError):
            dist.value_validation(dummyvar, [1, 2])
        
        dist.parameter_validation(dummyvar, 'throw?')
        dummyvar.set_transform('ln')
        with self.assertRaises(TypeError):
            dist.parameter_validation(dummyvar, 'throw?')

    def test_binom_parameterisations(self):
        """
        Test that the binomial parameterisations work
        """

        dist = variable.BinomialDistribution()

class test_polymorphic_factory(unittest.TestCase):
    """
    Test that the polymorphic variable system works as intended.
    """
    
    def test_construction(self):
        const_var = variable.Variable('const var', distribution = 'constant')
        binom_var = variable.Variable('binom var', distribution = 'binomial')
        normal_var = variable.Variable('normal var', distribution = 'normal')
        beta_var = variable.Variable('beta var', distribution = 'beta')
        gamma_var = variable.Variable('gamma var', distribution = 'gamma')
        constant_vector_var = variable.Variable('constant_vector var', distribution = 'constant_vector')
        mvn_var = variable.Variable('mvn var', distribution = 'mvn')
        dirichlet_var = variable.Variable('dirichlet var', distribution = 'dirichlet')

        self.assertIsInstance(const_var, variable.ConstantVariable)
        self.assertIsInstance(binom_var, variable.BinomialVariable)
        self.assertIsInstance(normal_var, variable.NormalVariable)
        self.assertIsInstance(beta_var, variable.BetaVariable)
        self.assertIsInstance(gamma_var, variable.GammaVariable)
        self.assertIsInstance(constant_vector_var, variable.ConstantVectorVariable)
        self.assertIsInstance(mvn_var, variable.MultivariateNormalVariable)
        self.assertIsInstance(dirichlet_var, variable.DirichletVariable)


def activate_dsa(var: variable.Variable):
    var.dsa_selectable = True
    var.dsa_selected = True
    var.dsa_active = True
    var.dsa_focussed = True

def activate_psa(var: variable.Variable):
    var.psa_selectable = True
    var.psa_selected = True
    var.psa_active = True

class TestVariableValidation(unittest.TestCase):
    """
    Ensure that Variables handle creation and sampling correctly
    """
    def make_constant_variable(self):
        return variable.Variable(
            'const1',
            variable_type = 'scalar',
            distribution = 'constant',
            transform = 'identity',
            parameters = 'String Constant',
            dsa_lower = 'Different String',
            dsa_upper = 'Another Different String'
        )
    
    def make_constant_variable_numeric(self):
        return variable.Variable(
            'const2',
            variable_type = 'scalar',
            distribution = 'constant',
            transform = 'identity',
            parameters = 12.34,
            dsa_lower = 9.9,
            dsa_upper = 20
        )
    
    def test_constant_constructors(self):
        var = variable.Variable('aconst')

        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('lower', True)
        )
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('upper', True)
        )

        var = variable.Variable('aconst', dsa_bounds_type='relative')
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('lower', True)
        )
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('upper', True)
        )

        var = variable.Variable('aconst', dsa_bounds_type='offset')
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('lower', True)
        )
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('upper', True)
        )

        var = variable.Variable('aconst', parameters = 'A string')
        self.assertEqual(
            var.deterministic_value,
            'A string'
        )

        var = variable.Variable(
            'aconst',
            parameters = ('A string',)
        )
        self.assertEqual(
            var.deterministic_value,
            'A string'
        )
        
        with self.assertRaises(ValueError):
            var = variable.Variable(
                'aconst',
                parameters = 'A string',
                transform = 'ln',
                dsa_bounds_type = 'relative'
            )
        
        var = variable.Variable(
                'aconst',
                parameters = 'A string',
                dsa_bounds_type = 'relative',
                dsa_lower = 0.9,
                dsa_upper = 1.1
            )
        
        with self.assertRaises(TypeError):
            var.get_dsa_value('lower', True)

    def test_constant_deterministic(self):
        var1 = self.make_constant_variable()

        self.assertEqual(
            var1.deterministic_value,
            'String Constant'
        )

        var1 = self.make_constant_variable_numeric()
        self.assertEqual(
            var1.deterministic_value,
            12.34
        )

        var1.set_parameters(10.1)
        self.assertEqual(
            var1.deterministic_value,
            10.1
        )

    def test_constant_dsa(self):
        var1 = self.make_constant_variable()
        var2 = self.make_constant_variable_numeric()

        for bound in ['central', 'lower', 'upper']:
            self.assertEqual(
                var1.get_dsa_value(bound), # pyright: ignore[reportArgumentType]
                'String Constant'
            )
            self.assertEqual(
                var2.get_dsa_value(bound), # pyright: ignore[reportArgumentType]
                12.34
            )

        for var_x in [var1, var2]:
            activate_dsa(var_x)
            
        self.assertEqual(
            var1.get_dsa_value('central'),
            'String Constant'
        )

        self.assertEqual(
            var1.get_dsa_value('lower'),
            'Different String'
        )

        self.assertEqual(
            var1.get_dsa_value('upper'),
            'Another Different String'
        )

        self.assertEqual(
            var2.get_dsa_value('central'),
            12.34
        )

        self.assertEqual(
            var2.get_dsa_value('lower'),
            9.9
        )

        self.assertEqual(
            var2.get_dsa_value('upper'),
            20.0
        )

        var2.dsa_bounds_type = 'relative'
        var2.dsa_upper = 1.1
        var2.dsa_lower = 0.9

        self.assertEqual(
            var2.get_dsa_value('central'),
            12.34
        )

        self.assertEqual(
            var2.get_dsa_value('lower'),
            12.34 * 0.9
        )

        self.assertEqual(
            var2.get_dsa_value('upper'),
            12.34 * 1.1
        )

        var2.dsa_bounds_type = 'offset'
        var2.dsa_upper = 1.2
        var2.dsa_lower = -1.2

        self.assertEqual(
            var2.get_dsa_value('lower'),
            12.34 -1.2
        )

        self.assertEqual(
            var2.get_dsa_value('upper'),
            12.34 + 1.2
        )

    def test_constant_psa(self):
        var1 = self.make_constant_variable()

        rng = np.random.default_rng(123)

        psa_draws = [None] * 100
        for i in range(100):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value() # pyright: ignore[reportCallIssue, reportArgumentType]
        
        self.assertTrue(all(x=='String Constant' for x in psa_draws))

        activate_psa(var1)
        
        psa_draws = ["None"] * 100
        for i in range(100):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value() # pyright: ignore[reportCallIssue, reportArgumentType]
        
        self.assertTrue(all(x=='String Constant' for x in psa_draws))


    def test_constant_validation(self):
        var1 = variable.Variable(
            'const1',
            variable_type = 'scalar',
            distribution = 'constant',
            transform = 'identity',
            parameters = 'String Constant'
        )

        with self.assertRaises(TypeError):
            var1.set_parameters('Test', 'Param')

        with self.assertRaises(ValueError):
            var1.set_parameters(['Test', 'Param'])

        var1.set_parameters(2)
        self.assertEqual(
            var1.deterministic_value,
            2
        )
        var1.set_parameters(5.5)
        self.assertEqual(
            var1.deterministic_value,
            5.5
        )
        var1.set_parameters([5.25])
        self.assertEqual(
            var1.deterministic_value,
            5.25
        )

        with self.assertRaises(ValueError):
            """
            Needs to be a scalar, not a vector.
            """
            var1 = variable.Variable(
                'const1',
                variable_type = 'vector',
                distribution = 'constant',
                transform = 'identity',
                parameters = 'String Constant'
            )
        
        with self.assertRaises(ValueError):
            """
            Cannot use a log transform with a string constant
            """
            var1 = variable.Variable(
                'const1',
                variable_type = 'scalar',
                distribution = 'constant',
                transform = 'ln',
                parameters = 'String Constant'
            )

    def make_binomial_variable(self):
        return variable.Variable(
            'const1',
            variable_type = 'scalar',
            distribution = 'binomial',
            transform = 'identity',
            parameters = [0.2, 5],
            dsa_lower = 0,
            dsa_upper = 3
        )
    
    def test_binomial_constructors(self):
        var = variable.Variable(
            'abinom',
            distribution = 'binomial'
        )

    def test_binomial_deterministic(self):
        var1 = self.make_binomial_variable()

        self.assertEqual(
            var1.deterministic_value,
            1
        )

        var1.set_parameters(0.8, 5)
        self.assertEqual(
            var1.deterministic_value,
            4
        )    

    def test_binomial_dsa(self):
        var1 = self.make_binomial_variable()

        for bound in ['central', 'lower', 'upper']:
            self.assertEqual(
                var1.get_dsa_value(bound), # pyright: ignore[reportArgumentType]
                1
            )
        
        activate_dsa(var1)

        self.assertEqual(
            var1.get_dsa_value('central'),
            1
        )
        self.assertEqual(
            var1.get_dsa_value('lower'),
            0
        )
        self.assertEqual(
            var1.get_dsa_value('upper'),
            3
        )

        var1.dsa_bounds_type = 'relative'
        var1.dsa_lower = 0.0
        var1.dsa_upper = 1.1
        self.assertEqual(
            var1.get_dsa_value('lower'),
            0
        )
        with self.assertRaises(ValueError):
            var1.get_dsa_value('upper')
        
    def test_binomial_psa(self):
        var1 = self.make_binomial_variable()
        var1.set_parameters(0.25, 4)
        rng = np.random.default_rng(123)

        n_draws = 1000
        psa_draws = np.empty(n_draws, dtype=np.int64)
        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()
        
        self.assertTrue(np.all(psa_draws == 1))
        
        activate_psa(var1)

        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()

        self.assertTrue(np.all(psa_draws >= 0))
        self.assertTrue(np.all(psa_draws <= 4)) # Expect nearly 4 in 1000
        self.assertTrue(np.min(psa_draws) == 0)
        self.assertTrue(np.max(psa_draws) == 4) 
        mean_psa = np.mean(psa_draws)
        self.assertGreater(mean_psa, 0)
        self.assertLess(mean_psa, 2)

        rng = np.random.default_rng(123)
        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()
        mean_psa_2 = np.mean(psa_draws)
        self.assertEqual(mean_psa, mean_psa_2)

    def make_normal_variable(self):
        return variable.Variable(
            'const1',
            variable_type = 'scalar',
            distribution = 'normal',
            transform = 'identity',
            parameters = [10, 2],
            dsa_lower = 6,
            dsa_upper = 14
        )
    
    def test_normal_constructors(self):
        var = variable.Variable(
            'norm1',
            variable_type = 'scalar',
            distribution = 'normal'
        )
    
    def test_normal_deterministic(self):
        var1 = self.make_normal_variable()
        
        self.assertEqual(
            var1.deterministic_value,
            10
        )

        var1.set_parameters(5, 1)
        self.assertEqual(
            var1.deterministic_value,
            5
        )

        var1.set_transform('ln')
        self.assertEqual(
            var1.deterministic_value,
            np.exp(5 + 0.5 * 1 * 1)
        )

        var1.parameterisation_index = var1.find_parameterisation(lambda x: 'mean' in x['names'])
        var1.set_parameters(5, 2)
        self.assertAlmostEqual(
            float(var1.deterministic_value),
            5.
        )

    def test_normal_dsa(self):
        var1 = self.make_normal_variable()

        for bound in ['central', 'lower', 'upper']:
            self.assertEqual(
                var1.get_dsa_value(bound), # pyright: ignore[reportArgumentType]
                10
            )
        
        activate_dsa(var1)
        
        self.assertEqual(
            var1.get_dsa_value('central'),
            10
        )
        self.assertEqual(
            var1.get_dsa_value('lower'),
            6
        )
        self.assertEqual(
            var1.get_dsa_value('upper'),
            14
        )

        var1.dsa_bounds_type = 'relative'
        var1.dsa_lower = 0.9
        var1.dsa_upper = 1.1
        self.assertEqual(
            var1.get_dsa_value('lower'),
            0.9 * 10
        )
        self.assertEqual(
            var1.get_dsa_value('upper'),
            1.1 * 10
        )

        var1.dsa_bounds_type = 'offset'
        var1.dsa_lower = -(1.96 * float(var1.parameters[1]))
        var1.dsa_upper = 1.96 * float(var1.parameters[1])

        self.assertEqual(
            var1.get_dsa_value('lower'),
            10 - 1.96 * 2
        )
        self.assertEqual(
            var1.get_dsa_value('upper'),
            10 + 1.96 * 2
        )
    
    def test_normal_psa(self):
        var1 = self.make_normal_variable()
        rng = np.random.default_rng(123)

        n_draws = 1000
        psa_draws = np.empty(n_draws, dtype=np.float64)
        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()

        self.assertTrue(np.all(psa_draws == 10))

        activate_psa(var1)

        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()

        sample_mean = np.mean(psa_draws)
        sample_sd = np.std(psa_draws)
        sem = sample_sd / np.sqrt(n_draws)
        self.assertGreater(
            sample_mean,
            var1.deterministic_value - 2 * sem
        )
        self.assertLess(
            sample_mean,
            var1.deterministic_value + 2 * sem
        )
        self.assertGreater(sample_sd, 1.9)
        self.assertLess(sample_sd, 2.1)
        
        var1.set_transform('ln')
        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()
        
        sample_mean = np.mean(psa_draws)
        sample_sd = np.std(psa_draws)
        sem = sample_sd / np.sqrt(n_draws)
        self.assertGreater(
            sample_mean,
            var1.deterministic_value - 2 * sem
        )
        self.assertLess(
            sample_mean,
            var1.deterministic_value + 2 * sem
        )

    def make_beta_variable(self):
        return variable.Variable(
            'const1',
            variable_type = 'scalar',
            distribution = 'beta',
            transform = 'identity',
            parameters = [1, 3],
            dsa_lower = 0.1,
            dsa_upper = 0.5
        )
    
    def test_beta_constructors(self):
        var = variable.Variable(
            'beta1',
            variable_type = 'scalar',
            distribution = 'beta'
        )

    def test_beta_deterministic(self):
        var1 = self.make_beta_variable()

        self.assertEqual(
            var1.deterministic_value,
            0.25
        )

        var1.parameterisation_index = var1.find_parameterisation(lambda x: 'mean' in x['names'])
        var1.set_parameters(1. / 3., 0.1)
        self.assertAlmostEqual(
            var1.deterministic_value,
            1. / 3.
        )

    def test_beta_dsa(self):
        var1 = self.make_beta_variable()

        for bound in ['central', 'lower', 'upper']:
            self.assertEqual(
                var1.get_dsa_value(bound), # pyright: ignore[reportArgumentType]
                0.25
            )
        
        activate_dsa(var1)

        self.assertEqual(
            var1.get_dsa_value('central'),
            0.25
        )
        self.assertEqual(
            var1.get_dsa_value('lower'),
            0.1
        )
        self.assertEqual(
            var1.get_dsa_value('upper'),
            0.5
        )

        var1.dsa_bounds_type = 'relative'
        var1.dsa_lower = 0.9
        var1.dsa_upper = 1.1
        self.assertEqual(
            var1.get_dsa_value('lower'),
            0.9 * 0.25
        )
        self.assertEqual(
            var1.get_dsa_value('upper'),
            1.1 * 0.25
        )
    
    def test_beta_psa(self):
        var1 = self.make_beta_variable()
        rng = np.random.default_rng(123)

        var1.parameterisation_index = var1.find_parameterisation(lambda x: 'mean' in x['names'])
        var1.set_parameters(1. / 3., 0.1)

        n_draws = 1000
        psa_draws = np.empty(n_draws, dtype=np.float64)
        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()

        self.assertTrue(np.all(psa_draws == var1.deterministic_value))

        activate_psa(var1)

        for i in range(n_draws):
            var1.draw_psa(rng)
            psa_draws[i] = var1.get_psa_value()

        sample_mean = np.mean(psa_draws)
        sample_sd = np.std(psa_draws)
        sem = sample_sd / np.sqrt(n_draws)
        self.assertGreater(
            sample_mean,
            var1.deterministic_value - 3 * sem # Slight expansion, as close enough
        )
        self.assertLess(
            sample_mean,
            var1.deterministic_value + 3 * sem # Slight expansion, as close enough
        )
        self.assertGreater(sample_sd, 0.05)
        self.assertLess(sample_sd, 0.15)

    def make_gamma_variable(self):
        return variable.Variable(
            'gamma1',
            variable_type = 'scalar',
            distribution = 'gamma',
            transform = 'identity',
            parameters = [1, 1],
            dsa_lower = 1.,
            dsa_upper = 3.
        )

    def test_gamma_deterministic(self):
        ...
        
    