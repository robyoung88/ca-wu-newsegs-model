"""
Unit tests for newsegsgeneration/sprakegeneration.

Focussing on ABC required behaviour.
"""
import unittest
import json

from unit_tests.common import setup_test_env
setup_test_env()

from src.util import jsonfuncs
from src.core import location
from src.newsegsgeneration import sprakegeneration
from src.newsegsmodel import sprakemodel # Needed for e.g. the wind turbine
from src.newsegsgeneration import constructors as genconstructors

class TestSprakeGenerationConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        turbine = sprakemodel.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)

        inst = sprakegeneration.SprakeGeneration(turbine)
        inst.set_location(loc)

        self.assertEqual(
            location.Location(inst.generator.generators[0].location),
            location.Location(inst.generator.generators[1].location),
        )

        d1 = inst.to_dict()

        turbine2 = sprakemodel.get_sprake_gamesa_126()

        inst2 = sprakegeneration.SprakeGeneration.from_dict(d1)

        self.assertEqual(
            inst.generator.generators[0].location,
            inst2.generator.generators[0].location,
        )

        self.assertEqual(
            inst.generator.generators[1].location,
            inst2.generator.generators[1].location,
        )

        self.assertEqual(
            inst.generator.generators[0].nameplate_capacity,
            inst2.generator.generators[0].nameplate_capacity,
        )

        self.assertEqual(
            inst.generator.generators[1].nameplate_capacity,
            inst2.generator.generators[1].nameplate_capacity,
        )
    
    def test_copy_construction(self):
        turbine = sprakemodel.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)
        mod_gen1 = sprakegeneration.SprakeGeneration(
            turbine,
            loc = loc, 
            name = 'Test generation module'
        )

        mod_gen2 = sprakegeneration.SprakeGeneration(mod_gen1)
        
        self.assertEqual(mod_gen1.generator.location, mod_gen2.generator.location)
        self.assertEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
        self.assertEqual(mod_gen1.name, mod_gen2.name)

        mod_gen2.generator.clear()
        self.assertNotEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertNotEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
    
    def test_serialisation(self):
        turbine = sprakemodel.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)
        mod_gen1 = sprakegeneration.SprakeGeneration(
            turbine,
            loc = loc, 
            name = 'Test generation module'
        )

        d1 = mod_gen1.to_dict()

        mod_gen2 = genconstructors.generation_module_from_dict(d1)
        
        self.assertEqual(mod_gen1.generator.location, mod_gen2.generator.location)
        self.assertEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
        self.assertEqual(mod_gen1.name, mod_gen2.name)

        mod_gen2.generator.clear()
        self.assertNotEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertNotEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
    
    def test_json_serialisation(self):
        turbine = sprakemodel.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)
        mod_gen1 = sprakegeneration.SprakeGeneration(
            turbine,
            loc = loc, 
            name = 'Test generation module'
        )

        d1 = mod_gen1.to_dict()

        sd1 = json.dumps(d1, cls=jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        # No 'from none' for SprakeGeneration as always need a turbine
        mod_gen2 = sprakegeneration.SprakeGeneration(turbine)
        mod_gen2.sync_with_dict(d2)
        
        self.assertEqual(mod_gen1.generator.location, mod_gen2.generator.location)
        self.assertEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
        self.assertEqual(mod_gen1.name, mod_gen2.name)

        mod_gen2.generator.clear()
        self.assertNotEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertNotEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )



