"""
Unit tests for core/timespan
"""
import unittest

import pandas as pd
import numpy.testing

# Ensure we can find modules
from unit_tests.common import setup_test_env
setup_test_env()

from src.core.timespan import TimeSpan, RegTimeSpan, OffsetRegTimeSpan

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

    def test_copy_construction(self):
        t1 = pd.Timestamp('2002-01-01T00:00:00', tz='utc')
        t2 = pd.Timestamp('2003-01-01T00:00:00', tz='Etc/GMT-9')
        ts_1 = TimeSpan(t1, t2)
        ts_2 = TimeSpan(ts_1)

        self.assertEqual(ts_1.start, ts_2.start)
        self.assertEqual(ts_1.end, ts_2.end)
        self.assertEqual(ts_1, ts_2)

    def test_regts_null_construction(self):
        ts = RegTimeSpan.from_none()
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, TimeSpan)
        self.assertIsInstance(ts, RegTimeSpan)
        self.assertIsNotNone(ts.start)
        self.assertIsNotNone(ts.end)
        self.assertIsNotNone(ts.timestep)
        self.assertGreater(ts.n_interval, 0)

    def test_regts_copy_construction(self):
        t1 = pd.Timestamp('2002-01-01T00:00:00', tz='utc')
        t2 = pd.Timestamp('2003-01-01T00:00:00', tz='Etc/GMT-9')
        ts_1 = RegTimeSpan(t1, t2, timestep = pd.Timedelta(0.5,'h'))
        ts_2 = RegTimeSpan(ts_1)

        self.assertEqual(ts_1.start, ts_2.start)
        self.assertEqual(ts_1.end, ts_2.end)
        self.assertEqual(ts_1.timestep, ts_2.timestep)
        self.assertEqual(ts_1, ts_2)

    def test_osregts_null_construction(self):
        ts = OffsetRegTimeSpan.from_none()
        self.assertIsNotNone(ts)
        self.assertIsInstance(ts, TimeSpan)
        self.assertIsInstance(ts, RegTimeSpan)
        self.assertIsInstance(ts, OffsetRegTimeSpan)
        self.assertIsNotNone(ts.start)
        self.assertIsNotNone(ts.end)
        self.assertIsNotNone(ts.timestep)
        self.assertGreater(ts.n_interval, 0)
        self.assertFalse(ts.offset_initialised)
        ts.set_offset(pd.Timestamp('2003-01-01T00:00:00', tz='utc'),
                      pd.Timestamp('2002-01-01T00:00:00', tz='utc'))
        self.assertTrue(ts.offset_initialised)

        ts2 = OffsetRegTimeSpan.from_none()
        self.assertFalse(ts2.offset_initialised)
    
    def test_osregts_basic_functionality(self):
        ts = OffsetRegTimeSpan(
            '2001-01-01T00:00:00', 
            '2002-01-01T00:00:00', 
            tz='utc'
        )
        ts.set_offset(pd.Timestamp('2001-01-01T00:00:00', tz='utc'),
                      pd.Timestamp('2001-01-01T00:00:00', tz='utc'))

        remote_ts = TimeSpan(
            '2001-01-01T00:00:00',
            '2001-01-01T01:00:00',
            tz='utc'
        )
        numpy.testing.assert_array_equal(
            ts.get_local_index(remote_ts),
            [0, 1]
        )
        
        remote_ts.end = '2001-01-01T00:00:00'
        numpy.testing.assert_array_equal(
            ts.get_local_index(remote_ts),
            [0]
        )

        remote_ts = TimeSpan(
            '2002-01-01T00:00:00',
            '2002-01-01T01:00:00',
            tz='utc'
        )
        numpy.testing.assert_array_equal(
            ts.get_local_index(remote_ts),
            [8760, 1]
        )

