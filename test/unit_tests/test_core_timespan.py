"""
Unit tests for core/timespan
"""
import unittest

import json
import pandas as pd
import numpy.testing

# Ensure we can find modules


from newsegsmodelframework.core.timespan import TimeSpan, RegTimeSpan, OffsetRegTimeSpan, timespan_from_dict

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

class TestTimespanEqualities(unittest.TestCase):

    def test_timespan_equality(self):
        ts1 = TimeSpan(
            '2001-01-01T00:00:00',
            '2002-01-01T00:00:00',
            tz='utc'
        )
        ts2 = TimeSpan(ts1)
        self.assertEqual(ts1, ts2)
        ts2.end = '2002-02-01T00:00:00'
        self.assertNotEqual(ts1, ts2)
        ts2.end = '2002-01-01T00:00:00'
        self.assertEqual(ts1, ts2)
        ts2.start = '2000-01-01T00:00:00'
        self.assertNotEqual(ts1, ts2)
    
    def test_regtimespan_equality(self):
        ts1 = RegTimeSpan(
            '2001-01-01T00:00:00',
            '2002-01-01T00:00:00',
            tz='utc',
            timestep = pd.Timedelta(1, 'h')
        )
        ts2 = RegTimeSpan(ts1)
        self.assertEqual(ts1, ts2)
        ts2.timestep = pd.Timedelta(0.5, 'h')
        self.assertNotEqual(ts1, ts2)
        ts3 = TimeSpan(ts2)
        self.assertEqual(ts1, ts3)
        self.assertEqual(ts3, ts1)
        ts2.timestep = pd.Timedelta(1, 'h')
        self.assertEqual(ts1, ts2)
        ts2.end = '2002-02-01T00:00:00'
        self.assertNotEqual(ts1, ts2)
        ts2.end = '2002-01-01T00:00:00'
        self.assertEqual(ts1, ts2)
        ts2.start = '2000-01-01T00:00:00'
        self.assertNotEqual(ts1, ts2)
    
    def test_offsetregtimespan_equality(self):
        ts1 = OffsetRegTimeSpan(
            '2001-01-01T00:00:00',
            '2002-01-01T00:00:00',
            tz='utc',
            timestep = pd.Timedelta(1, 'h')
        )

        ts1.set_offset(
            local_start='2001-01-01T00:00:00',
            remote_start='2002-01-01T00:00:00'
        )

        ts2 = OffsetRegTimeSpan(ts1)
        self.assertEqual(ts1, ts2)
        ts3 = RegTimeSpan(ts2)
        self.assertEqual(ts1, ts3)
        ts2.set_offset(
            local_start='2002-01-01T00:00:00',
            remote_start='2002-01-01T00:00:00'
        )
        self.assertNotEqual(ts1, ts2)

class TestTimespanRecovery(unittest.TestCase):
    def test_timespan_recovery(self):
        ts1 = TimeSpan(
            '2001-01-01T00:00:00',
            '2002-01-01T00:00:00',
            tz='utc'
        )

        d1 = ts1.to_dict()
        ts2 = timespan_from_dict(d1)
        self.assertEqual(ts1, ts2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        ts3 = timespan_from_dict(d2)
        self.assertEqual(ts1, ts3)
    
    def test_regtimespan_recovery(self):
        ts1 = RegTimeSpan(
            '2001-01-01T00:00:00',
            '2002-01-01T00:00:00',
            tz='utc',
            timestep = pd.Timedelta(1, 'h')
        )

        d1 = ts1.to_dict()
        ts2 = timespan_from_dict(d1)
        self.assertEqual(ts1, ts2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        ts3 = timespan_from_dict(d2)
        self.assertEqual(ts1, ts3)

    def test_offsetregtimespan_recovery(self):
        ts1 = OffsetRegTimeSpan(
            '2001-01-01T00:00:00',
            '2002-01-01T00:00:00',
            tz='utc',
            timestep = pd.Timedelta(1, 'h')
        )

        d1 = ts1.to_dict()
        ts2 = timespan_from_dict(d1)
        self.assertEqual(ts1, ts2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        ts3 = timespan_from_dict(d2)
        self.assertEqual(ts1, ts3)

        ts1.set_offset(
            local_start='2001-01-01T00:00:00',
            remote_start='2002-01-01T00:00:00'
        )

        d1 = ts1.to_dict()
        ts2 = timespan_from_dict(d1)
        self.assertEqual(ts1, ts2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        ts3 = timespan_from_dict(d2)
        self.assertEqual(ts1, ts3)
