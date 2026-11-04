"""
Unit tests for newsegscs/sprakeloccs.

The space heating consumption follows the air temperature served by the local environment. The
tests use the in-memory Sprake environment, so that they run offline; to test the persistent
caching of the degree days and profiles, it is made cacheable and given a temporary cache.
"""
import json
import tempfile
import unittest
from unittest import mock

import diskcache
import numpy as np
import pandas as pd

from newsegsmodelframework.core.environment import environment_cache
from newsegsmodelframework.core.environment.inmem_env_servers import InMemoryLocalEnv
from newsegsmodelframework.core.timespan.timespan import RegTimeSpan, TimeSpan
from newsegsmodelframework.newsegscs import sprake_thermal_model, sprakecs, sprakeloccs
from newsegsmodelframework.newsegsmodel import sprakemodel, sprakelocmodel

def _create_model() -> sprakelocmodel.SprakeLocModel:
    mdl = sprakelocmodel.SprakeLocModel.from_none()
    mdl.local_env = sprakemodel.get_sprake_environment_server()
    mdl.wider_env = sprakemodel.get_sprake_wider_env_server()
    return mdl

def _year_timespan() -> RegTimeSpan:
    ts = RegTimeSpan(TimeSpan('2005-01-01', '2006-01-01', tz = 'utc'))
    ts.timestep = pd.Timedelta(1, 'h')
    return ts

class TestHeatingDegreeDays(unittest.TestCase):

    def test_daily_mean_below_base(self):
        # Temperatures over the hours ending at each datetime; the one at midnight belongs to the day before
        datetimes = pd.date_range('2010-01-01T01:00', '2010-01-03T00:00', freq = 'h', tz = 'utc')
        temperatures = np.where(datetimes <= pd.Timestamp('2010-01-02T00:00', tz = 'utc'), 5.5, 20.)
        hdd = sprake_thermal_model.heating_degree_days_from_temperature(datetimes, temperatures)

        self.assertListEqual(
            list(hdd['timestamp']),
            [pd.Timestamp('2010-01-01', tz = 'utc'), pd.Timestamp('2010-01-02', tz = 'utc')]
        )
        np.testing.assert_array_equal(hdd['hdd_15_5'], [10., 0.])

class TestSprakeLocCSConstruction(unittest.TestCase):

    def test_default_of_model(self):
        mdl = sprakelocmodel.SprakeLocModel.from_none()
        self.assertIsInstance(mdl.consumption_storage, sprakeloccs.SprakeLocCS)
        self.assertIsInstance(mdl.consumption_storage.model, sprakelocmodel.SprakeLocModel)

    def test_model_rejects_sprake_cs(self):
        mdl = sprakelocmodel.SprakeLocModel.from_none()
        with self.assertRaises(TypeError):
            mdl.consumption_storage = sprakecs.SprakeCS.from_none()

    def test_copy_construction(self):
        cs = sprakeloccs.SprakeLocCS.from_none()
        cs.hlp = 0.5
        cs2 = sprakeloccs.SprakeLocCS(cs)
        self.assertIsInstance(cs2, sprakeloccs.SprakeLocCS)
        self.assertEqual(cs2.hlp, 0.5)

    def test_serialisation(self):
        mdl = _create_model()
        mdl.consumption_storage.hlp = 0.5
        mdl2 = sprakelocmodel.SprakeLocModel.from_dict(json.loads(mdl.json_dumps_repr()))
        self.assertIsInstance(mdl2.consumption_storage, sprakeloccs.SprakeLocCS)
        self.assertEqual(mdl2.consumption_storage.hlp, 0.5)

