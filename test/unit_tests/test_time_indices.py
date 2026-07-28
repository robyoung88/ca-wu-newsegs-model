"""
Unit tests for core/timespan time index functions
"""
import unittest

import numpy as np
import pandas as pd
import numpy.testing

from test.unit_tests.common import setup_test_env
setup_test_env()

from core.timespan import month_index

class TestTimeIndices(unittest.TestCase):
    
    def test_month_index_lastofmonth(self):
        testdates = pd.date_range('2002-01-31T00:00:00', '2003-01-31T00:00:00', freq='d', tz='utc')
        expected_months = np.asarray(
            ([0] * 1) + # J
            ([0]*27) + ([1] * 1) + # F
            ([1] * 30) + ([2] * 1) + # M
            ([2] * 29) + ([3] * 1) + # A
            ([3] * 30) +([4] * 1) + # M
            ([4] * 29) + ([5] * 1) + # J
            ([5] * 30) + ([6] * 1) + # J
            ([6] * 30) + ([7] * 1) + # A
            ([7] * 29) + ([8] * 1) + # S
            ([8] * 30) + ([9] * 1) + # O
            ([9] * 29) + ([10] * 1) + # N
            ([10] * 30) + ([11] * 1) + # D
            ([11] * 30) + ([12] * 1) # J
        )
        mis = month_index(testdates) # Default reference date - first index, last of Jan
        numpy.testing.assert_array_equal(mis, expected_months)

    def test_month_index_firstofmonth(self):
        testdates = pd.date_range('2002-01-31T00:00:00', '2003-01-31T00:00:00', freq='d', tz='utc')
        expected_months = np.asarray(
            ([0] * 1) + # J
            ([1] * 28) + # F
            ([2] * 31) + # M
            ([3] * 30) + # A
            ([4] * 31) + # M
            ([5] * 30) + # J
            ([6] * 31) + # J
            ([7] * 31) + # A
            ([8] * 30) + # S
            ([9] * 31) + # O
            ([10] * 30) + # N
            ([11] * 31) + # D
            ([12] * 31) # J
        )
        mis = month_index(testdates, pd.Timestamp('2002-01-01T00:00:00', tz='utc'))
        numpy.testing.assert_array_equal(mis, expected_months)

