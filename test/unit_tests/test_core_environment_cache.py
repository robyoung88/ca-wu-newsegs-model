"""
Unit tests for core/environment/environment_cache and its use by HourlyPVGISNEWALocalEnv.

The PVGIS and NEWA fetches are replaced by fakes, so that the tests run offline, and each test
uses its own cache in a temporary directory.
"""
import os
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import diskcache
import numpy as np
import pandas as pd
import requests

from newa import get_newa_data
from newsegsmodelframework.core import location
from newsegsmodelframework.core.environment import environment_cache, pvgis_newa_env_servers
from newsegsmodelframework.core.environment.environment_servers import EnvironmentDataUnavailableError
from newsegsmodelframework.core.timespan.timespan import TimeSpan

_IDENTITY = ('TestEnv', '0.0.1')
_TIMESPAN = TimeSpan('2010-01-01', '2010-01-02', tz = 'utc')

class TemporaryCacheTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.cache = diskcache.Cache(self._dir.name)

    def tearDown(self):
        self.cache.close()
        self._dir.cleanup()

class TestEnvironmentCacheKey(unittest.TestCase):

    def key(self, loc, timespan = _TIMESPAN, **kwargs):
        return environment_cache.environment_cache_key(_IDENTITY, 'measure', loc, timespan, **kwargs)

    def test_location_rounded_to_3dp(self):
        self.assertEqual(
            self.key(location.Location(53.25535, -3.47697)),
            self.key(location.Location(53.2549, -3.4774))
        )
        self.assertNotEqual(
            self.key(location.Location(53.25535, -3.47697)),
            self.key(location.Location(53.2565, -3.47697))
        )

    def test_negative_zero(self):
        self.assertEqual(
            self.key(location.Location(51.5, -0.0001)),
            self.key(location.Location(51.5, 0.0001))
        )

    def test_height_rounded_to_nearest_m(self):
        loc = location.Location(51.5, -0.1)
        self.assertEqual(self.key(loc, height = 20.2), self.key(loc, height = 19.8))
        self.assertNotEqual(self.key(loc, height = 20.), self.key(loc, height = 21.))
        self.assertNotEqual(self.key(loc, height = 0.), self.key(loc))

    def test_times_compared_in_utc(self):
        loc = location.Location(51.5, -0.1)
        self.assertEqual(
            self.key(loc, TimeSpan(pd.Timestamp('2010-01-01T00:00', tz = 'utc'), pd.Timestamp('2010-01-02T00:00', tz = 'utc'))),
            self.key(loc, TimeSpan(pd.Timestamp('2010-01-01T01:00', tz = 'Europe/Paris'), pd.Timestamp('2010-01-02T01:00', tz = 'Europe/Paris')))
        )
        self.assertNotEqual(self.key(loc), self.key(loc, TimeSpan('2010-01-01', '2010-01-03', tz = 'utc')))

    def test_identity_and_params(self):
        loc = location.Location(51.5, -0.1)
        key = self.key(loc, timestep = '1h')
        self.assertNotEqual(key, environment_cache.environment_cache_key(('TestEnv', '0.0.2'), 'measure', loc, _TIMESPAN, timestep = '1h'))
        self.assertNotEqual(key, self.key(loc, timestep = '30min'))
        # Keys are stable once pickled, as diskcache stores them
        self.assertEqual(pickle.dumps(key), pickle.dumps(self.key(location.Location(51.5, -0.1), timestep = '1h')))

class TestGetOrSet(TemporaryCacheTestCase):

    def test_computed_once(self):
        compute = mock.Mock(return_value = np.arange(3))
        for _ in range(2):
            np.testing.assert_array_equal(
                environment_cache.get_or_set(('a',), compute, cache = self.cache),
                np.arange(3)
            )
        compute.assert_called_once()

    def test_default_cache(self):
        compute = mock.Mock(return_value = 1)
        with mock.patch.object(environment_cache, 'get_environment_cache', return_value = self.cache):
            environment_cache.get_or_set(('a',), compute)
        self.assertEqual(self.cache[('a',)], 1)

    def test_time_independent_key(self):
        loc = location.Location(51.5, -0.1)
        key = environment_cache.environment_cache_key(_IDENTITY, 'horizon', loc, None)
        self.assertEqual(
            key, environment_cache.environment_cache_key(_IDENTITY, 'horizon', location.Location(51.5002, -0.1), None)
        )
        self.assertNotEqual(key, environment_cache.environment_cache_key(_IDENTITY, 'horizon', loc, _TIMESPAN))

