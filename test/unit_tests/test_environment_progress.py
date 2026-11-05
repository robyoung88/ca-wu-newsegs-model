"""
Unit tests for reporting waits for environmental data during model runs: `environment_progress`,
its use by the environment cache and `HourlyPVGISNEWALocalEnv`, the progress of `SprakeModel.run`,
and the merging of that progress into the deterministic run of the app.

The PVGIS and NEWA fetches are replaced by fakes, so that the tests run offline, and each test
uses its own cache in a temporary directory.
"""
import tempfile
import threading
import unittest
from unittest import mock

import diskcache
import numpy as np
import pandas as pd

# Fill the registers, as the app does on import
import newsegsmodelframework.register_plugins  # noqa: F401
import newsegsmodelapp.register_plugins  # noqa: F401

from newsegsmodelapp.plugins.pages.processes import common_deterministic
from newsegsmodelapp.plugins.pages.processes.progress_messages import runs_progress_message
from newsegsmodelframework.core import location
from newsegsmodelframework.core.environment import environment_cache, environment_progress, pvgis_newa_env_servers
from newsegsmodelframework.core.timespan.timespan import TimeSpan
from newsegsmodelframework.newsegssensitivity import dsa
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

_TIMESPAN = TimeSpan('2010-01-01', '2010-01-02', tz = 'utc')
_SITE = location.Location(53.255, -3.477)

