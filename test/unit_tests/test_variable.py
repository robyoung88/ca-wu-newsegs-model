"""
Unit tests for newsegsbrowser/variable.
"""

import copy
from functools import partial
import json
from typing import cast
import unittest

import numpy as np
import numpy.testing as nptest
from scipy.stats import lognorm
from scipy.stats import gamma as gamma_dist
from scipy.stats import beta as beta_dist
import scipy.integrate as integrate

from test.unit_tests.common import setup_test_env
setup_test_env()

from newsegsvariable import variable
from newsegsmodel import sprakemodel
from newsegsfinance import sprakefinance

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

        dummyvar = variable.Variable('dummy') # pyright: ignore[reportAbstractUsage]

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

class TestPolymorphicFactory(unittest.TestCase):
    """
    Test that the polymorphic variable system works as intended.
    """
    
    def test_construction(self):
        const_var = variable.Variable('const var', distribution = 'constant') # pyright: ignore[reportAbstractUsage]
        binom_var = variable.Variable('binom var', distribution = 'binomial') # pyright: ignore[reportAbstractUsage]
        normal_var = variable.Variable('normal var', distribution = 'normal') # pyright: ignore[reportAbstractUsage]
        beta_var = variable.Variable('beta var', distribution = 'beta') # pyright: ignore[reportAbstractUsage]
        gamma_var = variable.Variable('gamma var', distribution = 'gamma') # pyright: ignore[reportAbstractUsage]
        constant_vector_var = variable.Variable('constant_vector var', distribution = 'constant_vector') # pyright: ignore[reportAbstractUsage]
        mvn_var = variable.Variable('mvn var', distribution = 'mvn') # pyright: ignore[reportAbstractUsage]
        dirichlet_var = variable.Variable('dirichlet var', distribution = 'dirichlet') # pyright: ignore[reportAbstractUsage]

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

