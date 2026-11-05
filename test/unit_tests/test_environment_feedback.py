"""
Unit tests for the feedback on the environmental conditions of a site: the registers, the status and
drawing logic of `environment_feedback_callbacks`, the page layouts, and the data source and artists
of the `sprakeloc` model type.

The PVGIS and NEWA fetches are replaced by fakes giving synthetic data over the default run period,
so that the tests run offline, and each test uses its own cache in a temporary directory.
"""
import json
import tempfile
import unittest
from unittest import mock

from dash import dcc, html
import diskcache
import numpy as np
import pandas as pd

# Fill the registers, as the app does on import
import newsegsmodelframework.register_plugins  # noqa: F401
import newsegsmodelapp.register_plugins  # noqa: F401

from newsegsmodelapp import registers
from newsegsmodelapp.components.callbacks import environment_feedback_callbacks as efc
from newsegsmodelapp.plugins.models.sprakeloc.page_contents import environment_feedback as sle
from newsegsmodelapp.plugins.pages.p100_model_configuration_layout import create_model_configuration_layout
from newsegsmodelframework.core.environment import environment_cache, pvgis_newa_env_servers
from newsegsmodelframework.core.environment.environment_servers import EnvironmentDataUnavailableError
from newsegsmodelframework.core.location.location import Location
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

_SITE = Location(53.255, -3.477)
_OTHER_SITE = Location(51.5, -0.1)

def _fake_wind_at_site(lat, lon, rng, dt_start, dt_stop, site_heights):
    times = pd.date_range(dt_start, dt_stop, freq = '30min')
    hours = np.arange(len(times))
    return pd.DataFrame({
        'time': times,
        'hub_height': site_heights[0],
        # Varies by year, so that the years have different means
        'ws_hub': 6. + 2. * np.sin(hours / 500.) + (times.year - 2005) / 2.,
        'wind_from_direction_10m': (hours * 7.) % 360.,
    })

def _fake_pvgis_hourly(lat, lon, start, end, surface_tilt = 0., surface_azimuth = 180., **kwargs):
    times = pd.date_range(start + pd.Timedelta(10, 'm'), end, freq = 'h', name = 'time')
    daylight = np.clip(np.sin(np.pi * (times.hour - 6) / 12.), 0., None)
    # Planes facing south receive the most
    facing = np.cos(np.deg2rad(surface_azimuth - 180.)) * 0.3 + 1.
    return pd.DataFrame({
        'poa_global': 400. * daylight * facing,
        'poa_direct': 200. * daylight * facing,
        'temp_air': 10. - 8. * np.cos(2. * np.pi * (times.dayofyear - 15) / 365.) + lon,
    }, index = times), {}

def _fake_pvgis_horizon(lat, lon, **kwargs):
    azimuths = np.arange(0., 361., 7.5)
    return pd.Series(2. + np.sin(np.deg2rad(azimuths)), index = azimuths, name = 'horizon_elevation'), {}

class FakeSourceTestCase(unittest.TestCase):
    """The `sprakeloc` server, with its own cache and fake remote services."""

    def setUp(self):
        self._dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.cache = diskcache.Cache(self._dir.name)
        self.server = pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv(self.cache)
        mock.patch.object(sle, '_server', return_value = self.server).start()
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
        self.source = sle.SprakeLocEnvironmentData()
        # The default configuration of a new project in the app
        self.metamodel = PROJECT_FACTORIES['sprakeloc']().get_focussed_metamodel()
        self.config = sle.SiteConfiguration.from_metamodel(self.metamodel)

    def tearDown(self):
        self.cache.close()
        self._dir.cleanup()