class TestEnvironmentProgress(unittest.TestCase):

    def test_no_reporter(self):
        with environment_progress.awaiting('wind speeds'):
            pass

    def test_reports_start_and_end(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            with environment_progress.awaiting('wind speeds from NEWA', 'requests usually take 1 to 8 minutes'):
                messages.append('fetching')
        self.assertEqual(messages, [
            'Awaiting environmental data: wind speeds from NEWA (requests usually take 1 to 8 minutes)',
            'fetching',
            None,
        ])

    def test_nested_waits_restore_the_outer_message(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            with environment_progress.awaiting('outer'):
                with environment_progress.awaiting('inner'):
                    pass
        self.assertEqual(messages, [
            'Awaiting environmental data: outer',
            'Awaiting environmental data: inner',
            'Awaiting environmental data: outer',
            None,
        ])

    def test_ends_on_error(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            with self.assertRaises(RuntimeError):
                with environment_progress.awaiting('wind speeds'):
                    raise RuntimeError
        self.assertEqual(messages[-1], None)

    def test_reporter_errors_do_not_stop_the_fetch(self):
        reporter = mock.Mock(side_effect = RuntimeError('database locked'))
        fetched = []
        with self.assertLogs(environment_progress.logger, 'ERROR'):
            with environment_progress.reporting_waits(reporter):
                with environment_progress.awaiting('wind speeds'):
                    fetched.append(True)
        self.assertEqual(fetched, [True])

    def test_reporter_only_within_block(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            pass
        with environment_progress.awaiting('wind speeds'):
            pass
        self.assertEqual(messages, [])

    def test_threads_report_their_own_waits(self):
        messages = {'a': [], 'b': []}
        barrier = threading.Barrier(2)
        def run(name):
            with environment_progress.reporting_waits(messages[name].append):
                barrier.wait(5)
                with environment_progress.awaiting(name):
                    barrier.wait(5)
        threads = [threading.Thread(target = run, args = (name,)) for name in messages]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(10)
        self.assertEqual(messages, {
            'a': ['Awaiting environmental data: a', None],
            'b': ['Awaiting environmental data: b', None],
        })

class TemporaryCacheTestCase(unittest.TestCase):
    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.cache = diskcache.Cache(self._dir.name)

    def tearDown(self):
        self.cache.close()
        self._dir.cleanup()

class TestCacheWaits(TemporaryCacheTestCase):

    def test_computing_is_not_a_wait(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            environment_cache.get_or_set(('a',), lambda: 1, cache = self.cache, description = 'wind speeds')
        self.assertEqual(messages, [])

    def test_wait_for_another_request(self):
        started, release = threading.Event(), threading.Event()
        def compute():
            started.set()
            release.wait(5)
            return 1
        thread = threading.Thread(
            target = environment_cache.get_or_set, args = (('a',), compute), kwargs = {'cache': self.cache}
        )
        thread.start()
        self.assertTrue(started.wait(5))
        messages = []
        threading.Timer(0.2, release.set).start()
        with environment_progress.reporting_waits(messages.append):
            value = environment_cache.get_or_set(
                ('a',), lambda: 2, cache = self.cache, description = 'wind speeds for (53.255, -3.477) at 10 m'
            )
        thread.join(10)
        self.assertEqual(value, 1)
        self.assertEqual(messages, [
            'Awaiting environmental data: wind speeds for (53.255, -3.477) at 10 m, already being fetched for another request',
            None,
        ])

def _fake_wind_at_site(lat, lon, rng, dt_start, dt_stop, site_heights):
    times = pd.date_range(dt_start, dt_stop, freq = '30min')
    return pd.DataFrame({
        'time': times,
        'hub_height': site_heights[0],
        'ws_hub': 6. + np.sin(np.arange(len(times)) / 500.),
        'wind_from_direction_10m': np.full(len(times), 225.),
    })

def _fake_pvgis_hourly(lat, lon, start, end, **kwargs):
    times = pd.date_range(start + pd.Timedelta(10, 'm'), end, freq = 'h', name = 'time')
    daylight = np.clip(np.sin(np.pi * (times.hour - 6) / 12.), 0., None)
    return pd.DataFrame({
        'poa_global': 400. * daylight,
        'poa_direct': 200. * daylight,
        'temp_air': 10. - 8. * np.cos(2. * np.pi * (times.dayofyear - 15) / 365.),
    }, index = times), {}

class FakeServicesTestCase(TemporaryCacheTestCase):

    def setUp(self):
        super().setUp()
        self.server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        self.wind = mock.patch.object(
            pvgis_newa_env_servers.wind_resource_helpers, 'get_wind_at_site', side_effect = _fake_wind_at_site
        ).start()
        self.pvgis = mock.patch.object(
            pvgis_newa_env_servers.pvlib.iotools, 'get_pvgis_hourly', side_effect = _fake_pvgis_hourly
        ).start()
        self.addCleanup(mock.patch.stopall)

class TestServerWaits(FakeServicesTestCase):

    def test_newa_request_reported(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            self.server.get_wind_speeds(location.RaisedLocation(53.25535, -3.47697, 10.2), _TIMESPAN)
        self.assertEqual(messages, [
            'Awaiting environmental data: wind speeds for (53.255, -3.477) at 10 m from NEWA '
            '(requests usually take 1 to 8 minutes)',
            None,
        ])

    def test_pvgis_request_reported(self):
        messages = []
        with environment_progress.reporting_waits(messages.append):
            self.server.get_external_temperature(_SITE, _TIMESPAN)
        self.assertEqual(messages, [
            'Awaiting environmental data: solar data for (53.255, -3.477) from PVGIS '
            '(requests usually take under a minute)',
            None,
        ])

    def test_cached_data_not_reported(self):
        self.server.get_external_temperature(_SITE, _TIMESPAN)
        messages = []
        with environment_progress.reporting_waits(messages.append):
            self.server.get_external_temperature(_SITE, _TIMESPAN)
        self.assertEqual(messages, [])

class TestModelRunProgress(FakeServicesTestCase):
    """
    `SprakeModel.run` of the default `sprakeloc` configuration, with the fake services.
    """

    def setUp(self):
        super().setUp()
        self.model = PROJECT_FACTORIES['sprakeloc']().get_focussed_metamodel().model
        self.model.local_env = self.server
        # A short run period, so that the runs are quick
        run_period = TimeSpan('2010-01-01', '2010-01-08', tz = 'utc')
        self.model.run_period = run_period # pyright: ignore[reportAttributeAccessIssue]

    def run_model(self, **kwargs):
        progress = []
        self.model.run(progress_callback = lambda fraction, message: progress.append((fraction, message)), **kwargs)
        return progress

    def test_modules_reported(self):
        progress = self.run_model()
        # The message of a module is repeated after each of its waits
        modules = list(dict.fromkeys((f, m) for f, m in progress if environment_progress.AWAITING not in m))
        self.assertEqual(modules, [
            (0., 'Running the grid module'),
            (1. / 3., 'Running the generation module'),
            (2. / 3., 'Running the consumption and storage module'),
        ])

    def test_first_run_awaits_environmental_data(self):
        progress = self.run_model()
        awaiting = [(f, m) for f, m in progress if environment_progress.AWAITING in m]
        self.assertTrue(awaiting)
        # The generation module waits for the wind from NEWA, at the height of the turbine
        turbine_height = round(self.model.generation.generator.generators[0].location.height_agl) # pyright: ignore[reportAttributeAccessIssue]
        self.assertIn(
            (1. / 3., f'Running the generation module - Awaiting environmental data: wind speeds for '
                      f'(53.255, -3.477) at {turbine_height} m from NEWA (requests usually take 1 to 8 minutes)'),
            awaiting
        )
        # Each wait is followed by the message of its module again
        for i, (fraction, message) in enumerate(progress):
            if environment_progress.AWAITING in message:
                self.assertEqual(progress[i + 1][0], fraction)
                self.assertNotIn(environment_progress.AWAITING, progress[i + 1][1])

    def test_later_runs_do_not_await(self):
        self.run_model()
        progress = self.run_model()
        self.assertFalse([m for _, m in progress if environment_progress.AWAITING in m])

    def test_partial_run(self):
        self.run_model()
        progress = self.run_model(run_from = 'generation')
        self.assertEqual(progress, [(0., 'Running the consumption and storage module')])

    def test_run_without_callback(self):
        self.model.run()
        self.assertIsNotNone(self.model.get_generation_result())

class TestDeterministicRunProgress(unittest.TestCase):
    """
    The deterministic run reports progress as a count of its tasks completed, and the progress of
    the model run within its task.
    """

    def run_metamodel(self, **kwargs):
        mm = mock.MagicMock()
        def run(run_from, progress_callback):
            progress_callback(0., 'Running the grid module')
            progress_callback(0.5, 'Running the generation module - Awaiting environmental data: wind speeds')
        mm.model.run.side_effect = run
        mm.model.chain_modified = False
        mm.finance.chain_modified = False
        result_provider = mock.Mock()
        result_provider.get_result.return_value = (None, None)
        request = mock.Mock(request_id = 1, run_id = 2, trigger_request_id = -1)
        progress = []
        with mock.patch.object(common_deterministic.db_staleness, 'record_process_run'):
            common_deterministic.deterministic_run_metamodel(
                mm, mock.Mock(), request, mock.Mock(), result_provider, 2,
                lambda step, total, message: progress.append((step, total, message)),
                lambda: False,
                **kwargs,
            )
        return progress

    def test_model_progress_merged(self):
        self.assertEqual(self.run_metamodel(sequence_number = 2), [
            (0, 4, 'Setting model variables - config 2'),
            (1, 4, 'Running model - config 2'),
            (1., 4, 'Running model - config 2: Running the grid module'),
            (1.5, 4, 'Running model - config 2: Running the generation module - Awaiting environmental data: wind speeds'),
            (2, 4, 'Running finance - config 2'),
            (3, 4, 'Saving results - config 2'),
        ])

    def test_single_configuration_counts_tasks_completed(self):
        # 0% to 75% as the tasks start; 100% is set by the worker when the run is complete
        fractions = [step / total for step, total, _ in self.run_metamodel(total_steps = common_deterministic.DETERMINISTIC_STEPS)]
        self.assertEqual(fractions[0], 0.)
        self.assertEqual(max(fractions), 0.75)
        self.assertEqual(sorted(fractions), fractions)

    def test_configurations_follow_each_other(self):
        # The second of two configurations runs from 50% to 87.5%, after the first's 0% to 37.5%
        n = common_deterministic.DETERMINISTIC_STEPS
        first = [step / total for step, total, _ in self.run_metamodel(start_step = 0, total_steps = 2 * n)]
        second = [step / total for step, total, _ in self.run_metamodel(start_step = n, total_steps = 2 * n)]
        self.assertEqual((first[0], max(first)), (0., 0.375))
        self.assertEqual((second[0], max(second)), (0.5, 0.875))

class TestRunsProgressMessage(unittest.TestCase):

    def test_names_the_run_underway(self):
        self.assertEqual(runs_progress_message('DSA', 0, 9, 0.), 'DSA: Run 1 of 9. Elapsed time: 0 seconds.')
        self.assertEqual(runs_progress_message('DSA', 2, 9, 3.), 'DSA: Run 3 of 9, 1.5 sec/run. Elapsed time: 3 seconds.')

    def test_complete(self):
        self.assertEqual(
            runs_progress_message('PSA (all configurations)', 9, 9, 12.),
            'PSA (all configurations): 9 of 9 runs complete. Elapsed time: 12 seconds.'
        )

class TestSingleDSAProgress(unittest.TestCase):
    """
    The DSA of one metamodel counts its model runs: the central run, and one at each bound of each
    selected variable.
    """

    def test_counts_model_runs(self):
        variables = []
        for name, selected in (('a', True), ('b', True), ('c', False)):
            v = mock.Mock(dsa_possible = True, dsa_selected = selected)
            v.name = name
            variables.append(v)
        mm = mock.MagicMock()
        mm.variables.values.return_value = variables
        calls = []
        with mock.patch.object(dsa, 'make_dsa_result', return_value = {}):
            dsa.run_dsa(mm, progress = lambda i, n: calls.append((i, n)))
        self.assertEqual(calls, [(i, 5) for i in range(6)])
        # One report for each model run, after the first
        self.assertEqual(mm.model.run.call_count, 5)