class TestSprakeLocCSSpaceHeat(unittest.TestCase):

    def test_spaceheat_consumption(self):
        cs = _create_model().consumption_storage
        ts = _year_timespan()
        cons = cs.get_spaceheat_consumption(ts)

        self.assertEqual(len(cons), len(ts.to_pandas()))
        self.assertFalse(np.isnan(cons).any())
        self.assertTrue((cons >= 0).all())
        # The first timestep has no consumption, as all meters
        self.assertEqual(cons[0], 0.)
        # Heating is mostly in the winter
        january = cons[1:24*31 + 1].sum()
        july = cons[24*181 + 1:24*212 + 1].sum()
        self.assertGreater(january, 5 * july)

    def test_scaled_by_parameters(self):
        cs = _create_model().consumption_storage
        ts = _year_timespan()
        cons = cs.get_spaceheat_consumption(ts)

        cs.hlp = 2 * cs.hlp
        cs.n_units = 3 * cs.n_units
        np.testing.assert_allclose(cs.get_spaceheat_consumption(ts), 6 * cons)

    def test_daily_consumption_from_degree_days(self):
        cs = _create_model().consumption_storage
        ts = _year_timespan()
        cons = pd.Series(cs.get_spaceheat_consumption(ts), index = ts.to_pandas())
        hdd = cs.get_heating_degree_days(ts).set_index('timestamp')['hdd_15_5']

        # Consumption over the hour ending at each datetime, so midnight belongs to the day before
        daily = cons.groupby((cons.index - pd.Timedelta(1, 'm')).floor('D')).sum()
        day = pd.Timestamp('2005-02-01', tz = 'utc')
        self.assertAlmostEqual(
            daily[day],
            hdd[day] * cs.hlp * cs.gfa * cs.n_households * 24. / 1000.
        )

    def test_run(self):
        mdl = _create_model()
        mdl.set_run_period(_year_timespan())
        mdl.run()
        meters = mdl.get_consumption_storage_result().meters_to_pandas()
        np.testing.assert_allclose(
            meters['spaceheat_import'].to_numpy(),
            mdl.consumption_storage.get_spaceheat_consumption(_year_timespan())
        )

class TestSprakeLocCSCache(unittest.TestCase):
    """
    With a cacheable local environment, the degree days and the unit profile are cached, so that
    the temperatures are fetched once.
    """

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.cache = diskcache.Cache(self._dir.name)
        mock.patch.object(environment_cache, 'get_environment_cache', return_value = self.cache).start()
        mock.patch.object(
            InMemoryLocalEnv, 'cache_identity', new = property(lambda self: ('InMemoryLocalEnv', 'test'))
        ).start()
        self.addCleanup(mock.patch.stopall)

        self.mdl = _create_model()
        self.temperature = mock.patch.object(
            self.mdl.local_env, 'get_external_temperature', wraps = self.mdl.local_env.get_external_temperature
        ).start()

    def tearDown(self):
        self.cache.close()
        self._dir.cleanup()

    def test_temperatures_fetched_once(self):
        cs = self.mdl.consumption_storage
        ts = _year_timespan()
        cons = cs.get_spaceheat_consumption(ts)

        # A new module, as in another process, with other parameters
        cs2 = sprakeloccs.SprakeLocCS(cs)
        cs2.model = self.mdl
        cs2.gfa = 2 * cs.gfa
        np.testing.assert_allclose(cs2.get_spaceheat_consumption(ts), 2 * cons)

        self.temperature.assert_called_once()

    def test_degree_days_shared_between_timesteps(self):
        cs = self.mdl.consumption_storage
        ts = _year_timespan()
        cs.get_spaceheat_consumption(ts)
        ts.timestep = pd.Timedelta(30, 'm')
        cs.get_spaceheat_consumption(ts)

        self.temperature.assert_called_once()
        self.assertEqual(len(self.cache), 3)

    def test_not_cached_by_default(self):
        mock.patch.object(InMemoryLocalEnv, 'cache_identity', new = property(lambda self: None)).start()
        self.mdl.consumption_storage.get_spaceheat_consumption(_year_timespan())
        self.assertEqual(len(self.cache), 0)