class TestSprakeLocEnvironmentData(FakeSourceTestCase):

    def test_registered(self):
        self.assertIsInstance(registers.get_environment_data_source('sprakeloc'), sle.SprakeLocEnvironmentData)
        self.assertIsNone(registers.get_environment_data_source('sprake'))

    def test_configuration(self):
        # The heights of the generators of the configuration, which are those runs use
        plants = self.metamodel.model.generation.generator.generators
        self.assertEqual(self.config.turbine_height, plants[0].location.height_agl)
        self.assertEqual(self.config.pv_height, plants[1].location.height_agl)
        self.assertEqual(self.config.timespan, self.metamodel.model.run_period)

    def test_fetch_makes_available(self):
        self.assertFalse(self.source.is_available(_SITE, self.metamodel))
        self.source.fetch(_SITE, self.metamodel)
        self.assertTrue(self.source.is_available(_SITE, self.metamodel))
        self.assertFalse(self.source.is_available(_OTHER_SITE, self.metamodel))
        # Wind at the turbine and the PV heights, the horizontal data once and each plane once,
        # and the horizon once
        self.assertEqual(
            sorted(c.kwargs['site_heights'][0] for c in self.wind.call_args_list),
            sorted([round(self.config.turbine_height), round(self.config.pv_height)])
        )
        self.assertEqual(self.pvgis.call_count, 1 + len(sle.PV_AZIMUTHS))
        self.horizon.assert_called_once()

        # Nothing is fetched again
        self.source.fetch(_SITE, self.metamodel)
        self.assertEqual(self.wind.call_count, 2)

    def test_depends_on_turbine_height(self):
        self.source.fetch(_SITE, self.metamodel)
        self.metamodel.model.generation.generator.generators[0].turbine.hub_height = self.config.turbine_height + 5.
        self.assertFalse(self.source.is_available(_SITE, self.metamodel))

    def test_run_after_fetch_fetches_nothing(self):
        # A run of the configuration at the site uses only the data the feedback fetched
        self.source.fetch(_SITE, self.metamodel)
        for fetch in (self.wind, self.pvgis, self.horizon):
            fetch.reset_mock()
        model = self.metamodel.model
        model.local_env = self.server
        model.location = Location(_SITE.lat, _SITE.lon)
        model.run()
        self.wind.assert_not_called()
        self.pvgis.assert_not_called()

    def test_pending_while_another_process_fetches(self):
        self.assertFalse(self.source.is_pending(_SITE, self.metamodel))
        _, lock_key = self.server._cache_key(
            'wind_speeds', sle._raised(_SITE, self.config.turbine_height), self.config.timespan
        )
        lock = environment_cache._lock(lock_key, self.cache)
        lock.acquire()
        try:
            self.assertTrue(self.source.is_pending(_SITE, self.metamodel))
            self.assertFalse(self.source.is_pending(_OTHER_SITE, self.metamodel))
        finally:
            lock.release()
        self.assertFalse(self.source.is_pending(_SITE, self.metamodel))

class TestSprakeLocArtists(FakeSourceTestCase):

    def setUp(self):
        super().setUp()
        self.source.fetch(_SITE, self.metamodel)
        self.wind.reset_mock()
        self.pvgis.reset_mock()
        self.horizon.reset_mock()

    def assert_nothing_fetched(self):
        self.wind.assert_not_called()
        self.pvgis.assert_not_called()
        self.horizon.assert_not_called()

    def draw(self, key, sites = ()):
        return registers.get_environment_feedback_artist(key, 'sprakeloc')(_SITE, list(sites), self.metamodel)

    def test_wind_rose(self):
        graph = self.draw('wind-rose')
        self.assertIsInstance(graph, dcc.Graph)
        traces = graph.figure.data
        # The proportions of all directions and speeds sum to 100%
        self.assertAlmostEqual(sum(float(np.sum(t.r)) for t in traces), 100., places = 6)
        self.assertTrue(all(len(t.r) == sle.WIND_ROSE_SECTORS for t in traces))
        self.assertIn('Mean wind speed', graph.figure.layout.annotations[0].text)
        self.assertEqual(graph.figure.layout.title.text, f'Wind rose at {self.config.turbine_height:g} m')
        self.assert_nothing_fetched()

    def test_wind_speed_distribution(self):
        graph = self.draw('wind-speed-distribution')
        names = [t.name for t in graph.figure.data]
        self.assertTrue(any(n.startswith('Mean') for n in names))
        # The fake speeds rise each year
        self.assertTrue(any(n.startswith('Lowest year (2005)') for n in names))
        self.assertTrue(any(n.startswith('Highest year (2014)') for n in names))
        self.assertIn('kWh/m²', graph.figure.layout.annotations[0].text)
        self.assert_nothing_fetched()

    def test_sun_path(self):
        graph = self.draw('sun-path')
        names = [t.name for t in graph.figure.data if t.name]
        self.assertEqual(names, ['Horizon', '21 June', '20 March', '21 December'])
        # The sun is highest at the summer solstice
        june, december = graph.figure.data[1], graph.figure.data[5]
        self.assertGreater(max(june.y), max(december.y))
        self.assert_nothing_fetched()

    def test_external_temperature_of_cached_sites_only(self):
        uncached = Location(52., -1.)
        self.source.fetch(_OTHER_SITE, self.metamodel)
        for fetch in (self.wind, self.pvgis, self.horizon):
            fetch.reset_mock()
        graph = self.draw('external-temperature', [('Other site', _OTHER_SITE), ('Uncached site', uncached)])
        names = [t.name for t in graph.figure.data]
        self.assertEqual(names, ['Other site', 'This site'])
        self.assertEqual(len(graph.figure.data[-1].y), 12)
        self.assert_nothing_fetched()

    def test_generation_potential(self):
        table = sle.generation_potential(_SITE, self.metamodel)
        self.assertEqual(list(table['Technology']), ['Wind'] + ['PV'] * len(sle.PV_AZIMUTHS))
        self.assertEqual(table['Position'].iloc[0], f'{self.config.turbine_height:g} m hub height')
        self.assertTrue((table['Annual production'] > 0).all())
        pv = table[table['Technology'] == 'PV'].set_index('Position')['Annual production']
        self.assertEqual(pv.idxmax(), 'South, 35° pitch')
        self.assertIsInstance(self.draw('generation-potential'), html.Div)
        self.assert_nothing_fetched()

    def test_annual_specific_wind_energy(self):
        # A constant wind gives the turbine's power at that speed for every hour of the year
        speeds = pd.Series(np.full(8766, 8.), index = pd.date_range('2005-01-01', periods = 8766, freq = 'h'))
        cp = self.config.cp
        expected = 0.5 * 1.225 * float(cp(np.asarray([8.]))[0]) * 8.**3 / 1000. * 8766.
        self.assertAlmostEqual(sle.annual_specific_wind_energy(speeds, 1.225, cp), expected, places = 6)

