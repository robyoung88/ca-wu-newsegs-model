"""
Unit tests for newsegscs/sprakecs
"""
import unittest
import json

from unit_tests.common import setup_test_env
setup_test_env()

from util import jsonfuncs
from newsegscs import sprakecs
from newsegscs import constructors as csconstructors

class TestSprakeCSConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        cs1 = sprakecs.SprakeCS.from_none()
        self.assertDictEqual(
            cs1.appliance_params,
            {
                'efficiency_reduction': 0.1,
                'n_households': cs1.n_units
            }
        )

        cs1 = sprakecs.SprakeCS(500)
        self.assertDictEqual(
            cs1.appliance_params,
            {
                'efficiency_reduction': 0.1,
                'n_households': 500
            }
        )
        self.assertDictEqual(
            cs1.ev_params,
            {
                'annual_residential_consumption_per_ev': 1760.0*0.747,
                'n_evs': cs1.ev_per_unit * 500
            }
        )

    def test_copy_construction(self):
        cs1 = sprakecs.SprakeCS(
            500,
            storage_params = {
                'storage_capacity': 5000.0,
                'storage_rte': 0.88
            },
            dhw_params = {
                'ref_daily_consumption': 4.5,
                'seasonal_variance': 0.15,
                'n_households': 50
            },
            name = 'Test'
        )

        cs2 = sprakecs.SprakeCS(cs1)

        self.assertEqual(cs1.n_units, cs2.n_units)
        self.assertDictEqual(cs1.storage_params, cs2.storage_params)
        self.assertEqual(cs1.dhw_params['n_households'], cs2.dhw_params['n_households'])
        self.assertEqual(cs2.n_units, cs2.dhw_params['n_households'])
        self.assertEqual(cs2.name, cs2.name)

    def test_serialisation(self):
        cs1 = sprakecs.SprakeCS(
            500,
            storage_params = {
                'storage_capacity': 5000.0,
                'storage_rte': 0.88
            },
            dhw_params = {
                'ref_daily_consumption': 4.5,
                'seasonal_variance': 0.15,
                'n_households': 50
            },
            name = 'Test'
        )

        d1 = cs1.to_dict()

        cs2 = csconstructors.cs_module_from_dict(d1)

        self.assertEqual(cs1.n_units, cs2.n_units)
        self.assertDictEqual(cs1.storage_params, cs2.storage_params)
        self.assertEqual(cs1.dhw_params['n_households'], cs2.dhw_params['n_households'])
        self.assertEqual(cs2.n_units, cs2.dhw_params['n_households'])
        self.assertEqual(cs2.name, cs2.name)
    
    def test_json_serialisation(self):
        cs1 = sprakecs.SprakeCS(
            500,
            storage_params = {
                'storage_capacity': 5000.0,
                'storage_rte': 0.88
            },
            dhw_params = {
                'ref_daily_consumption': 4.5,
                'seasonal_variance': 0.15,
                'n_households': 50
            },
            name = 'Test'
        )

        d1 = cs1.to_dict()

        sd1 = json.dumps(d1, cls=jsonfuncs.NumpyEncoder)
        d2 = json.loads(sd1)

        cs2 = sprakecs.SprakeCS.from_none()
        cs2.update(d2)

        self.assertEqual(cs1.n_units, cs2.n_units)
        self.assertDictEqual(cs1.storage_params, cs2.storage_params)
        self.assertEqual(cs1.dhw_params['n_households'], cs2.dhw_params['n_households'])
        self.assertEqual(cs2.n_units, cs2.dhw_params['n_households'])
        self.assertEqual(cs2.name, cs2.name)
