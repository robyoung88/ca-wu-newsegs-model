"""
Unit tests for newsegsgeneration/sprakelocgeneration.

As for SprakeGeneration, plus the location-aware behaviour: setting the location of the module
passes only the point location to the generators, which keep their own height, pitch and aspect.
"""
import json
from typing import cast
import unittest

from newsegsmodelframework.util import jsonfuncs
from newsegsmodelframework.core import location
from newsegsmodelframework.newsegsgeneration import sprakegeneration, sprakelocgeneration
from newsegsmodelframework.newsegsgeneration import constructors as genconstructors

def _create_generation_module() -> sprakelocgeneration.SprakeLocGeneration:
    return sprakelocgeneration.SprakeLocGeneration(
        sprakegeneration.get_sprake_ned100(),
        location = location.RaisedLocation(50, -3, 10),
        name = 'Test generation module'
    )

class TestSprakeLocGenerationConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        inst = _create_generation_module()
        self.assertIsInstance(inst, sprakegeneration.SprakeGeneration)

        self.assertEqual(
            location.Location(inst.generator.generators[0].location),
            location.Location(inst.generator.generators[1].location),
        )

    def test_copy_construction(self):
        mod_gen1 = _create_generation_module()
        mod_gen2 = sprakelocgeneration.SprakeLocGeneration(mod_gen1)

        self.assertIsInstance(mod_gen2, sprakelocgeneration.SprakeLocGeneration)
        self.assertEqual(mod_gen1.location, mod_gen2.location)
        self.assertEqual(mod_gen1.generator.location, mod_gen2.generator.location)
        self.assertEqual(
            mod_gen1.generator.nameplate_capacity,
            mod_gen2.generator.nameplate_capacity
        )
        self.assertEqual(mod_gen1.name, mod_gen2.name)

        mod_gen2.generator.generators.clear()
        self.assertNotEqual(
            len(mod_gen1.generator.generators),
            len(mod_gen2.generator.generators)
        )

    def test_serialisation(self):
        mod_gen1 = _create_generation_module()

        mod_gen2 = cast(
            sprakelocgeneration.SprakeLocGeneration,
            genconstructors.generation_module_from_dict(mod_gen1.to_dict())
        )
        # The generic constructor must find the subclass, not SprakeGeneration
        self.assertIsInstance(mod_gen2, sprakelocgeneration.SprakeLocGeneration)

        self.assertEqual(mod_gen1.location, mod_gen2.location)
        for gen1, gen2 in zip(mod_gen1.generator.generators, mod_gen2.generator.generators):
            self.assertEqual(gen1.location, gen2.location)
            self.assertEqual(gen1.nameplate_capacity, gen2.nameplate_capacity)
        self.assertEqual(mod_gen1.name, mod_gen2.name)

    def test_json_serialisation(self):
        mod_gen1 = _create_generation_module()

        sd1 = json.dumps(mod_gen1.to_dict(), cls=jsonfuncs.NumpyEncoder)
        mod_gen2 = sprakelocgeneration.SprakeLocGeneration.from_dict(json.loads(sd1))

        self.assertIsInstance(mod_gen2, sprakelocgeneration.SprakeLocGeneration)
        self.assertEqual(mod_gen1.location, mod_gen2.location)
        for gen1, gen2 in zip(mod_gen1.generator.generators, mod_gen2.generator.generators):
            self.assertEqual(gen1.location, gen2.location)
            self.assertEqual(gen1.nameplate_capacity, gen2.nameplate_capacity)

class TestSprakeLocGenerationLocation(unittest.TestCase):
    """
    The location of the module is a point location, which the generators share.
    """

    def test_location_is_downcast(self):
        inst = _create_generation_module()
        inst.location = location.RaisedLocation(51.5, -0.1, 30)

        self.assertIs(type(inst.location), location.Location)
        self.assertEqual(inst.location, location.Location(51.5, -0.1))

    def test_generators_keep_their_heights(self):
        inst = _create_generation_module()
        heights = [
            cast(location.RaisedLocation, gen.location).height_agl
            for gen in inst.generator.generators
        ]

        inst.location = location.RaisedLocation(51.5, -0.1, 30)

        for gen, height in zip(inst.generator.generators, heights):
            self.assertEqual(location.Location(gen.location), location.Location(51.5, -0.1))
            self.assertEqual(cast(location.RaisedLocation, gen.location).height_agl, height)

    def test_location_survives_serialisation(self):
        inst = _create_generation_module()
        inst.location = location.RaisedLocation(51.5, -0.1, 30)

        inst2 = sprakelocgeneration.SprakeLocGeneration.from_dict(
            json.loads(json.dumps(inst.to_dict(), cls=jsonfuncs.NumpyEncoder))
        )

        self.assertEqual(inst2.location, location.Location(51.5, -0.1))
        for gen1, gen2 in zip(inst.generator.generators, inst2.generator.generators):
            self.assertEqual(gen1.location, gen2.location)
