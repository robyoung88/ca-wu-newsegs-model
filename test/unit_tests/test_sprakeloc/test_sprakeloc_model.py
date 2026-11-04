"""
Unit tests for newsegsmodel/sprakelocmodel.

The location-aware model fetches its environment from PVGIS and NEWA. So that the tests run
offline, the runs here use the Sprake environment servers instead, except for
`TestSprakeLocModelNetworkRun`, which runs only when the environment variable
`NEWSEGS_NETWORK_TESTS` is set to `1`.
"""
import json
import os
import unittest

import numpy as np
import numpy.testing

from newsegsmodelframework.core import location
from newsegsmodelframework.core.environment import dummy_env_servers, pvgis_newa_env_servers
from newsegsmodelframework.core.timespan.timespan import TimeSpan
from newsegsmodelframework.newsegsmodel import sprakemodel, sprakelocmodel
from newsegsmodelframework.newsegsgeneration import sprakegeneration, sprakelocgeneration
from newsegsmodelframework.newsegsgrid import sprakegrid
from newsegsmodelframework.newsegscs import sprakecs

def _create_model() -> sprakelocmodel.SprakeLocModel:
    mdl = sprakelocmodel.SprakeLocModel.from_none()
    mdl.generation.wind_capacity = 200.
    mdl.generation.pv_capacity = 50.
    mdl.grid.import_rate = 0.5
    mdl.consumption_storage.efficiency_reduction = 0.5
    return mdl

def _use_offline_environment(mdl: sprakelocmodel.SprakeLocModel) -> None:
    mdl.local_env = sprakemodel.get_sprake_environment_server()
    mdl.wider_env = sprakemodel.get_sprake_wider_env_server()
    # The Sprake wind speeds are at the height of the Sprake turbine only
    mdl.generation.generator.generators[0].turbine.hub_height = sprakegeneration.NOMINAL_WT_HEIGHT # pyright: ignore[reportAttributeAccessIssue]
    mdl.generation.generator.chain_syncronise()

class TestSprakeLocModelConfigEqualities(unittest.TestCase):
    """
    Tests for creating, serialising and restoring the model config.

    Running and results not considered in this test suite.
    """

    def assertModelsEqual(self, mdl: sprakelocmodel.SprakeLocModel, mdl2: sprakelocmodel.SprakeLocModel):
        self.assertIsInstance(mdl2, sprakelocmodel.SprakeLocModel)
        self.assertIsInstance(mdl2.generation, sprakelocgeneration.SprakeLocGeneration)
        self.assertEqual(mdl.generation.location, mdl2.generation.location)
        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(mdl.grid.import_rate, mdl2.grid.import_rate)
        self.assertDictEqual(
            mdl.consumption_storage.get_appliance_params(),
            mdl2.consumption_storage.get_appliance_params()
        )

    def test_basic_construction(self):
        mdl = sprakelocmodel.SprakeLocModel.from_none()
        self.assertEqual(mdl.model_type, 'sprakeloc')
        self.assertIsInstance(mdl.generation, sprakelocgeneration.SprakeLocGeneration)
        self.assertIsInstance(mdl.grid, sprakegrid.SprakeGrid)
        self.assertIsInstance(mdl.consumption_storage, sprakecs.SprakeCS)

        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        self.assertEqual(mdl.generation.generator.nameplate_capacity, 200)

    def test_default_environment_servers(self):
        mdl = sprakelocmodel.SprakeLocModel.from_none()
        self.assertIsInstance(mdl.local_env, pvgis_newa_env_servers.HourlyPVGISNEWALocalEnv)
        self.assertIsInstance(mdl.wider_env, dummy_env_servers.DummyWiderEnv)

    def test_copy_construction(self):
        mdl = _create_model()
        mdl2 = sprakelocmodel.SprakeLocModel(mdl)
        self.assertModelsEqual(mdl, mdl2)

    def test_not_copied_from_sprake_model(self):
        with self.assertRaises(TypeError):
            sprakelocmodel.SprakeLocModel(sprakemodel.SprakeModel.from_none())

    def test_serialisation(self):
        mdl = _create_model()

        # Use the without component server form
        mdl2 = sprakelocmodel.SprakeLocModel.from_dict(mdl.to_dict_repr())
        self.assertModelsEqual(mdl, mdl2)

    def test_json_serialisation(self):
        mdl = _create_model()
        mdl.generation.location = location.Location(51.5, -0.1)

        mdl2 = sprakelocmodel.SprakeLocModel.from_dict(json.loads(mdl.json_dumps_repr()))
        self.assertModelsEqual(mdl, mdl2)

    def test_not_restored_as_sprake_model(self):
        mdl = _create_model()
        with self.assertRaises(ValueError):
            sprakemodel.SprakeModel.from_dict(json.loads(mdl.json_dumps_repr()))

class TestSprakeLocModelLocation(unittest.TestCase):
    """
    The location of the model determines the location of the generators.
    """

    def assertLocationReachesGenerators(self, mdl: sprakelocmodel.SprakeLocModel, loc: location.Location):
        self.assertEqual(mdl.location, loc)
        self.assertEqual(mdl.generation.location, loc)
        for gen in mdl.generation.generator.generators:
            self.assertEqual(location.Location(gen.location), loc)

    def test_location_reaches_generators(self):
        mdl = _create_model()
        heights = [gen.location.height_agl for gen in mdl.generation.generator.generators] # pyright: ignore[reportAttributeAccessIssue]

        loc = location.Location(51.5, -0.1)
        mdl.location = loc

        self.assertLocationReachesGenerators(mdl, loc)
        # The generators keep their own heights
        self.assertEqual(
            heights,
            [gen.location.height_agl for gen in mdl.generation.generator.generators] # pyright: ignore[reportAttributeAccessIssue]
        )

    def test_location_survives_serialisation(self):
        mdl = _create_model()
        loc = location.Location(51.5, -0.1)
        mdl.location = loc

        mdl2 = sprakelocmodel.SprakeLocModel.from_dict(json.loads(mdl.json_dumps_repr()))
        self.assertLocationReachesGenerators(mdl2, loc)

    def test_location_of_copy_is_independent(self):
        mdl = _create_model()
        original_location = mdl.location
        mdl2 = sprakelocmodel.SprakeLocModel(mdl)

        mdl2.location = location.Location(51.5, -0.1)

        self.assertLocationReachesGenerators(mdl, original_location)
        self.assertLocationReachesGenerators(mdl2, location.Location(51.5, -0.1))

class TestSprakeLocModelRun(unittest.TestCase):
    """
    Tests for basic operation of model run, using the Sprake environment servers.
    """

    def test_default_run(self):
        mdl = sprakelocmodel.SprakeLocModel.from_none()
        _use_offline_environment(mdl)
        mdl.run()
        self.assertIsInstance(
            mdl.get_generation_result(),
            sprakegeneration.SprakeGenerationResult
        )
        self.assertIsInstance(
            mdl.get_grid_result(),
            sprakegrid.SprakeGridResult
        )
        self.assertIsInstance(
            mdl.get_cs_result(),
            sprakecs.SprakeCSResult
        )

    def test_post_serialisation_run_stability(self):
        mdl = _create_model()
        _use_offline_environment(mdl)
        mdl.run()

        gen_meters_1 = mdl.get_generation_result().meters_to_pandas()
        cs_meters_1 = mdl.get_consumption_storage_result().meters_to_pandas()

        mdl2 = sprakelocmodel.SprakeLocModel.from_dict(json.loads(mdl.json_dumps_repr()))
        # The environment servers are not serialised
        _use_offline_environment(mdl2)
        mdl2.run()
        numpy.testing.assert_array_equal(
            gen_meters_1.to_numpy(),
            mdl2.get_generation_result().meters_to_pandas().to_numpy()
        )
        numpy.testing.assert_array_equal(
            cs_meters_1.to_numpy(),
            mdl2.get_consumption_storage_result().meters_to_pandas().to_numpy()
        )

@unittest.skipUnless(
    os.environ.get('NEWSEGS_NETWORK_TESTS') == '1',
    'Fetches data from PVGIS and NEWA; set NEWSEGS_NETWORK_TESTS=1 to run'
)
class TestSprakeLocModelNetworkRun(unittest.TestCase):
    """
    A run with the PVGIS and NEWA environment, over a year to limit the data fetched.
    """

    def test_one_year_run(self):
        mdl = sprakelocmodel.SprakeLocModel.from_none()
        mdl.set_run_period(TimeSpan('2010-01-01', '2011-01-01', tz = 'utc'))
        mdl.run()

        gen_meters = mdl.get_generation_result().meters_to_pandas()
        self.assertEqual(len(gen_meters), 8761)
        self.assertFalse(np.isnan(gen_meters.to_numpy()).any())
        # Both generators produce, and neither exceeds its capacity
        self.assertTrue((gen_meters.mean() > 0).all())
        self.assertTrue((gen_meters.max() <= 1.01 * mdl.generation.generator.nameplate_capacity).all())