class TestVariableDeterministic(unittest.TestCase):
    """
    Ensure sensible behaviour of variables for serving deterministic values
    """

    def test_constant_deterministic(self):
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'constant'
        )

        # From construction - string
        var = create_var(parameters = 'A String')
        self.assertEqual(
            var.deterministic_value,
            'A String'
        )

        # From construction - int
        var = create_var(parameters = 1)
        self.assertEqual(
            var.deterministic_value,
            1
        )

        # From construction - float
        var = create_var(parameters = 123.456)
        self.assertEqual(
            var.deterministic_value,
            123.456
        )

        # From construction - sequence (single)
        var = create_var(parameters = [123.456,])
        self.assertEqual(
            var.deterministic_value,
            123.456
        )

        # From construction - sequence (multiple)
        with self.assertRaises(TypeError):
            var = create_var(parameters = [123.456, 999.9])

        # From construction - string with log transform
        with self.assertRaises(TypeError):
            var = create_var(parameters = 'A String', transform = 'ln')
        
        # From construction - float with log
        var = create_var(parameters = 123.456, transform = 'ln')
        self.assertEqual(
            var.deterministic_value,
            np.exp(123.456)
        )

        # Change after construction - string
        var = create_var(parameters = 'A String')
        var.set_parameters('Another string')
        self.assertEqual(
            var.deterministic_value,
            'Another string'
        )

        # Change type after construction
        var = create_var(parameters = 'A String')
        var.set_parameters(123.4)
        self.assertEqual(
            var.deterministic_value,
            123.4
        )

        # Change transform after construction
        var = create_var(parameters = 'A String')
        var.set_transform('ln')
        with self.assertRaises(TypeError):
            x = var.deterministic_value
        
        var.set_parameters(123.4)
        self.assertEqual(
            var.deterministic_value,
            np.exp(123.4)
        )

        # Change type in opposite direction
        var = create_var(parameters = 123.4, transform = 'ln')
        
        with self.assertRaises(TypeError):
            var.set_parameters('A String')

        var.set_transform('identity')
        var.set_parameters('A String')
        self.assertEqual(
            var.deterministic_value,
            'A String'
        )

    def test_binom_deterministic_param1(self):
        """
        Parameterisation 1 - prob, trials
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'binomial'
        )

        # From construction
        var = create_var()
        self.assertEqual(
            var.deterministic_value,
            0
        )

        var = create_var(parameters = (0.25, 4))
        self.assertEqual(
            var.deterministic_value,
            1
        )

        var = create_var(parameters = (1, 4))
        self.assertEqual(
            var.deterministic_value,
            4
        )

        var = create_var(parameters = (0, 4))
        self.assertEqual(
            var.deterministic_value,
            0
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = (-0.2, 4))

        with self.assertRaises(ValueError):
            var = create_var(parameters = (1.2, 4))

        var = create_var(parameters = (0.25, 0))
        self.assertEqual(
            var.deterministic_value,
            0
        )
        
        with self.assertRaises(ValueError):
            var = create_var(parameters = (0.25, 4.5))
        
        # After construction
        var = create_var(parameters = (0.25, 4))
        var.set_parameters(0.5, 4)
        self.assertEqual(
            var.deterministic_value,
            2
        )

    def test_binom_deterministic_param2(self):
        """
        Parameterisation 1 - mean, trials
        """

        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'binomial',
            parameterisation_index = 1
        )

        # From construction
        var = create_var()
        self.assertEqual(
            var.deterministic_value,
            0
        )

        var = create_var(parameters = (1, 4))
        self.assertEqual(
            var.deterministic_value,
            1
        )

        var = create_var(parameters = (2, 4))
        self.assertEqual(
            var.deterministic_value,
            2
        )

        var = create_var(parameters = (0, 4))
        self.assertEqual(
            var.deterministic_value,
            0
        )

        var = create_var(parameters = (4, 4))
        self.assertEqual(
            var.deterministic_value,
            4
        )

        var = create_var(parameters = (0, 0))
        self.assertEqual(
            var.deterministic_value,
            0
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = (5, 4))
        
        # Ok to have a non-integer expected number of successes
        var = create_var(parameters = (2.5, 4))
        self.assertEqual(
            var.deterministic_value,
            int(round(4* (2.5/4)))
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = (-1, 4))

        with self.assertRaises(TypeError):
            var = create_var(parameters = ('foo', 4))

        # After construction
        var = create_var(parameters = (1, 4))
        var.set_parameters(2, 4)
        self.assertEqual(
            var.deterministic_value,
            2
        )

        # Revert parameterisation
        var.parameterisation_index = 0
        self.assertEqual(
            var.deterministic_value,
            2
        )
        var.set_parameters(0.75, 4)
        self.assertEqual(
            var.deterministic_value,
            3
        )

    def test_normal_deterministic_param1(self):
        """
        Parameterisation 1 - mean, sd
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'normal'
        )

        var = create_var()
        self.assertEqual(
            var.deterministic_value,
            0
        )

        var = create_var(parameters = (20.20, 1))
        self.assertEqual(
            var.deterministic_value,
            20.20
        )

        var = create_var(parameters = (-100, 100))
        self.assertEqual(
            var.deterministic_value,
            -100
        )

        var = create_var(parameters = (10, 0))
        self.assertEqual(
            var.deterministic_value,
            10
        )

        with self.assertRaises(TypeError):
            var = create_var(parameters = ('foo', 1))

        with self.assertRaises(ValueError):
            var = create_var(parameters = (10, -1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = 10)
        
        # After construction
        var = create_var(parameters = (10, 1))
        var.set_parameters(5,2)
        self.assertEqual(
            var.deterministic_value,
            5
        )

        # Change transform after construction
        var.set_transform('ln')
        self.assertEqual(
            var.deterministic_value,
            lognorm.mean(2, scale = np.exp(5))
        )
        self.assertAlmostEqual(
            var.deterministic_value,
            1096.633, # From R's flexsurv::mean_lnorm, the parameterisation of which I know and trust # type: ignore
            places = 2
        ) # type: ignore

    def test_normal_deterministic_param2(self):
        """
        Parameterisation 2 - lognormal with mu, sigma
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'normal',
            transform = 'ln'
        )

        var = create_var()
        self.assertEqual(
            var.parameterisation_index,
            1
        )
        self.assertEqual(
            var.deterministic_value,
            lognorm.mean(1, scale = np.exp(0))
        )

        var = create_var(parameters = (2, 3))
        self.assertEqual(
            var.deterministic_value,
            lognorm.mean(3, scale = np.exp(2))
        )

        var = create_var(parameters = (-1, 2.5))
        self.assertEqual(
            var.deterministic_value,
            lognorm.mean(2.5, scale = np.exp(-1))
        )

        var = create_var(parameters = (-1, 0))
        self.assertEqual(
            var.deterministic_value,
            np.exp(-1)
            #lognorm.mean(0, scale = np.exp(-1)) # Stats does not know how to handle the degenerate case
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = (1, -1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = ('foo', 1))
        
        with self.assertRaises(TypeError):
            var = create_var(parameters = 55)

        # After construction
        var = create_var(parameters = (2, 3))
        var.set_parameters(4, 1.5)
        self.assertEqual(
            var.deterministic_value,
            lognorm.mean(1.5, scale = np.exp(4))
        )

        # Change transform after construction
        var.set_transform('identity')
        self.assertEqual(
            var.deterministic_value,
            4
        )

    def test_normal_deterministic_param3(self):
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'normal',
            transform = 'ln',
            parameterisation_index = 2
        )
         
        var = create_var()
        self.assertEqual(
            var.deterministic_value,
            1
        )

        var = create_var(parameters = (4, 2.5))
        self.assertAlmostEqual(
            var.deterministic_value,
            4.0 # type: ignore
        ) # type: ignore

        var = create_var(parameters = (4, 0))
        self.assertAlmostEqual(
            var.deterministic_value,
            4.0 # type: ignore
        ) # type: ignore

        with self.assertRaises(ValueError):
            var = create_var(parameters = (0, 1))
        
        with self.assertRaises(ValueError):
            var = create_var(parameters = (-1, 1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = ('foo', 1))
        
        with self.assertRaises(TypeError):
            var = create_var(parameters = 55)

        # After construction
        var = create_var(parameters = (2, 3))
        var.set_parameters(4, 1.5)
        self.assertEqual(
            var.deterministic_value,
            4
        )

        # Change transform after construction
        var.set_transform('identity')
        # Immediately after this, the deterministic value will be nonsense
        var.parameterisation_index = 1
        var.set_parameters(9, 6)
        self.assertEqual(
            var.deterministic_value,
            9
        )

    def test_beta_deterministic_param1(self):
        """
        Parameterisation 1 - a, b
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'beta'
        )

        var = create_var()
        self.assertEqual(var.deterministic_value, 0.5)

        var = create_var(parameters = (2, 3))
        self.assertEqual(var.deterministic_value, 0.4)

        var = create_var(parameters = (2, 0))
        self.assertEqual(var.deterministic_value, 1)

        var = create_var(parameters = (0, 4))
        self.assertEqual(var.deterministic_value, 0)

        with self.assertRaises(ValueError):
            create_var(parameters = (-1, 1))

        with self.assertRaises(ValueError):
            create_var(parameters = (1, -1))

        with self.assertRaises(TypeError):
            create_var(parameters = ('foo', 1))
        
        with self.assertRaises(TypeError):
            create_var(parameters = 20)

        # After construction
        var = create_var(parameters = (2, 3))
        var.set_parameters(3, 1)
        self.assertEqual(var.deterministic_value, 0.75)

    def test_beta_deterministic_param2(self):
        """
        Parameterisation 2 - mean, sd
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'beta',
            parameterisation_index = 1
        )

        var = create_var()
        self.assertEqual(var.parameterisation_index, 1)
        self.assertEqual(var.deterministic_value, 0.5)

        var = create_var(parameters = (1. / 3., 0.1))
        self.assertAlmostEqual(var.deterministic_value, 1. / 3.) # type: ignore

        var = create_var(parameters = (0, 0.1))
        self.assertEqual(var.deterministic_value, 0)

        var = create_var(parameters = (1, 0.1))
        self.assertEqual(var.deterministic_value, 1)

        with self.assertRaises(ValueError):
            create_var(parameters = (1.5, 0.1))

        with self.assertRaises(TypeError):
            create_var(parameters = ('foo', 0.1))

        # After construction
        var = create_var(parameters = (1. / 3., 0.1))
        var.set_parameters(0.6, 0.15)
        self.assertAlmostEqual(var.deterministic_value, 0.6) # type: ignore

        # Revert parameterisation
        var.parameterisation_index = 0
        self.assertAlmostEqual(var.deterministic_value, 0.6) # type: ignore
        var.set_parameters(2, 1)
        self.assertAlmostEqual(var.deterministic_value, 2. / 3.) # type: ignore

    def test_beta_deterministic_param3(self):
        """
        Parameterisation 3 - a_log, b_log
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'beta',
            transform = 'ln',
            parameterisation_index = 2
        )

        var = create_var()
        self.assertEqual(var.parameterisation_index, 2)
        self.assertAlmostEqual(var.deterministic_value, beta_dist.expect(np.exp, (1,1)))

        var = create_var(parameters = (2.5, 0.75))
        self.assertAlmostEqual(var.deterministic_value, beta_dist.expect(np.exp, (2.5, 0.75)))

        with self.assertRaises(TypeError):
            create_var(parameters = ('foo', 1))

        with self.assertRaises(TypeError):
            create_var(parameters = 55)

        var = create_var(parameters = (2.5, 0.75))
        var.set_parameters(1.2, 0.8)
        self.assertAlmostEqual(var.deterministic_value, beta_dist.expect(np.exp, (1.2, 0.8)))

        var.set_transform('identity')
        var.parameterisation_index = 1
        var.set_parameters(0.3, 0.1)
        self.assertAlmostEqual(var.deterministic_value, 0.3) # type: ignore

    def test_gamma_deterministic_param1(self):
        """
        Parameterisation 1 - shape, scale
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'gamma'
        )

        var = create_var()
        self.assertEqual(
            var.deterministic_value,
            1
        )

        var = create_var(parameters = (5, 2))
        self.assertEqual(
            var.deterministic_value,
            10
        )

        var = create_var(parameters = (20.20, 0))
        self.assertEqual(
            var.deterministic_value,
            0
        )

        # This break from gamma behaviour to allow for constant values to be used.
        var = create_var(parameters = (0, 2))
        self.assertEqual(
            var.deterministic_value,
            2
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = (-1, 2))
        
        with self.assertRaises(ValueError):
            var = create_var(parameters = (2, -1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = ('foo', 1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = 10)

        # After construction
        var = create_var(parameters = (10, 2.5))
        var.set_parameters(5,1.2)
        self.assertEqual(
            var.deterministic_value,
            5*1.2
        )

    def test_gamma_deterministic_param2(self):
        """
        Parameterisation 2 - gamma with mean, sd
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'gamma',
            parameterisation_index = 1
        )

        var = create_var()
        self.assertEqual(
            var.deterministic_value,
            1
        )

        var = create_var(parameters = (5, 2))
        self.assertEqual(
            var.deterministic_value,
            5
        )

        #with self.assertRaises(ValueError):
        var = create_var(parameters = (0, 2))
        self.assertEqual(
            var.deterministic_value,
            0
        )

        #with self.assertRaises(ValueError):
        var = create_var(parameters = (20.20, 0.0))
        self.assertEqual(
            var.deterministic_value,
            20.2
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = (-1, 2))
        
        with self.assertRaises(ValueError):
            var = create_var(parameters = (2, -1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = ('foo', 1))

        with self.assertRaises(TypeError):
            var = create_var(parameters = 10)

        # After construction
        var = create_var(parameters = (10, 2.5))
        var.set_parameters(5,1.2)
        self.assertEqual(
            var.deterministic_value,
            5
        )

        # Reversion of parameterisation
        var.parameterisation_index = 0
        self.assertEqual(
            var.deterministic_value,
            5
        )
        var.set_parameters(5,1.2)
        self.assertEqual(
            var.deterministic_value,
            5 * 1.2
        )
    
    def test_gamma_deterministic_param3(self):
        """
        Parameterisation 3 - loggamma with shape, scale of underlying gamma

        NB - this relies on quadrature and often results in numeric overflow.
        """ 
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'gamma',
            transform = 'ln'
        )
        var = create_var()
        self.assertEqual(
            var.parameterisation_index,
            2
        )
        self.assertEqual(
            var.deterministic_value,
            integrate.quad(lambda x: 1 - gamma_dist.cdf(np.log(x), a = 1, scale = 1), 0, np.inf)[0]
            #gamma_dist.expect(np.exp, (1,), scale = 1)
        )
        
        var = create_var(parameters = (4, 2.5))
        self.assertEqual(
            var.deterministic_value,
            integrate.quad(lambda x: 1 - gamma_dist.cdf(np.log(x), a = 4, scale = 2.5), 0, np.inf)[0]
            #gamma_dist.expect(np.exp, (4,), scale = 2.5) # Absurd that scale is an int. # pyright: ignore[reportArgumentType]
        )

        # That will do - the loggamma has some numeric issues and is not a priority

    def test_constant_vector_deterministic(self):
        _create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'constant_vector'
        )
        create_var = lambda **kwargs: cast(variable.VectorVariable, _create_var(**kwargs))

        var = create_var()
        
        self.assertListEqual(
            list(var.deterministic_value),
            [1]
        )

        var = create_var(parameters = 'A String')
        self.assertListEqual(
            list(var.deterministic_value),
            ['A String']
        )

        var = create_var(parameters = ['A String', 'Another String'])
        self.assertListEqual(
            list(var.deterministic_value),
            ['A String', 'Another String']
        )

        var = create_var(parameters = ['A String', 12])
        self.assertListEqual(
            list(var.deterministic_value),
            ['A String', 12]
        )

        var = create_var(parameters = [['This is the preferred form', 19], ])
        self.assertListEqual(
            list(var.deterministic_value),
            ['This is the preferred form', 19]
        )


        var = create_var(parameters = np.asarray([1,2,3]))
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([1,2,3])
        )

        var = create_var(parameters = np.asarray([1,2,3]), transform = 'ln')
        nptest.assert_array_equal(
            var.deterministic_value,
            np.exp(np.asarray([1,2,3]))
        )

        var = create_var(
            parameters = np.asarray([1,2,3]),
            transform = ('ln', 'identity', 'ln')
        )
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([np.exp(1),2,np.exp(3)])
        )

        # Change after construction
        var.set_transform('identity')
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([1,2,3])
        )
        var.set_parameters(['A sequence', 3])
        self.assertListEqual(
            list(var.deterministic_value),
            ['A sequence', 3]
        )
        
        var.set_parameters('Not', 'a', 'sequence')
        self.assertListEqual(
            list(var.deterministic_value),
            ['Not', 'a', 'sequence']
        )

        var.set_parameters(['Item1List1', 'Item2List1'], ['Item1List2', 'Item2List2'])
        self.assertListEqual(
            list(var.deterministic_value),
            [['Item1List1', 'Item2List1'], ['Item1List2', 'Item2List2']]
        )

    def test_mvn_deterministic_param1(self):
        """
        Parameterisation 1 - mean, vcv
        """
        _create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'mvn'
        )
        create_var = lambda **kwargs: cast(variable.NumericVectorVariable, _create_var(**kwargs))

        var = create_var()
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0,0])
        )

        var = create_var(parameters = ([1,2], [[1,0],[0,1]]))
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([1,2])
        )
        means, vcv = var.parameters
        nptest.assert_array_equal(
            means,
            np.asarray([1,2], dtype = np.float64),
            strict=True
        )
        nptest.assert_array_equal(
            vcv,
            np.asarray([[1,0],[0,1]], dtype = np.float64),
            strict=True
        )

        var.set_parameters([5,3], np.asarray([[0.5,0.2,0.2,0.3]]))
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([5,3])
        )

    def test_mvn_deterministic_param2(self):
        """
        Parameterisation 2 - all lognormal with mu, vcv
        """
        _create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'mvn',
            transform = 'ln'
        )
        create_var = lambda **kwargs: cast(variable.NumericVectorVariable, _create_var(**kwargs))

        var = create_var()
        self.assertEqual(
            var.parameterisation_index,
            1
        )
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([
                lognorm.mean(1, scale = np.exp(0)),
                lognorm.mean(1, scale = np.exp(0))
            ])
        )
        
        var = create_var(
            parameters = (
                [-1, 1],
                np.asarray([[0.25,0.1],[0.1,0.3]])
            )
        )
        nptest.assert_array_almost_equal(
            var.deterministic_value,
            np.asarray([
                lognorm.mean(np.sqrt(0.25), scale = np.exp(-1)),
                lognorm.mean(np.sqrt(0.3), scale = np.exp(1))
            ])
        )

    def test_mvn_deterministic_param3(self):
        """
        Parameterisation 3 - mixed (log) normal with mu, vcv
        """
        _create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'mvn',
            transform = 'ln',
            parameterisation_index = 2
        )
        create_var = lambda **kwargs: cast(variable.NumericVectorVariable, _create_var(**kwargs))

        var = create_var()
        self.assertEqual(
            var.parameterisation_index,
            2
        )
        self.assertTupleEqual(
            var.transform,
            ('ln', 'ln')
        )
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([
                1,
                1
            ])
        )
        var.set_transform('identity')
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([
                np.log(1)- 0.5*1**2,
                np.log(1)- 0.5*1**2
            ])
        )
        var.set_transform(('identity','ln'))
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([
                np.log(1)- 0.5*1**2,
                1
            ])
        )

    def test_dirichlet_deterministic_param1(self):
        """
        Parameterisation 1 - alpha
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'dirichlet'
        )

        var = create_var()
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0.5,0.5])
        )

        var = create_var(parameters = [[5,3,2]])
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0.5, 0.3, 0.2])
        )

        var = create_var(parameters = [[5,3,0,2]])
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0.5, 0.3, 0.0, 0.2])
        )

        with self.assertRaises(TypeError):
            var = create_var(parameters = [5,3,0,2])
        
        var = create_var(parameters = [[5,3,0,2]])
        var.set_parameters([3,2])
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0.6,0.4])
        )
    
    def test_dirichlet_deterministic_param2(self):
        """
        Parameterisation 2 - mean, vcv
        """
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'dirichlet',
            parameterisation_index = 1
        )

        var = create_var()
        self.assertEqual(
            var.parameterisation_index,
            1
        )
        self.assertTupleEqual(
            var.parameterisation.names,
            ('mean', 'vcv')
        )
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0.5,0.5])
        )

        with self.assertRaises(ValueError):
            var = create_var(parameters = [[0.125,0.75], np.matrix([[0.1,0.05,0.05,0.02]])])
        
        with self.assertRaises(ValueError):
            var = create_var(parameters = [[0.125,0.75,0.125], np.matrix([[0.1,0.05,0.05,0.02]])])
        
        def dvar(x,s):
            return ((x/s)*(1.-x/s))/(s+1)
        def dcov(x,y,s):
            return ((x/s) - (x/s)*(y/s))/(s+1)

        var = create_var(parameters = [[0.125,0.75,0.125], 
                                       np.matrix([[
                                           dvar(1,8), dcov(1,6,8), dcov(1,1,8),
                                           dcov(6,1,8), dvar(6,8), dcov(6,1,8),
                                           dcov(1,1,8), dcov(1,6,8), dvar(1,8)]])])
        nptest.assert_array_equal(
            var.deterministic_value,
            np.asarray([0.125,0.75,0.125])
        )

class TestVariablePSA(unittest.TestCase):

    def test_binom_psa(self):
        true_mean = 33.33

        var = variable.Variable(
            'Variable name',
            distribution = 'binomial',
            parameterisation_index=1,
            parameters = (true_mean, 100)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)

        mn = oarray.mean()
        std = oarray.std()
        self.assertGreater(
            mn,
            true_mean * 0.9
        )
        self.assertLess(
            mn,
            true_mean * 1.1
        )

        var.dsa_bounds_type = 'interval'
        interval_width = 0.9
        var.dsa_lower = interval_width
        var.dsa_upper = interval_width

        var = cast(variable.NumericScalarVariable, var)

        lb = float(var.get_dsa_value('lower', True))
        ub = float(var.get_dsa_value('upper', True))
        in_bound = np.logical_and(
            oarray >= lb,
            oarray <= ub
        )

        p_in_bound = in_bound.sum() / n_sample
        self.assertGreater(p_in_bound, interval_width - 0.02)
        self.assertLess(p_in_bound, interval_width + 0.02)

    def test_normal_psa(self):
        true_mean = 3.33
        true_sd = 0.7

        var = variable.Variable(
            'Variable name',
            distribution = 'normal',
            parameterisation_index=0,
            parameters = (true_mean, true_sd)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)

        mn = oarray.mean()
        std = oarray.std()
        se = std / np.sqrt(n_sample)
        self.assertGreater(
            mn,
            true_mean - 1.96 * se
        )
        self.assertLess(
            mn,
            true_mean + 1.96 * se
        )

        self.assertGreater(
            std,
            true_sd * 0.9
        )
        self.assertLess(
            std,
            true_sd * 1.1
        )

        var.dsa_bounds_type = 'interval'
        interval_width = 0.9
        var.dsa_lower = interval_width
        var.dsa_upper = interval_width

        var = cast(variable.NumericScalarVariable, var)

        lb = float(var.get_dsa_value('lower', True))
        ub = float(var.get_dsa_value('upper', True))
        in_bound = np.logical_and(
            oarray >= lb,
            oarray <= ub
        )

        p_in_bound = in_bound.sum() / n_sample
        self.assertGreater(p_in_bound, interval_width - 0.02)
        self.assertLess(p_in_bound, interval_width + 0.02)

    def test_lognormal_psa(self):
        true_mean = 3.33
        true_sd = 0.7

        var = variable.Variable(
            'Variable name',
            distribution = 'normal',
            transform = 'ln',
            parameterisation_index=2,
            parameters = (true_mean, true_sd)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)

        mn = oarray.mean()
        std = oarray.std()
        se = std / np.sqrt(n_sample)
        self.assertGreater(
            mn,
            true_mean - 1.96 * se
        )
        self.assertLess(
            mn,
            true_mean + 1.96 * se
        )

        self.assertGreater(
            std,
            true_sd * 0.9
        )
        self.assertLess(
            std,
            true_sd * 1.1
        )

        var.dsa_bounds_type = 'interval'
        interval_width = 0.9
        var.dsa_lower = interval_width
        var.dsa_upper = interval_width

        var = cast(variable.NumericScalarVariable, var)

        lb = float(var.get_dsa_value('lower', True))
        ub = float(var.get_dsa_value('upper', True))
        in_bound = np.logical_and(
            oarray >= lb,
            oarray <= ub
        )

        p_in_bound = in_bound.sum() / n_sample
        self.assertGreater(p_in_bound, interval_width - 0.02)
        self.assertLess(p_in_bound, interval_width + 0.02)

    def test_beta_psa(self):
        true_mean = 0.33
        true_sd = 0.12

        var = variable.Variable(
            'Variable name',
            distribution = 'beta',
            parameterisation_index=1,
            parameters = (true_mean, true_sd)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)

        mn = oarray.mean()
        std = oarray.std()
        se = std / np.sqrt(n_sample)
        # This normal approximation may not work
        self.assertGreater(
            mn,
            true_mean - 1.96 * se
        )
        self.assertLess(
            mn,
            true_mean + 1.96 * se
        )

        self.assertGreater(
            std,
            true_sd * 0.9
        )
        self.assertLess(
            std,
            true_sd * 1.1
        )

        var.dsa_bounds_type = 'interval'
        interval_width = 0.9
        var.dsa_lower = interval_width
        var.dsa_upper = interval_width

        var = cast(variable.NumericScalarVariable, var)

        lb = float(var.get_dsa_value('lower', True))
        ub = float(var.get_dsa_value('upper', True))
        in_bound = np.logical_and(
            oarray >= lb,
            oarray <= ub
        )

        p_in_bound = in_bound.sum() / n_sample
        self.assertGreater(p_in_bound, interval_width - 0.02)
        self.assertLess(p_in_bound, interval_width + 0.02)

    def test_logbeta_psa(self):
        var = variable.Variable(
            'Variable name',
            distribution = 'beta',
            transform = 'ln'
        ) # pyright: ignore[reportAbstractUsage]

        true_mean = var.deterministic_value
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 5000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)

        mn = oarray.mean()
        std = oarray.std()
        se = std / np.sqrt(n_sample)
        # This normal approximation may not work - requires large number of samples
        self.assertGreater(
            mn,
            true_mean - 1.96 * se
        )
        self.assertLess(
            mn,
            true_mean + 1.96 * se
        )

        #TODO: Get the Log-beta interval evaluation check.
        # Probably worth changing the interval function signature to match the vector type
        # so the transform check can happen within the interval function rather than the
        # main Distribution class

    def test_gamma_psa(self):
        true_mean = 3.33
        true_sd = 0.7

        var = variable.Variable(
            'Variable name',
            distribution = 'gamma',
            parameterisation_index=1,
            parameters = (true_mean, true_sd)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)

        mn = oarray.mean()
        std = oarray.std()
        se = std / np.sqrt(n_sample)
        self.assertGreater(
            mn,
            true_mean - 1.96 * se
        )
        self.assertLess(
            mn,
            true_mean + 1.96 * se
        )

        self.assertGreater(
            std,
            true_sd * 0.9
        )
        self.assertLess(
            std,
            true_sd * 1.1
        )

        var.dsa_bounds_type = 'interval'
        interval_width = 0.9
        var.dsa_lower = interval_width
        var.dsa_upper = interval_width

        var = cast(variable.NumericScalarVariable, var)

        lb = float(var.get_dsa_value('lower', True))
        ub = float(var.get_dsa_value('upper', True))
        in_bound = np.logical_and(
            oarray >= lb,
            oarray <= ub
        )

        p_in_bound = in_bound.sum() / n_sample
        self.assertGreater(p_in_bound, interval_width - 0.02)
        self.assertLess(p_in_bound, interval_width + 0.02)

    def test_logamma_psa(self):

        var = variable.Variable(
            'Variable name',
            distribution = 'gamma',
            transform = 'ln',
            parameterisation_index=2,
            parameters = (1.2, 0.2)
        ) # pyright: ignore[reportAbstractUsage]

        true_mean = var.deterministic_value
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000
        oarray = np.empty(n_sample, dtype = np.float64)
        for i in range(n_sample):
            oarray[i] = var.draw_psa(rng)
        oarray = oarray[np.logical_not(np.isinf(oarray))]
        n_sample = len(oarray)

        mn = oarray.mean()
        std = oarray.std()
        se = std / np.sqrt(n_sample)
        self.assertGreater(
            mn,
            true_mean - 1.96 * se
        )
        self.assertLess(
            mn,
            true_mean + 1.96 * se
        )
        
        var.dsa_bounds_type = 'interval'
        interval_width = 0.9
        var.dsa_lower = interval_width
        var.dsa_upper = interval_width

        var = cast(variable.NumericScalarVariable, var)

        lb = float(var.get_dsa_value('lower', True))
        ub = float(var.get_dsa_value('upper', True))
        in_bound = np.logical_and(
            oarray >= lb,
            oarray <= ub
        )

        p_in_bound = in_bound.sum() / n_sample
        self.assertGreater(p_in_bound, interval_width - 0.02)
        self.assertLess(p_in_bound, interval_width + 0.02)

    def test_mvn_psa(self):

        true_means = np.asarray((3.33, 1.23), dtype = np.float64)
        true_sds = np.asarray((0.7, 0.33))
        true_vcv = np.asarray([[true_sds[0]**2, 0.25],[0.25, true_sds[1]**2]], dtype = np.float64)

        var = variable.Variable(
            'Variable name',
            distribution = 'mvn',
            parameterisation_index=0,
            parameters = (true_means, true_vcv)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 5000 # Bumping up the number of samples to ensure SD comes within arbitrary bounds
        oarray = np.empty(n_sample*len(true_means), dtype = np.float64).reshape((n_sample, -1))
        for i in range(n_sample):
            oarray[i, :] = var.draw_psa(rng)

        mn = oarray.mean(axis = 0)
        std = oarray.std(axis = 0)
        se = std / np.sqrt(n_sample)
        nptest.assert_array_less(
            true_means - 1.96 * se,
            mn
        )
        nptest.assert_array_less(
            mn,
            true_means + 1.96 * se
        )

        nptest.assert_array_less(
            true_sds * 0.9,
            std
        )
        nptest.assert_array_less(
            std,
            true_sds * 1.1
        )

    def test_mvln_psa(self):

        true_means = np.asarray((3.33, 1.23), dtype = np.float64)
        true_sds = np.asarray((0.7, 0.33))
        true_vcv = np.asarray([[true_sds[0]**2, 0.25],[0.25, true_sds[1]**2]], dtype = np.float64)

        var = variable.Variable(
            'Variable name',
            distribution = 'mvn',
            transform = 'ln',
            parameterisation_index=2,
            parameters = (true_means, true_vcv)
        ) # pyright: ignore[reportAbstractUsage]
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000 
        oarray = np.empty(n_sample*len(true_means), dtype = np.float64).reshape((n_sample, -1))
        for i in range(n_sample):
            oarray[i, :] = var.draw_psa(rng)

        mn = oarray.mean(axis = 0)
        std = oarray.std(axis = 0)
        se = std / np.sqrt(n_sample)
        nptest.assert_array_less(
            true_means - 1.96 * se,
            mn
        )
        nptest.assert_array_less(
            mn,
            true_means + 1.96 * se
        )

        # The VCV is on the log scale, so we can't compare the sds

    def test_mixed_mvn_psa(self):

        true_means = np.asarray((3.33, 1.23), dtype = np.float64)
        true_sds = np.asarray((0.7, 0.33))
        true_vcv = np.asarray([[true_sds[0]**2, 0.25],[0.25, true_sds[1]**2]], dtype = np.float64)

        var = cast(
            variable.VectorVariable,
            variable.Variable(
                'Variable name',
                distribution = 'mvn',
                transform = ('identity','ln'),
                parameterisation_index=2,
                parameters = (true_means, true_vcv)
            ) # pyright: ignore[reportAbstractUsage]
        )
        
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000 
        oarray = np.empty(n_sample*len(true_means), dtype = np.float64).reshape((n_sample, -1))
        for i in range(n_sample):
            oarray[i, :] = var.draw_psa(rng)

        mn = oarray.mean(axis = 0)
        std = oarray.std(axis = 0)
        se = std / np.sqrt(n_sample)

        nptest.assert_array_almost_equal(
            true_means,
            np.asarray(var.deterministic_value)
        )
        self.assertTrue(
            any(mn1 != mn2 for mn1, mn2 in zip(var.deterministic_value, np.asarray(var.parameters[0])))
        )
        self.assertFalse(
            all(mn1 != mn2 for mn1, mn2 in zip(var.deterministic_value, np.asarray(var.parameters[0])))
        )

        nptest.assert_array_less(
            true_means - 1.96 * se,
            mn
        )
        nptest.assert_array_less(
            mn,
            true_means + 1.96 * se
        )

        # The VCV is on the log scale for transformed parameters, so we can't compare the sds

    def test_dirichlet_psa(self):

        true_alphas = np.asarray((4,16,2))

        var = cast(
            variable.VectorVariable,
            variable.Variable(
                'Variable name',
                distribution = 'dirichlet',
                parameterisation_index=0,
                parameters = (true_alphas,)
            ) # pyright: ignore[reportAbstractUsage]
        )
        

        true_means = var.deterministic_value
        activate_psa(var)
        rng = np.random.default_rng(123)
        n_sample = 1000 
        oarray = np.empty(n_sample*len(true_means), dtype = np.float64).reshape((n_sample, -1))
        for i in range(n_sample):
            oarray[i, :] = var.draw_psa(rng)

        mn = oarray.mean(axis = 0)
        std = oarray.std(axis = 0)
        se = std / np.sqrt(n_sample)
        nptest.assert_array_less(
            true_means - 1.96 * se,
            mn
        )
        nptest.assert_array_less(
            mn,
            true_means + 1.96 * se
        )


class TestVariableConstructionFromJSON(unittest.TestCase):
    """
    Ensure that variables handle being constructed from a json file correctly
    """

    def test_sprake_json_construction(self):
        with open('data/sprake-variable-config-novalues.json') as f:
            var_conf_list = json.load(f)
        
        self.assertIsInstance(var_conf_list, list)
        variables = [variable.Variable(**x) for x in var_conf_list] # pyright: ignore[reportAbstractUsage]
        for var in variables:
            self.assertIsInstance(var, variable.Variable)

class TestVariableSynchronisation(unittest.TestCase):
    """
    Check synchronisation with model/finance instances
    """

    def load_sprake_variables(self):
        with open('data/sprake-variable-config-novalues.json') as f:
            var_conf_list = json.load(f)
        return [variable.Variable(**x) for x in var_conf_list] # pyright: ignore[reportAbstractUsage]
    
    def test_synchronisation_scalar_constant(self):
        vars = self.load_sprake_variables()
        mdl = sprakemodel.SprakeModel.from_none()

        vbl = [x for x in vars if x.model_parameter == 'storage_capacity'][0]
        self.assertEqual(vbl.model_parameter, 'storage_capacity')
        self.assertNotEqual(vbl.deterministic_value, mdl.consumption_storage.storage_params['storage_capacity'])
        vbl.synchronise_from_model(mdl)
        self.assertEqual(vbl.deterministic_value, mdl.consumption_storage.storage_params['storage_capacity'])

    def test_synchronisation_scalar_beta(self):
        vars = self.load_sprake_variables()
        mdl = sprakemodel.SprakeModel.from_none()

        vbl = [x for x in vars if x.model_parameter == 'storage_rte'][0]
        self.assertEqual(vbl.model_parameter, 'storage_rte')
        self.assertNotEqual(vbl.deterministic_value, mdl.consumption_storage.storage_params['storage_rte'])
        vbl.synchronise_from_model(mdl)
        self.assertAlmostEqual(vbl.deterministic_value, mdl.consumption_storage.storage_params['storage_rte'])
    
    def test_synchronisation_scalar_normal(self):
        vars = self.load_sprake_variables()
        mdl = sprakemodel.SprakeModel.from_none()

        vbl = [x for x in vars if x.model_parameter == 'hlp'][0]
        self.assertEqual(vbl.model_parameter, 'hlp')
        self.assertNotEqual(vbl.deterministic_value, mdl.consumption_storage.spaceheat_params['hlp'])
        vbl.synchronise_from_model(mdl)
        self.assertAlmostEqual(vbl.deterministic_value, mdl.consumption_storage.spaceheat_params['hlp'])

    def test_synchronisation_scalar_gamma(self):
        vars = self.load_sprake_variables()
        fnc = sprakefinance.SprakeFinance.from_none()

        vbl = [x for x in vars if x.model_parameter == 'resident_var_per_unit'][0]
        self.assertEqual(vbl.model_parameter, 'resident_var_per_unit')
        self.assertNotEqual(vbl.deterministic_value, fnc.unit_costs['resident_var_per_unit'])
        vbl.synchronise_from_model(fnc)
        self.assertAlmostEqual(vbl.deterministic_value, fnc.unit_costs['resident_var_per_unit'])

    def test_update_function(self):
        """
        Verify the behaviour of update_model_with_value
        """
        mdl = sprakemodel.SprakeModel.from_none()
        self.assertNotEqual(
            mdl.consumption_storage.storage_params['storage_capacity'],
            100.0
        )
        variable.update_model_with_value(
            100.0,
            mdl,
            'mod_cs._storage_params',
            'storage_capacity'
        )
        self.assertEqual(
            mdl.consumption_storage.storage_params['storage_capacity'],
            100.0
        )

        fnc = sprakefinance.SprakeFinance.from_none()
        self.assertNotEqual(
            fnc.unit_costs['grid_import_sc_per_day'],
            25
        )
        variable.update_model_with_value(
            25,
            fnc,
            '_unit_costs',
            'grid_import_sc_per_day'
        )
        self.assertEqual(
            fnc.unit_costs['grid_import_sc_per_day'],
            25
        )

    def test_update_det_scalar_constant(self):
        vars = self.load_sprake_variables()
        mdl = sprakemodel.SprakeModel.from_none()

        vbl = [x for x in vars if x.model_parameter == 'storage_capacity'][0]
        self.assertEqual(vbl.model_parameter, 'storage_capacity')
        vbl.synchronise_from_model(mdl)
        self.assertNotEqual(
            mdl.consumption_storage.storage_params['storage_capacity'], 
            100
        )
        vbl.set_parameters(100)
        vbl.update_model(mdl)
        self.assertEqual(
            mdl.consumption_storage.storage_params['storage_capacity'], 
            100
        )
        
    def test_update_det_scalar_beta(self):
        vars = self.load_sprake_variables()
        mdl = sprakemodel.SprakeModel.from_none()

        vbl = [x for x in vars if x.model_parameter == 'storage_rte'][0]
        self.assertEqual(vbl.model_parameter, 'storage_rte')
        vbl.synchronise_from_model(mdl)
        self.assertNotEqual(
            mdl.consumption_storage.storage_params['storage_rte'], 
            0.8
        )
        self.assertEqual(vbl.parameterisation_index, 1)
        vbl.set_parameters(0.8, 0.1)
        vbl.update_model(mdl)
        self.assertEqual(
            mdl.consumption_storage.storage_params['storage_rte'], 
            0.8
        )
    
    def test_update_det_scalar_normal(self):
        vars = self.load_sprake_variables()
        mdl = sprakemodel.SprakeModel.from_none()

        vbl = [x for x in vars if x.model_parameter == 'hlp'][0]
        self.assertEqual(vbl.model_parameter, 'hlp')
        vbl.synchronise_from_model(mdl)
        self.assertNotEqual(
            mdl.consumption_storage.spaceheat_params['hlp'], 
            0.5
        )
        vbl.set_parameters(0.5, 0.02)
        vbl.update_model(mdl)
        self.assertEqual(
            mdl.consumption_storage.spaceheat_params['hlp'],
            0.5
        )
    
    def test_update_det_scalar_gamma(self):
        vars = self.load_sprake_variables()
        fnc = fnc = sprakefinance.SprakeFinance.from_none()

        vbl = [x for x in vars if x.model_parameter == 'resident_var_per_unit'][0]
        self.assertEqual(vbl.model_parameter, 'resident_var_per_unit')
        vbl.synchronise_from_model(fnc)
        self.assertNotEqual(
            fnc.unit_costs['resident_var_per_unit'], 
            0.33
        )
        self.assertEqual(vbl.parameterisation_index, 1)
        vbl.set_parameters(0.33, 0.05)
        vbl.update_model(fnc)
        self.assertEqual(
            fnc.unit_costs['resident_var_per_unit'],
            0.33
        )

class TestVariableSerialisation(unittest.TestCase):
    """
    Check serialisation of variables
    """

    # NB - using from_dict form here, not direct construction.
    # This allows us to hold onto e.g. raw_parameters
    def load_sprake_variables(self):
        with open('data/sprake-variable-config.json') as f:
            var_conf_list = json.load(f)
        return [variable.variable_from_dict(x) for x in var_conf_list]
    
    def test_synchronisation_scalar_constant(self):
        vars = self.load_sprake_variables()
        
        vbl = [x for x in vars if x.model_parameter == 'storage_capacity'][0]
        self.assertEqual(vbl.distribution.distribution, 'numeric_constant')
        self.assertEqual(vbl.name, 'Storage capacity')
        
        self.assertTupleEqual(vbl._raw_parameters, (4000,))
    
class TestVariableCopy(unittest.TestCase):
    """
    Check copy behaviour of variables
    """

    def test_deep_copy(self):
        create_var = partial(
            variable.Variable,
            'Variable name',
            distribution = 'normal'
        )

        var = create_var(parameters = (5,2))
        self.assertEqual(
            var.deterministic_value,
            5
        )

        varlist = [var]

        varlist_2 = copy.deepcopy(varlist)
        self.assertEqual(
            varlist_2[0].deterministic_value,
            5
        )
        varlist_2[0].set_parameters(10,1)
        self.assertEqual(
            varlist_2[0].deterministic_value,
            10
        )
        self.assertEqual(
            varlist[0].deterministic_value,
            5
        )

class TestVariableReset(unittest.TestCase):
    """
    Check the reset behaviour of variables
    """

    def test_scalar_reset(self):
        create_var = partial(
            variable.Variable,
            'Spam',
            distribution = 'normal'
        )

        var = create_var(parameters = (5, 2))
        self.assertListEqual(
            list(var.parameters),
            [5, 2]
        )

        var.set_parameters(10, 3)
        self.assertListEqual(
            list(var.parameters),
            [10, 3]
        )

        var.reset_parameters()
        self.assertListEqual(
            list(var.parameters),
            [5, 2]
        )

        var.set_parameters(10, 3)
        var.reset_parameters(0)
        self.assertListEqual(
            list(var.parameters),
            [5, 3]
        )

class TestVariableValidation(unittest.TestCase):
    """
    Ensure that Variables handle creation and sampling correctly
    """
    def make_constant_variable(self):
        return variable.Variable(
            'const1',
            distribution = 'constant',
            transform = 'identity',
            parameters = 'String Constant',
            dsa_lower = 'Different String',
            dsa_upper = 'Another Different String'
        ) # pyright: ignore[reportAbstractUsage]
    
    def make_constant_variable_numeric(self):
        return variable.Variable(
            'const2',
            distribution = 'constant',
            transform = 'identity',
            parameters = 12.34,
            dsa_lower = 9.9,
            dsa_upper = 20
        ) # pyright: ignore[reportAbstractUsage]
    
    def test_constant_constructors(self):
        var = variable.Variable('aconst') # pyright: ignore[reportAbstractUsage]

        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('lower', True)
        )
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('upper', True)
        )

        var = variable.Variable('aconst', dsa_bounds_type='relative') # pyright: ignore[reportAbstractUsage]
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('lower', True)
        )
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('upper', True)
        )

        var = variable.Variable('aconst', dsa_bounds_type='offset') # pyright: ignore[reportAbstractUsage]
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('lower', True)
        )
        self.assertEqual(
            var.deterministic_value,
            var.get_dsa_value('upper', True)
        )

        var = variable.Variable('aconst', parameters = 'A string') # pyright: ignore[reportAbstractUsage]
        self.assertEqual(
            var.deterministic_value,
            'A string'
        )

        var = variable.Variable(
            'aconst',
            parameters = ('A string',)
        ) # pyright: ignore[reportAbstractUsage]
        self.assertEqual(
            var.deterministic_value,
            'A string'
        )
        
        with self.assertRaises(TypeError):
            var = variable.Variable(
                'aconst',
                parameters = 'A string',
                transform = 'ln',
                dsa_bounds_type = 'relative'
            ) # pyright: ignore[reportAbstractUsage]
        
        var = variable.Variable(
                'aconst',
                parameters = 'A string',
                dsa_bounds_type = 'relative',
                dsa_lower = 0.9,
                dsa_upper = 1.1
            ) # pyright: ignore[reportAbstractUsage]
        
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
            distribution = 'constant',
            transform = 'identity',
            parameters = 'String Constant'
        ) # pyright: ignore[reportAbstractUsage]

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
        
        with self.assertRaises(TypeError):
            """
            Cannot use a log transform with a string constant
            """
            var1 = variable.Variable(
                'const1',
                distribution = 'constant',
                transform = 'ln',
                parameters = 'String Constant'
            ) # pyright: ignore[reportAbstractUsage]

    def make_binomial_variable(self):
        return variable.Variable(
            'const1',
            distribution = 'binomial',
            transform = 'identity',
            parameters = [0.2, 5],
            dsa_lower = 0,
            dsa_upper = 3
        ) # pyright: ignore[reportAbstractUsage]
    
    def test_binomial_constructors(self):
        var = variable.Variable(
            'abinom',
            distribution = 'binomial'
        ) # pyright: ignore[reportAbstractUsage]

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
            distribution = 'normal',
            transform = 'identity',
            parameters = [10, 2],
            dsa_lower = 6,
            dsa_upper = 14
        ) # pyright: ignore[reportAbstractUsage]
    
    def test_normal_constructors(self):
        var = variable.Variable(
            'norm1',
            distribution = 'normal'
        ) # pyright: ignore[reportAbstractUsage]
    
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

        var1.parameterisation_index = var1.find_parameterisation(lambda x: 'mean' in x.names)
        var1.set_parameters(5, 2)
        var1 = cast(variable.NumericScalarVariable, var1)
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

        var1 = cast(variable.NumericScalarVariable, var1)

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
            distribution = 'beta',
            transform = 'identity',
            parameters = [1, 3],
            dsa_lower = 0.1,
            dsa_upper = 0.5
        ) # pyright: ignore[reportAbstractUsage]
    
    def test_beta_constructors(self):
        var = variable.Variable(
            'beta1',
            distribution = 'beta'
        ) # pyright: ignore[reportAbstractUsage]

    def test_beta_deterministic(self):
        var1 = self.make_beta_variable()

        self.assertEqual(
            var1.deterministic_value,
            0.25
        )

        var1.parameterisation_index = var1.find_parameterisation(lambda x: 'mean' in x.names)
        var1 = cast(variable.NumericScalarVariable, var1)
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

        var1.parameterisation_index = var1.find_parameterisation(lambda x: 'mean' in x.names)
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
            distribution = 'gamma',
            transform = 'identity',
            parameters = [1, 1],
            dsa_lower = 1.,
            dsa_upper = 3.
        ) # pyright: ignore[reportAbstractUsage]

    def test_gamma_deterministic(self):
        ...
        
    