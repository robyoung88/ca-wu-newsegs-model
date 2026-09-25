"""
Unit tests for stats/dirichlet.
"""
import unittest

import numpy as np
import numpy.testing as nptest
from scipy.stats import dirichlet

from newsegsmodelframework.newsegsstats.dirichlet import fit_dirichlet

class TestDirichletFitting(unittest.TestCase):
    """
    Check the behaviour of the dirichlet fitting function
    """

    def test_fit_synthetic_dirichlet(self):
        alphas = np.asarray([1., 4., 5.])
        mean = dirichlet.mean(alphas)
        vcv = dirichlet.cov(alphas)

        fit = fit_dirichlet(mean, vcv)
        nptest.assert_array_almost_equal(alphas, fit)
        nptest.assert_array_almost_equal(mean, dirichlet.mean(fit))
    
    def test_fit_sampled_dirichlet(self):
        alphas = np.asarray([0.1, 0.3, 0.2])
        
        rng = np.random.default_rng(123)
        data = rng.dirichlet(alphas, 10000)
        mean = data.mean(0)        
        vcv = np.cov(data, rowvar = False)

        fit = fit_dirichlet(mean, vcv)
        nptest.assert_array_almost_equal(alphas, fit, decimal=2)
        