class _Source:
    """A data source whose state is set by the test."""
    def __init__(self, available = False, pending = False):
        self.available = available
        self.pending = pending
    def is_available(self, location, metamodel):
        return self.available
    def is_pending(self, location, metamodel):
        return self.pending
    def fetch(self, location, metamodel):
        pass

_METAMODEL = mock.Mock(id = 'metam-test')
_READY = json.dumps({'site': '53.255,-3.477', 'metamodel_id': 'metam-test'})

class TestStatus(unittest.TestCase):

    def test_site_location(self):
        self.assertEqual(efc.site_location(json.dumps({'lat': 53.2, 'lon': -3.4, 'name': 'A'})), Location(53.2, -3.4))
        for value in (None, '', '{}', json.dumps({'lat': None, 'lon': -3.4}), 'not json'):
            self.assertIsNone(efc.site_location(value), value)

    def test_location_key(self):
        self.assertEqual(efc.location_key(Location(53.25535, -3.47697)), '53.255,-3.477')
        self.assertEqual(efc.location_from_key('53.255,-3.477'), Location(53.255, -3.477))

    def test_unset(self):
        for location, metamodel in ((None, _METAMODEL), (_SITE, None)):
            status = efc.get_status(_Source(available = True), location, metamodel)
            self.assertEqual(status.status, 'unset')
            self.assertFalse(status.can_fetch)
            self.assertIsNone(status.ready)

    def test_available(self):
        status = efc.get_status(_Source(available = True), _SITE, _METAMODEL)
        self.assertEqual((status.status, status.can_fetch, status.ready, status.stale), ('available', False, _READY, False))
        self.assertEqual(status.message, '')

    def test_missing(self):
        status = efc.get_status(_Source(), _SITE, _METAMODEL)
        self.assertEqual((status.status, status.can_fetch, status.ready, status.stale), ('missing', True, None, True))

    def test_pending(self):
        for status in (
            efc.get_status(_Source(pending = True), _SITE, _METAMODEL),
            efc.get_status(_Source(), _SITE, _METAMODEL, fetch_requested = True),
        ):
            self.assertEqual((status.status, status.can_fetch, status.stale), ('pending', False, True))

    def test_failed(self):
        result = {'key': '53.255,-3.477', 'error': 'Unable to obtain wind speeds'}
        status = efc.get_status(_Source(), _SITE, _METAMODEL, result)
        self.assertEqual((status.status, status.message, status.can_fetch), ('failed', 'Unable to obtain wind speeds', True))
        # The error of another site is not shown
        self.assertEqual(efc.get_status(_Source(), _OTHER_SITE, _METAMODEL, result).status, 'missing')

    def test_fetch_errors_reported(self):
        source = _Source()
        self.assertEqual(efc.fetch_environment_data(source, _SITE, _METAMODEL), {'key': '53.255,-3.477', 'error': None})
        source.fetch = mock.Mock(side_effect = EnvironmentDataUnavailableError('Unable to obtain the horizon'))
        self.assertEqual(efc.fetch_environment_data(source, _SITE, _METAMODEL)['error'], 'Unable to obtain the horizon')
        source.fetch = mock.Mock(side_effect = RuntimeError('internal'))
        with self.assertLogs(efc.logger, 'ERROR'):
            self.assertEqual(
                efc.fetch_environment_data(source, _SITE, _METAMODEL)['error'], 'The environmental data could not be fetched'
            )

    def test_focussed_metamodel(self):
        provider = mock.Mock()
        lmm = mock.Mock(id = 'metam-2')
        provider.get_lightweight_project.return_value = mock.Mock(metamodels = [mock.Mock(), lmm], focussed_metamodel_index = 1)
        provider.metamodel_provider.get_component.return_value = _METAMODEL
        self.assertIs(efc.focussed_metamodel(provider, 'proj-1'), _METAMODEL)
        provider.metamodel_provider.get_component.assert_called_once_with('metam-2')
        self.assertIsNone(efc.focussed_metamodel(provider, ''))
        provider.get_lightweight_project.side_effect = KeyError('Project not found')
        self.assertIsNone(efc.focussed_metamodel(provider, 'proj-missing'))

    def test_other_sites(self):
        lmms = []
        for name, loc in [
            ('Config 1', Location(53.2551, -3.4772, name = 'Same site')),
            ('Config 2', Location(51.5, -0.1, name = 'London')),
            ('Config 3', Location(51.5001, -0.1, name = 'London again')),
            ('Config 4', Location(52., -1.)),
        ]:
            lmm = mock.Mock(location = loc)
            # `name` is an argument of Mock, so is set afterwards
            lmm.name = name
            lmms.append(lmm)
        sites = efc.other_sites(mock.Mock(metamodels = lmms), _SITE)
        # An unnamed site is named by its co-ordinates
        self.assertEqual([name for name, _ in sites], ['London', 'Site at 52.000, -1.000'])