class TestGetOrSetLock(TemporaryCacheTestCase):
    """
    A key is locked while computed, so that concurrent requests compute it once.
    """

    def _slow_compute(self, started: threading.Event, release: threading.Event, value = 1):
        def compute():
            started.set()
            release.wait(5)
            return value
        return mock.Mock(side_effect = compute)

    def test_concurrent_requests_computed_once(self):
        started, release = threading.Event(), threading.Event()
        compute = self._slow_compute(started, release)
        results = []
        def request():
            # Each thread opens the cache, as another process would
            with diskcache.Cache(self._dir.name) as cache:
                results.append(environment_cache.get_or_set(('a',), compute, cache = cache))

        threads = [threading.Thread(target = request) for _ in range(3)]
        threads[0].start()
        self.assertTrue(started.wait(5))
        for thread in threads[1:]:
            thread.start()
        time.sleep(0.2)
        release.set()
        for thread in threads:
            thread.join(10)

        self.assertEqual(results, [1, 1, 1])
        compute.assert_called_once()

    def test_is_pending(self):
        started, release = threading.Event(), threading.Event()
        thread = threading.Thread(
            target = environment_cache.get_or_set,
            args = (('a',), self._slow_compute(started, release)),
            kwargs = {'cache': self.cache}
        )
        self.assertFalse(environment_cache.is_pending(('a',), self.cache))
        thread.start()
        self.assertTrue(started.wait(5))
        self.assertTrue(environment_cache.is_pending(('a',), self.cache))
        self.assertFalse(environment_cache.is_pending(('b',), self.cache))
        release.set()
        thread.join(10)
        self.assertFalse(environment_cache.is_pending(('a',), self.cache))

    def test_failed_compute_releases_lock(self):
        with self.assertRaises(RuntimeError):
            environment_cache.get_or_set(('a',), mock.Mock(side_effect = RuntimeError), cache = self.cache)
        self.assertFalse(environment_cache.is_pending(('a',), self.cache))
        self.assertNotIn(('a',), self.cache)
        self.assertEqual(environment_cache.get_or_set(('a',), lambda: 2, cache = self.cache), 2)

    def test_shared_lock_key(self):
        # A request for one entry waits for a computation of another with the same lock key,
        # which sets both
        started, release = threading.Event(), threading.Event()
        def compute_both():
            started.set()
            release.wait(5)
            self.cache.set(('b',), 'b')
            return 'a'
        thread = threading.Thread(
            target = environment_cache.get_or_set,
            args = (('a',), compute_both),
            kwargs = {'cache': self.cache}
        )
        thread.start()
        self.assertTrue(started.wait(5))
        compute_b = mock.Mock(return_value = 'not this')
        threading.Timer(0.2, release.set).start()
        self.assertEqual(
            environment_cache.get_or_set(('b',), compute_b, cache = self.cache, lock_key = ('a',)),
            'b'
        )
        thread.join(10)
        compute_b.assert_not_called()

    def test_lock_expires(self):
        # A lock left by a process which stopped while computing does not block the key
        with mock.patch.object(environment_cache, 'settings', {'ENV_CACHE_LOCK_EXPIRE_S': 0.1}):
            lock = environment_cache._lock(('a',), self.cache)
            lock.acquire()
            lock._stop_renewal.set() # pyright: ignore[reportOptionalMemberAccess] - as when its holder stops
            self.assertTrue(environment_cache.is_pending(('a',), self.cache))
            time.sleep(0.2)
            self.assertFalse(environment_cache.is_pending(('a',), self.cache))
            self.assertEqual(environment_cache.get_or_set(('a',), lambda: 1, cache = self.cache), 1)

    # A holder renews its lock while it computes, so that the lock can expire soon after a holder stops (#182),
    # however long a computation takes

    def test_default_expiry_is_short(self):
        # A NEWA fetch can take 8 minutes, but a stopped holder must not block the data for longer than a few
        from config import settings
        self.assertLessEqual(float(settings.get('ENV_CACHE_LOCK_EXPIRE_S', environment_cache.DEFAULT_LOCK_EXPIRE_S)), 300)
        self.assertLessEqual(environment_cache.DEFAULT_LOCK_EXPIRE_S, 300)

    def test_lock_renewed_while_computing(self):
        # A computation lasting several times the expiry keeps the key locked throughout, and is not repeated
        started, release = threading.Event(), threading.Event()
        compute = self._slow_compute(started, release)
        with mock.patch.object(environment_cache, 'settings', {'ENV_CACHE_LOCK_EXPIRE_S': 0.4}):
            thread = threading.Thread(
                target = environment_cache.get_or_set, args = (('a',), compute), kwargs = {'cache': self.cache}
            )
            thread.start()
            self.assertTrue(started.wait(5))
            for _ in range(6):
                time.sleep(0.25)
                self.assertTrue(environment_cache.is_pending(('a',), self.cache))
            threading.Timer(0.2, release.set).start()
            self.assertEqual(environment_cache.get_or_set(('a',), compute, cache = self.cache), 1)
            thread.join(10)
        compute.assert_called_once()
        self.assertFalse(environment_cache.is_pending(('a',), self.cache))

    def test_release_keeps_the_lock_of_another_holder(self):
        # A holder whose lock expired, and was taken by another, does not release the other's
        with mock.patch.object(environment_cache, 'settings', {'ENV_CACHE_LOCK_EXPIRE_S': 0.1}):
            first = environment_cache._lock(('a',), self.cache)
            first.acquire()
            self.cache.touch(('lock', ('a',)), 0.01) # As if the holder had stopped renewing it
            time.sleep(0.05)
            second = environment_cache._lock(('a',), self.cache)
            second.acquire()
            first.release()
            self.assertTrue(environment_cache.is_pending(('a',), self.cache))
            second.release()
            self.assertFalse(environment_cache.is_pending(('a',), self.cache))

    def test_holder_stopped_while_computing(self):
        # A process killed while computing leaves its lock, which expires and is then taken by the next request
        script = (
            'import sys, time\n'
            'import diskcache\n'
            'from newsegsmodelframework.core.environment import environment_cache\n'
            'def compute():\n'
            '    print("started", flush = True)\n'
            '    time.sleep(60)\n'
            'environment_cache.get_or_set(("a",), compute, cache = diskcache.Cache(sys.argv[1]))\n'
        )
        env = dict(os.environ, DYNACONF_ENV_CACHE_LOCK_EXPIRE_S = '1')
        env['PYTHONPATH'] = os.pathsep.join([str(Path(environment_cache.__file__).parents[3]), env.get('PYTHONPATH', '')])
        proc = subprocess.Popen(
            [sys.executable, '-c', script, self._dir.name], stdout = subprocess.PIPE, text = True, env = env,
        )
        try:
            self.assertEqual(proc.stdout.readline().strip(), 'started') # pyright: ignore[reportOptionalMemberAccess]
            self.assertTrue(environment_cache.is_pending(('a',), self.cache))
        finally:
            proc.kill()
            proc.wait(10)
            proc.stdout.close() # pyright: ignore[reportOptionalMemberAccess]
        self.assertTrue(environment_cache.is_pending(('a',), self.cache))
        started = time.monotonic()
        with mock.patch.object(environment_cache, 'settings', {'ENV_CACHE_LOCK_EXPIRE_S': 1}):
            self.assertEqual(environment_cache.get_or_set(('a',), lambda: 2, cache = self.cache), 2)
        self.assertLess(time.monotonic() - started, 5)

