"""
Unit tests for core/location
"""
import unittest

import json

# Ensure we can find modules


from newsegsmodelframework.core import location

class TestLocationEqualities(unittest.TestCase):

    def test_location_equality(self):
        l1 = location.Location(50.0, -3.0)
        l2 = location.Location(l1)
        self.assertEqual(l1, l2)
        l2 = l2 + (20, -10)
        self.assertNotEqual(l1, l2)
        l2 = l2 - (20, -10)
        # The lossy transformations result in inexact equality
        self.assertAlmostEqual(l1.lat, l2.lat)
        self.assertAlmostEqual(l1.lon, l2.lon)
        #self.assertEqual(l1, l2)

    def test_raisedlocation_equality(self):
        l1 = location.RaisedLocation(50., -3., 10.)
        l2 = location.Location(l1)
        self.assertEqual(l1, l2)
        self.assertEqual(l2, l1)
        l3 = location.RaisedLocation(l2)
        self.assertNotEqual(l1, l3)
        l3.height_agl = l1.height_agl
        self.assertEqual(l1, l3)

    def test_aspectlocation_equality(self):
        l1 = location.AspectLocation(50., -3., 10., 270., 35.)
        l2 = location.Location(l1)
        self.assertEqual(l1, l2)
        l2 = location.RaisedLocation(l1)
        self.assertEqual(l1, l2)
        l3 = location.AspectLocation(l2)
        self.assertNotEqual(l1, l3)
        l3.azimuth = 270
        l3.pitch = 35
        self.assertEqual(l1, l3)

class TestLocationRecovery(unittest.TestCase):
    def test_location_recovery(self):
        l1 = location.Location(50.0, -3.0)
        d1 = l1.to_dict()
        l2 = location.location_from_dict(d1)
        self.assertEqual(l1, l2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        l3 = location.location_from_dict(d2)
        self.assertEqual(l1, l3)
    
    def test_raisedlocation_equality(self):
        l1 = location.RaisedLocation(50., -3., 10.)
        d1 = l1.to_dict()
        l2 = location.location_from_dict(d1)
        self.assertEqual(l1, l2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        l3 = location.location_from_dict(d2)
        self.assertEqual(l1, l3)
    
    def test_aspectlocation_equality(self):
        l1 = location.AspectLocation(50., -3., 10., 270., 35.)
        d1 = l1.to_dict()
        l2 = location.location_from_dict(d1)
        self.assertEqual(l1, l2)
        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)
        l3 = location.location_from_dict(d2)
        self.assertEqual(l1, l3)

class TestLocationFromCharacteristics(unittest.TestCase):
    def test_location_fromcharacteristics(self):
        l1 = location.Location(50.0, -3.0)
        l2 = location.Location.from_characteristics(50.0, -3.0, crs = 'EPSG:4326')
        self.assertIsInstance(l2, location.Location)
        self.assertEqual(l1, l2)
    
    def test_raisedlocation_fromcharacteristics(self):
        l1 = location.RaisedLocation(50.0, -3.0, 55)
        l2 = location.RaisedLocation.from_characteristics(50.0, -3.0, height_agl = 55)
        self.assertIsInstance(l2, location.RaisedLocation)
        self.assertEqual(l1, l2)
    
    def test_aspectlocation_fromcharacteristics(self):
        l1 = location.AspectLocation(50.0, -3.0, 55, 75, 30)
        l2 = location.AspectLocation.from_characteristics(50.0, -3.0, height_agl = 55, azimuth = 75, pitch = 30)
        self.assertIsInstance(l2, location.AspectLocation)
        self.assertEqual(l1, l2)
        with self.assertRaises(TypeError):
            # Missing height
            l2 = location.AspectLocation.from_characteristics(50.0, -3.0, azimuth = 75, pitch = 30)
        