class TestDrawItems(unittest.TestCase):

    def setUp(self):
        self.artists = mock.patch.dict(registers.ENVIRONMENT_FEEDBACK_ARTISTS, clear = False).start()
        self.addCleanup(mock.patch.stopall)

    def test_draws_with_artists(self):
        registers.ENVIRONMENT_FEEDBACK_ARTISTS[('test-ok', 'test-model')] = lambda loc, sites, mm: html.Span(f'{loc.lat}:{len(sites)}:{mm.id}')
        registers.ENVIRONMENT_FEEDBACK_ARTISTS[('test-fails', 'default')] = mock.Mock(side_effect = ValueError)
        with self.assertLogs(efc.logger, 'ERROR'):
            children = efc.draw_items(
                [{'key': 'test-ok'}, {'key': 'test-fails'}, {'key': 'test-missing'}],
                'test-model', _SITE, [('Other', _OTHER_SITE)], _METAMODEL
            )
        self.assertEqual(children[0].children, '53.255:1:metam-test')
        self.assertEqual(children[1].children, 'This feedback could not be drawn')
        self.assertIsNone(children[2])

class TestRegisters(unittest.TestCase):

    def setUp(self):
        mock.patch.dict(registers.ENVIRONMENT_FEEDBACK_ARTISTS, clear = False).start()
        mock.patch.dict(registers.ENVIRONMENT_DATA_SOURCES, clear = False).start()
        self.addCleanup(mock.patch.stopall)

    def test_artist_fallback(self):
        first = registers.register_environment_feedback_artist('test-item', 'model-a')(lambda loc, sites, mm: 'a')
        registers.register_environment_feedback_artist('test-item', 'model-b')(lambda loc, sites, mm: 'b')
        self.assertIs(registers.get_environment_feedback_artist('test-item', 'model-c'), first)
        self.assertEqual(registers.get_environment_feedback_artist('test-item', 'model-b')(None, [], None), 'b')
        with self.assertRaises(KeyError):
            registers.register_environment_feedback_artist('test-item', 'model-a')(lambda loc, sites, mm: 'again')
        with self.assertRaises(KeyError):
            registers.get_environment_feedback_artist('test-no-item')

    def test_one_source_per_model_type(self):
        registers.register_environment_data_source(_Source(), 'test-model')
        with self.assertRaises(KeyError):
            registers.register_environment_data_source(_Source(), 'test-model')

def _visibility(component, id_, hidden = False):
    """Whether the component with an id is visible, or None if it is not in a layout"""
    hidden = hidden or (getattr(component, 'style', None) or {}).get('display') == 'none'
    if getattr(component, 'id', None) == id_:
        return not hidden
    children = getattr(component, 'children', None)
    if children is None:
        return None
    for child in children if isinstance(children, (list, tuple)) else [children]:
        found = _visibility(child, id_, hidden)
        if found is not None:
            return found
    return None

class TestLayout(unittest.TestCase):

    def test_feedback_shown_only_for_model_types_with_it(self):
        # Model types without it have its components hidden, for its callbacks
        for model_type, expected in (('sprakeloc', True), ('sprake', False), ('default', False)):
            layout = create_model_configuration_layout(registers.get_page_layout_configuration('site-config', model_type))
            for id_ in ('btn-fetch-environment-data', 'environment-feedback-details'):
                self.assertEqual(_visibility(layout, id_), expected, (model_type, id_))

    def test_sprakeloc_items(self):
        layout = str(create_model_configuration_layout(registers.get_page_layout_configuration('site-config', 'sprakeloc')))
        for item in sle.ITEMS:
            self.assertIn(repr(item.key), layout)
            registers.get_environment_feedback_artist(item.key, 'sprakeloc')
