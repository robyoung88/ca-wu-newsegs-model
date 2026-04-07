"""
Unit tests for core/timespan
"""
import unittest

import pandas as pd

# Ensure we can find modules
from unit_tests.common import setup_test_env
setup_test_env()

from src.core.timespan import TimeSpan

class TestBasicTimespan(unittest.TestCase):
    def test_null_construction(self):
        ts = TimeSpan.from_none()
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, TimeSpan)
        self.assertIsNotNone(ts.start)
        self.assertIsNotNone(ts.end)

    def test_str_construction(self):
        t1 = pd.Timestamp('2002-01-01T00:00:00', tz='utc')
        t2 = pd.Timestamp('2003-01-01T00:00:00', tz='utc')
        ts = TimeSpan('2002-01-01T00:00:00',
                      '2003-01-01T00:00:00',
                      tz='utc')
        self.assertEqual(ts.start, t1)
        self.assertEqual(ts.end, t2)
        self.assertEqual(ts.start.tz, ts.end.tz)
    
    def test_timestamp_construction(self):
        t1 = pd.Timestamp('2002-01-01T00:00:00', tz='utc')
        t2 = pd.Timestamp('2003-01-01T00:00:00', tz='utc')
        ts = TimeSpan(t1,
                      t2)
        self.assertEqual(ts.start, t1)
        self.assertEqual(ts.end, t2)
        self.assertEqual(ts.start.tz, ts.end.tz)

    def test_mixed_timestamp_construction(self):
        t1 = pd.Timestamp('2002-01-01T00:00:00', tz='utc')
        t2 = pd.Timestamp('2003-01-01T00:00:00', tz='Etc/GMT-9')
        ts = TimeSpan(t1,
                      t2)
        self.assertEqual(ts.start, t1)
        self.assertEqual(ts.end, t2)
        # This is the trick - ts.end should be converted
        self.assertEqual(ts.start.tz, ts.end.tz)
        
        t3 = pd.Timestamp('2003-01-01T00:00:00', tz='utc')
        self.assertNotEqual(ts.end, t3)
        # And ensure we have delta preserved
        dt_real = (t2 - t1).value
        self.assertEqual(ts.delta.value, dt_real)
