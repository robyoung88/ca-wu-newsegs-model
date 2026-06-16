"""
Unit tests for newsegsgrid/sprakegrid
"""
import unittest
import json

from unit_tests.common import setup_test_env
setup_test_env()

from newsegsgrid import sprakegrid
from newsegsgrid import constructors as gridconstructors

class TestSprakeGridConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        gr1 = sprakegrid.SprakeGrid.from_none()
        self.assertEqual(gr1.import_rate, 0.2)
        self.assertEqual(gr1.export_rate, 0.07)

        gr2 = sprakegrid.SprakeGrid(0.35, 0.1)
        self.assertEqual(gr2.import_rate, 0.35)
        self.assertEqual(gr2.export_rate, 0.1)
    
    def test_copy_construction(self):
        gr1 = sprakegrid.SprakeGrid(0.35, 0.1, name = 'Test')
        gr2 = sprakegrid.SprakeGrid(gr1)
        
        self.assertEqual(gr1.import_rate, gr2.import_rate)
        self.assertEqual(gr1.export_rate, gr2.export_rate)
        self.assertEqual(gr1.name, gr2.name)

        gr2.export_rate = 0.15
        self.assertNotEqual(gr1.export_rate, gr2.export_rate)
    
    def test_serialisation(self):
        gr1 = sprakegrid.SprakeGrid(0.35, 0.1, name = 'Test')
        d1 = gr1.to_dict()

        gr2 = gridconstructors.grid_module_from_dict(d1)
        self.assertEqual(gr1.import_rate, gr2.import_rate)
        self.assertEqual(gr1.export_rate, gr2.export_rate)
        self.assertEqual(gr1.name, gr2.name)
    
    def test_json_serialisation(self):
        gr1 = sprakegrid.SprakeGrid(0.35, 0.1, name = 'Test')
        d1 = gr1.to_dict()

        sd1 = json.dumps(d1)
        d2 = json.loads(sd1)

        gr2 = sprakegrid.SprakeGrid.from_none()
        gr2.sync_with_dict(d2)
        self.assertEqual(gr1.import_rate, gr2.import_rate)
        self.assertEqual(gr1.export_rate, gr2.export_rate)
        self.assertEqual(gr1.name, gr2.name)
