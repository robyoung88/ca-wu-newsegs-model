"""
Unit tests for newsegsgeneration/sprakegeneration.

Focussing on ABC required behaviour.
"""
import json
from typing import cast
import unittest

from test.unit_tests.common import setup_test_env
setup_test_env()

from util import jsonfuncs
from core import location
from newsegsgeneration import sprakegeneration
from newsegsmodel import sprakemodel # Needed for e.g. the wind turbine
from newsegsgeneration import constructors as genconstructors

class TestSprakeGenerationConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        turbine = sprakegeneration.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)

        inst = sprakegeneration.SprakeGeneration(turbine)
        inst.set_location(loc)

        self.assertEqual(
            location.Location(inst.generator.generators[0].location),
            location.Location(inst.generator.generators[1].location),
        )

        d1 = inst.to_dict()

        turbine2 = sprakegeneration.get_sprake_gamesa_126()

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
        turbine = sprakegeneration.get_sprake_ned100()
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

        mod_gen2.generator.generators.clear()
        self.assertNotEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertNotEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
    
    def test_serialisation(self):
        turbine = sprakegeneration.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)
        mod_gen1 = sprakegeneration.SprakeGeneration(
            turbine,
            loc = loc, 
            name = 'Test generation module'
        )

        d1 = mod_gen1.to_dict()

        mod_gen2 = cast(
            sprakegeneration.SprakeGeneration,
            genconstructors.generation_module_from_dict(d1)
        )
        # The cast is for static type checking, this test proves the point:
        self.assertIsInstance(mod_gen2, sprakegeneration.SprakeGeneration)
        
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

        mod_gen2.generator.generators.clear()
        self.assertNotEqual(
            mod_gen1.generator.nameplate_capacity, 
            mod_gen2.generator.nameplate_capacity
        )
        self.assertNotEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )
    
    def test_json_serialisation(self):
        turbine = sprakegeneration.get_sprake_ned100()
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

        mod_gen2.update(d2)
        
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

    def test_update(self):
        """
        Testing update from other and partial updates.
        """
        turbine = sprakegeneration.get_sprake_ned100()
        loc = location.RaisedLocation(50, -3, 10)
        mod_gen_1 = sprakegeneration.SprakeGeneration(
            turbine,
            loc = loc, 
            name = 'Test generation module'
        )

        turbine_2 = sprakegeneration.get_sprake_gamesa_126()
        loc_2 = location.RaisedLocation(55, -2, 50)
        mod_gen_2 = sprakegeneration.SprakeGeneration(
            turbine_2,
            loc = loc_2,
            name = 'Target generation module'
        )

        self.assertNotEqual(mod_gen_1, mod_gen_2)
        self.assertNotEqual(mod_gen_1.location, mod_gen_2.location)

        update_dict_1 = {'location': mod_gen_1.location}
        mod_gen_2.update(update_dict_1)
        self.assertEqual(mod_gen_1.location, mod_gen_2.location)
        

        full_dict = mod_gen_1.to_dict()







