"""
Unit tests for newsegsmodel/sprakemodel.
"""
import unittest
import json

import numpy.testing

from unit_tests.common import setup_test_env
setup_test_env()

from src.util import jsonfuncs
from src.core import location
from src.newsegsmodel import sprakemodel
from src.newsegsgeneration import sprakegeneration
from src.newsegsgrid import sprakegrid
from src.newsegscs import sprakecs

class TestSprakeModelConfigEqualities(unittest.TestCase):
    """
    Tests for creating, serialising and restoring the model config.

    Running and results not considered in this test suite.
    """

    def test_basic_construction(self):
        mdl = sprakemodel.SprakeModel.from_none()
        self.assertIsInstance(mdl.generation, sprakegeneration.SprakeGeneration)
        self.assertIsInstance(mdl.grid, sprakegrid.SprakeGrid)
        self.assertIsInstance(mdl.consumption_storage, sprakecs.SprakeCS)

        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        self.assertEqual(mdl.generation.generator.nameplate_capacity, 200)
    
    def test_copy_construction(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.appliance_params['efficiency_reduction'] = 0.5

        mdl2 = sprakemodel.SprakeModel(mdl)
        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(
            mdl.grid.import_rate,
            mdl2.grid.import_rate
        )
        self.assertDictEqual(
            mdl.consumption_storage.appliance_params,
            mdl2.consumption_storage.appliance_params
        )
    
    def test_serialisation(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.appliance_params['efficiency_reduction'] = 0.5

        d1 = mdl.to_dict()

        mdl2 = sprakemodel.SprakeModel.from_dict(d1)

        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(
            mdl.grid.import_rate,
            mdl2.grid.import_rate
        )
        self.assertDictEqual(
            mdl.consumption_storage.appliance_params,
            mdl2.consumption_storage.appliance_params
        )
    
    def test_json_serialisation(self):
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.appliance_params['efficiency_reduction'] = 0.5

        d1 = mdl.to_dict()

        sd1 = json.dumps(d1, cls = jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        mdl2 = sprakemodel.SprakeModel.from_none()
        mdl2.sync_with_dict(d2)

        self.assertEqual(
            mdl.generation.generator.nameplate_capacity,
            mdl2.generation.generator.nameplate_capacity
        )
        self.assertEqual(
            mdl.grid.import_rate,
            mdl2.grid.import_rate
        )
        self.assertDictEqual(
            mdl.consumption_storage.appliance_params,
            mdl2.consumption_storage.appliance_params
        )

class TestSprakeModelRun(unittest.TestCase):
    """
    Tests for basic operation of model run.
    """

    def test_default_run(self):
        mdl = sprakemodel.SprakeModel.from_none()
        self.assertTrue(mdl.dirty)
        mdl.run()
        self.assertFalse(mdl.dirty)
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
        mdl = sprakemodel.SprakeModel.from_none()
        mdl.generation.generator.generators[0].set_nameplate_capacity(200.)
        mdl.generation.generator.generators[1].set_nameplate_capacity(0.)
        mdl.grid.import_rate = 0.5
        mdl.consumption_storage.appliance_params['efficiency_reduction'] = 0.5
        mdl.run()

        gen_meters_1 = mdl.get_generation_result().meters_to_pandas()
        cs_meters_1 = mdl.get_consumption_storage_result().meters_to_pandas()

        d1 = mdl.to_dict()

        sd1 = json.dumps(d1, cls = jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        mdl2 = sprakemodel.SprakeModel.from_dict(d2)
        mdl2.run()
        numpy.testing.assert_array_equal(
            gen_meters_1.to_numpy(),
            mdl2.get_generation_result().meters_to_pandas().to_numpy()
        )
        numpy.testing.assert_array_equal(
            cs_meters_1.to_numpy(),
            mdl2.get_consumption_storage_result().meters_to_pandas().to_numpy()
        )
