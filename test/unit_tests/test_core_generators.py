"""
Unit tests for core/generation/generators
"""
import unittest
import json

import numpy as np
import numpy.testing

from unit_tests.common import setup_test_env
setup_test_env()

from core import location
from core.generation import generators
from util import jsonfuncs

class TestWindTurbineElecGenerator(unittest.TestCase):

    def test_basic_construction(self):
        turb = generators.WindTurbineElecGenerator.from_none()
        self.assertEqual(turb.cp(3), 0)
        numpy.testing.assert_array_equal(
            turb.cp(np.asarray([5, 10])),
            [0.25, 0.4]
        )
    
    def test_json_reconstruction(self):
        turb = generators.WindTurbineElecGenerator.from_none()
        loc = location.Location(55, -4)
        turb.location = loc
        turb.hub_height = 25.

        d1 = turb.to_dict()
        turb2 = generators.WindTurbineElecGenerator.from_dict(d1)

        numpy.testing.assert_array_equal(
            turb2.cp(np.asarray([5, 10])),
            [0.25, 0.4]
        )

        # JSON serialisation / unserialisation
        sd1 = json.dumps(d1, cls=jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        turb3 = generators.WindTurbineElecGenerator.from_dict(d2)
        self.assertEqual(turb.location, turb3.location)
        self.assertEqual(turb.hub_height, turb3.hub_height)
        self.assertEqual(turb3.location.height_agl, turb3.hub_height)

        numpy.testing.assert_array_equal(
            turb3.cp(np.asarray([5, 10])),
            [0.25, 0.4]
        )

    def test_dictionary_sync(self):
        turb = generators.WindTurbineElecGenerator.from_none()
        loc = location.Location(55, -4)
        turb.location = loc
        turb.hub_height = 25.

        turb2 = generators.WindTurbineElecGenerator(turb)
        turb2.location.lat = 51
        self.assertNotEqual(turb.location, turb2.location)
        turb2.hub_height = 40.
        self.assertNotEqual(turb.hub_height, turb2.hub_height)

        d1 = turb2.to_dict()
        turb.sync_with_dict(d1)
        self.assertEqual(turb.location, turb2.location)
        self.assertEqual(turb.hub_height, turb2.hub_height)

class TestPowerPlantHomogeneousWind(unittest.TestCase):

    def test_basic_construction(self):
        pp = generators.PowerPlantHomogeneousWind.from_none()
        turb = generators.WindTurbineElecGenerator.from_none()
        self.assertEqual(pp.nameplate_capacity, turb.nameplate_capacity)

        pp.n = 5.5
        self.assertEqual(pp.nameplate_capacity, 5.5*turb.nameplate_capacity)

        pp.n_turbines = 2
        self.assertEqual(pp.nameplate_capacity, 2*turb.nameplate_capacity)

        pp.set_nameplate_capacity(50)
        self.assertEqual(pp.nameplate_capacity, 50)
        self.assertEqual(pp.n, 50 / turb.nameplate_capacity)
    
    def test_json_reconstruction(self):
        pp = generators.PowerPlantHomogeneousWind.from_none()
        loc = location.Location(55, -4)
        pp.location = loc
        pp.n = 5

        pp2 = generators.PowerPlantHomogeneousWind(pp)

        self.assertEqual(pp.nameplate_capacity, pp2.nameplate_capacity)
        self.assertEqual(pp.location, pp2.location)
        self.assertEqual(pp.turbine.location, pp2.turbine.location)

        pp2.location.lat = 50.
        self.assertNotEqual(pp.location, pp2.location)
        self.assertNotEqual(pp.turbine.location, pp2.turbine.location)

        d1 = pp2.to_dict()
        pp3 = generators.generator_from_dict(d1)
        self.assertEqual(pp2.location, pp3.location)
        self.assertEqual(pp2.turbine.location, pp3.turbine.location)

        sd1 = json.dumps(d1, cls=jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        pp.sync_with_dict(d2)
        self.assertEqual(pp.location, pp3.location)
        self.assertEqual(pp.turbine.location, pp3.turbine.location)

        pp3.turbine.hub_height *= 2
        self.assertNotEqual(pp.turbine.location, pp3.turbine.location)

class TestSprakePVGISElecGenerator(unittest.TestCase):

    def test_basic_construction(self):
        gen = generators.SprakePVGISElecGenerator.from_none()
        self.assertEqual(gen.nameplate_capacity, gen.peak_power)
    
    def test_json_reconstruction(self):
        gen = generators.SprakePVGISElecGenerator.from_none()
        loc = location.Location(55, -4)
        gen.location = loc
        gen.location.azimuth = 90.

        gen2 = generators.SprakePVGISElecGenerator(gen)
        self.assertEqual(gen.location, gen2.location)
        self.assertEqual(gen.nameplate_capacity, gen2.nameplate_capacity)

        gen2.peak_power *= 2
        self.assertNotEqual(gen.nameplate_capacity, gen2.nameplate_capacity)
        gen2.location.pitch = 30.
        self.assertNotEqual(gen.location, gen2.location)
        
        d1 = gen2.to_dict()
        gen3 = generators.generator_from_dict(d1)
        self.assertEqual(gen3.location, gen2.location)
        self.assertEqual(gen3.nameplate_capacity, gen2.nameplate_capacity)

        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)

        gen.sync_with_dict(d2)
        self.assertEqual(gen.location, gen2.location)
        self.assertEqual(gen.nameplate_capacity, gen2.nameplate_capacity)

class TestPowerPlantHomogeneousPV(unittest.TestCase):

    def test_basic_construction(self):
        pp = generators.PowerPlantHomogeneousPV.from_none()
        pv_array = generators.SprakePVGISElecGenerator.from_none()
        self.assertEqual(pp.nameplate_capacity, pv_array.nameplate_capacity)

        pp.n = 5.5
        self.assertEqual(pp.nameplate_capacity, 5.5*pv_array.nameplate_capacity)

        pp.n_arrays = 2
        self.assertEqual(pp.nameplate_capacity, 2*pv_array.nameplate_capacity)

        pp.set_nameplate_capacity(50)
        self.assertEqual(pp.nameplate_capacity, 50)
        self.assertEqual(pp.n, 50 / pv_array.nameplate_capacity)
    
    def test_json_reconstruction(self):
        pp = generators.PowerPlantHomogeneousPV.from_none()
        loc = location.Location(55, -4)
        pp.location = loc
        pp.n = 5

        pp2 = generators.PowerPlantHomogeneousPV(pp)

        self.assertEqual(pp.nameplate_capacity, pp2.nameplate_capacity)
        self.assertEqual(pp.location, pp2.location)
        self.assertEqual(pp.pv_array.location, pp2.pv_array.location)

        pp2.location.lat = 50.
        self.assertNotEqual(pp.location, pp2.location)
        self.assertNotEqual(pp.pv_array.location, pp2.pv_array.location)

        d1 = pp2.to_dict()
        pp3 = generators.generator_from_dict(d1)
        self.assertEqual(pp2.location, pp3.location)
        self.assertEqual(pp2.pv_array.location, pp3.pv_array.location)

        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)

        pp.sync_with_dict(d2)
        self.assertEqual(pp.location, pp3.location)
        self.assertEqual(pp.pv_array.location, pp3.pv_array.location)

        pp3.pv_array.location.azimuth = 120.
        self.assertNotEqual(pp.pv_array.location, pp3.pv_array.location)