def _fake_wind_at_site(lat, lon, rng, dt_start, dt_stop, site_heights):
    times = pd.date_range(dt_start, dt_stop, freq = '30min')
    return pd.DataFrame({
        'time': times,
        'hub_height': site_heights[0],
        'ws_hub': lat + lon / 1000. + site_heights[0] / 1e6 + np.zeros(len(times)),
        # Alternating either side of north, so that a mean of the angles would give 180
        'wind_from_direction_10m': np.where(np.arange(len(times)) % 2 == 0, 350., 10.),
    })

def _fake_pvgis_horizon(lat, lon, **kwargs):
    azimuths = np.arange(0., 361., 7.5)
    return pd.Series(np.full(len(azimuths), lat / 10.), index = azimuths, name = 'horizon_elevation'), {}

def _fake_pvgis_hourly(lat, lon, start, end, **kwargs):
    times = pd.date_range(start + pd.Timedelta(10, 'm'), end, freq = 'h', name = 'time')
    return pd.DataFrame({
        'poa_global': np.full(len(times), lat),
        'temp_air': np.full(len(times), lon),
        'wind_speed': np.ones(len(times)),
    }, index = times), {}

class TestHourlyPVGISNEWALocalEnvCache(TemporaryCacheTestCase):

    def setUp(self):
        super().setUp()
        self.wind = mock.patch.object(
            pvgis_newa_env_servers.wind_resource_helpers, 'get_wind_at_site', side_effect = _fake_wind_at_site
        ).start()
        self.pvgis = mock.patch.object(
            pvgis_newa_env_servers.pvlib.iotools, 'get_pvgis_hourly', side_effect = _fake_pvgis_hourly
        ).start()
        self.horizon = mock.patch.object(
            pvgis_newa_env_servers.pvlib.iotools, 'get_pvgis_horizon', side_effect = _fake_pvgis_horizon
        ).start()
        self.addCleanup(mock.patch.stopall)

    def test_wind_directions_fetched_with_speeds(self):
        loc = location.RaisedLocation(53.25535, -3.47697, 15)
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        speeds = server.get_wind_speeds(loc, _TIMESPAN)
        directions = server.get_wind_directions(loc, _TIMESPAN)
        self.wind.assert_called_once()
        self.assertEqual(len(speeds), len(directions))
        # Hourly means of 350 and 10 degrees are north, not south. The first hour has a single
        # observation, at 350 degrees
        signed_directions = (np.asarray(directions) + 180.) % 360. - 180.
        self.assertAlmostEqual(signed_directions[0], -10.)
        np.testing.assert_allclose(signed_directions[1:], 0., atol = 1e-9)

    def test_wind_speeds_cached_with_directions(self):
        loc = location.RaisedLocation(53.25535, -3.47697, 15)
        pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_wind_directions(loc, _TIMESPAN)
        pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_wind_speeds(loc, _TIMESPAN)
        self.wind.assert_called_once()

    def test_wind_directions_fetched_for_speeds_cached_without_them(self):
        # Speeds cached before directions were served are kept; the directions are fetched
        loc = location.RaisedLocation(53.25535, -3.47697, 15)
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        speeds = server.get_wind_speeds(loc, _TIMESPAN)
        directions_key, _ = server._cache_key('wind_directions', loc, _TIMESPAN)
        self.cache.delete(directions_key)
        server.get_wind_directions(loc, _TIMESPAN)
        self.assertEqual(self.wind.call_count, 2)
        np.testing.assert_array_equal(server.get_wind_speeds(loc, _TIMESPAN), speeds)

    def test_wind_directions_of_locations(self):
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        directions = server.get_wind_directions(
            [location.RaisedLocation(53.255, -3.477, 15), location.RaisedLocation(51.5, -0.1, 15)], _TIMESPAN
        )
        self.assertEqual(np.asarray(directions).shape[0], 2)

    def test_horizon_fetched_once(self):
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        horizon = server.get_horizon(location.Location(53.25535, -3.47697))
        pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_horizon(location.Location(53.2551, -3.4772))
        self.horizon.assert_called_once()
        self.assertEqual(self.horizon.call_args.args, (53.255, -3.477))
        self.assertEqual(self.horizon.call_args.kwargs['timeout'], (10., 120.))
        np.testing.assert_allclose(horizon.values, 5.3255)

    def test_horizon_unavailable(self):
        self.horizon.side_effect = requests.ConnectionError('Max retries exceeded')
        with self.assertRaisesRegex(
            EnvironmentDataUnavailableError,
            r'^Unable to obtain the horizon of \(53.255, -3.477\) from PVGIS: the service could not be reached$'
        ):
            pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_horizon(location.Location(53.255, -3.477))

    def test_other_servers_do_not_serve_directions_or_horizon(self):
        from newsegsmodelframework.core.environment.inmem_env_servers import InMemoryLocalEnv
        server = InMemoryLocalEnv()
        with self.assertRaises(NotImplementedError):
            server.get_wind_directions(location.RaisedLocation(53.255, -3.477, 15), _TIMESPAN)
        with self.assertRaises(NotImplementedError):
            server.get_horizon(location.Location(53.255, -3.477))

    def test_wind_speeds_fetched_once(self):
        loc = location.RaisedLocation(53.25535, -3.47697, 20.2)
        ws1 = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_wind_speeds(loc, _TIMESPAN)
        # A new server, as in another process, at a location rounding to the same key
        ws2 = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_wind_speeds(
            location.RaisedLocation(53.2551, -3.4772, 19.8), _TIMESPAN
        )
        np.testing.assert_array_equal(ws1, ws2)
        self.wind.assert_called_once()
        # Fetched at the rounded location and height
        args, kwargs = self.wind.call_args
        self.assertEqual(args[:2], (53.255, -3.477))
        self.assertEqual(kwargs['site_heights'], [20])

    def test_wind_speeds_by_height(self):
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        server.get_wind_speeds(location.RaisedLocation(53.255, -3.477, 20), _TIMESPAN)
        server.get_wind_speeds(location.RaisedLocation(53.255, -3.477, 30), _TIMESPAN)
        self.assertEqual(self.wind.call_count, 2)

    def test_pvgis_data_shared_by_measures(self):
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        loc = location.Location(53.25535, -3.47697)
        flux = server.get_horizontal_solar_flux(loc, _TIMESPAN)
        temp = server.get_external_temperature(loc, _TIMESPAN)
        self.pvgis.assert_called_once()
        np.testing.assert_array_equal(flux, 53.255)
        np.testing.assert_array_equal(temp, -3.477)
        self.assertEqual(len(temp), len(server.get_true_datetimes('external_temperature', loc, _TIMESPAN)))

    def test_external_temperature_of_locations(self):
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        temps = server.get_external_temperature(
            [location.Location(53.255, -3.477), location.Location(51.5, -0.1)], _TIMESPAN
        )
        np.testing.assert_array_equal(temps[:, 0], [-3.477, -0.1])

    def test_new_version_does_not_use_old_data(self):
        loc = location.Location(53.255, -3.477)
        pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_horizontal_solar_flux(loc, _TIMESPAN)
        with mock.patch.object(pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv, '_version', '99'):
            pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_horizontal_solar_flux(loc, _TIMESPAN)
        self.assertEqual(self.pvgis.call_count, 2)

    def test_no_response_from_newa(self):
        self.wind.side_effect = requests.ReadTimeout('Read timed out')
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        with self.assertRaises(EnvironmentDataUnavailableError) as cm:
            server.get_wind_speeds(location.RaisedLocation(53.25535, -3.47697, 20), _TIMESPAN)
        self.assertEqual(
            str(cm.exception),
            'Unable to obtain wind speeds for (53.255, -3.477) at 20 m from NEWA: the service did not respond in time'
        )
        self.assertFalse(cm.exception.retryable)

        # Nothing is cached, so the data are fetched once the service responds
        self.assertEqual(len(self.cache), 0)
        self.wind.side_effect = _fake_wind_at_site
        server.get_wind_speeds(location.RaisedLocation(53.25535, -3.47697, 20), _TIMESPAN)
        self.assertEqual(self.wind.call_count, 2)

    def test_newa_error_response(self):
        # get_newa_data raises the builtin ConnectionError for an error status
        self.wind.side_effect = ConnectionError('Error 503 from NEWA API: Service Unavailable')
        with self.assertRaisesRegex(EnvironmentDataUnavailableError, 'from NEWA: Error 503'):
            pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_wind_speeds(
                location.RaisedLocation(53.255, -3.477, 20), _TIMESPAN
            )

    def test_pvgis_unreachable(self):
        self.pvgis.side_effect = requests.ConnectionError('Max retries exceeded')
        with self.assertRaisesRegex(
            EnvironmentDataUnavailableError,
            r'^Unable to obtain solar data for \(53.255, -3.477\) from PVGIS: the service could not be reached$'
        ):
            pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_external_temperature(
                location.Location(53.255, -3.477), _TIMESPAN
            )

    def test_pvgis_refuses_request(self):
        # pvlib raises the error message of PVGIS as an HTTPError
        self.pvgis.side_effect = requests.HTTPError('Location over the sea')
        with self.assertRaisesRegex(EnvironmentDataUnavailableError, 'from PVGIS: Location over the sea'):
            pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_horizontal_solar_flux(
                location.Location(53.255, -3.477), _TIMESPAN
            )

    def test_pvgis_timeout_passed(self):
        pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache).get_horizontal_solar_flux(
            location.Location(53.255, -3.477), _TIMESPAN
        )
        self.assertEqual(self.pvgis.call_args.kwargs['timeout'], (10., 120.))

    def test_server_pickles_with_its_cache(self):
        server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        loc = location.Location(53.255, -3.477)
        server.get_horizontal_solar_flux(loc, _TIMESPAN)
        server2 = pickle.loads(pickle.dumps(server))
        server2.get_horizontal_solar_flux(loc, _TIMESPAN)
        server2.cache.close()
        self.pvgis.assert_called_once()

class TestNewaTimeout(unittest.TestCase):

    def test_requests_have_timeout(self):
        with mock.patch.object(get_newa_data.requests, 'get', side_effect = requests.ConnectTimeout) as get:
            for fetch in (
                lambda: get_newa_data.get_newa_micro_point(53.255, -3.477),
                lambda: get_newa_data.get_newa_meso_ts_point(53.255, -3.477, dt_start = '2010-01-01T00:00:00', dt_stop = '2010-01-02T00:00:00'),
            ):
                with self.assertRaises(requests.ConnectTimeout):
                    fetch()
                self.assertEqual(get.call_args.kwargs['timeout'], (10., 300.))