class TestPowerPlantHeterogeneousGenerators(unittest.TestCase):

    def test_basic_construction(self):
        pp = generators.PowerPlantHeterogeneousGenerators.from_none()
        for gen in pp.generators:
            gen.set_nameplate_capacity(20.)
        
        self.assertEqual(pp.nameplate_capacity, len(pp.generators)*20.)
        g2 = generators.SprakePVGISElecGenerator.from_none()
        loc = location.AspectLocation(pp.location)
        loc.azimuth = 270.        
        g2.location = loc
        g2.peak_power = 20.
        pp.append(g2)
        self.assertEqual(pp.nameplate_capacity, len(pp.generators)*20.)

    def test_json_reconstruction(self):
        pp = generators.PowerPlantHeterogeneousGenerators.from_none()
        g2 = generators.SprakePVGISElecGenerator.from_none()
        loc = location.AspectLocation(pp.location)
        loc.azimuth = 270.        
        g2.location = loc
        g2.peak_power = 20.
        g4 = generators.PowerPlantHomogeneousPV(g2)
        pp.append(g4)

        pp.location = location.Location(60,-5)

        pp2 = generators.PowerPlantHeterogeneousGenerators(pp)

        self.assertEqual(pp.nameplate_capacity, pp2.nameplate_capacity)
        self.assertEqual(pp.location, pp2.location)

        pp2.location = location.Location(61, -5)
        g3 = generators.WindTurbineElecGenerator.from_none()
        g3.rated_power = 20.
        g3.location = pp2.location
        
        g5 = generators.PowerPlantHomogeneousWind(g3)
        pp2.append(g5)
        self.assertNotEqual(pp.nameplate_capacity, pp2.nameplate_capacity)
        self.assertNotEqual(pp.location, pp2.location)

        d1 = pp2.to_dict()

        pp3 = generators.generator_from_dict(d1)
        self.assertEqual(pp2.nameplate_capacity, pp3.nameplate_capacity)
        self.assertEqual(pp2.location, pp3.location)

        sd1 = json.dumps(d1, cls = jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        pp.sync_with_dict(d2)
        self.assertEqual(pp.nameplate_capacity, pp3.nameplate_capacity)
        self.assertEqual(pp.location, pp3.location)
    
    def test_location_propagation(self):
        pp = generators.PowerPlantHeterogeneousGenerators.from_none()        
        loc = location.Location(50, -3)
        pp.location = loc
        
