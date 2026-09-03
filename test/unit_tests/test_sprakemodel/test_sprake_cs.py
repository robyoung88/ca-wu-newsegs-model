"""
Unit tests for newsegscs/sprakecs
"""
from typing import cast
import unittest
import json

from test.unit_tests.common import setup_test_env
setup_test_env()

from newsegsmodelframework.util import jsonfuncs
from newsegsmodelframework.newsegscs import sprakecs
from newsegsmodelframework.newsegscs import constructors as csconstructors

class TestSprakeCSConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        cs1 = sprakecs.SprakeCS.from_none()
        self.assertDictEqual(
            cs1.get_appliance_params(),
            {
                'efficiency_reduction': 0.1,
                'n_households': cs1.n_units
            }
        )

        cs1 = sprakecs.SprakeCS(500)
        self.assertDictEqual(
            cs1.get_appliance_params(),
            {
                'efficiency_reduction': 0.1,
                'n_households': 500
            }
        )
        self.assertDictEqual(
            cs1.get_ev_params(),
            {
                'annual_residential_consumption_per_ev': 1760.0*0.747,
                'n_evs': cs1.ev_per_unit * 500
            }
        )

    def test_copy_construction(self):
        cs1 = sprakecs.SprakeCS(
            500,
            **{
                'storage_capacity': 5000.0,
                'storage_rte': 0.88
            },
            **{
                'ref_daily_consumption': 4.5,
                'seasonal_variance': 0.15,
            },
            name = 'Test'
        )

        cs2 = sprakecs.SprakeCS(cs1)

        self.assertEqual(cs1.n_units, cs2.n_units)
        self.assertDictEqual(cs1.get_storage_params(), cs2.get_storage_params())
        self.assertEqual(cs1.get_dhw_params()['n_households'], cs2.get_dhw_params()['n_households'])
        self.assertEqual(cs2.n_units, cs2.get_dhw_params()['n_households'])
        self.assertEqual(cs2.name, cs2.name)

    def test_serialisation(self):
        cs1 = sprakecs.SprakeCS(
            500,
            **{
                'storage_capacity': 5000.0,
                'storage_rte': 0.88
            },
            **{
                'ref_daily_consumption': 4.5,
                'seasonal_variance': 0.15,
            },
            name = 'Test'
        )

        d1 = cs1.to_dict()

        cs2 = csconstructors.cs_module_from_dict(d1)
        cs2 = cast(sprakecs.SprakeCS, cs2)

        self.assertEqual(cs1.n_units, cs2.n_units)
        self.assertDictEqual(cs1.get_storage_params(), cs2.get_storage_params())
        self.assertEqual(cs1.get_dhw_params()['n_households'], cs2.get_dhw_params()['n_households'])
        self.assertEqual(cs2.n_units, cs2.get_dhw_params()['n_households'])
        self.assertEqual(cs2.name, cs2.name)
    
    def test_json_serialisation(self):
        cs1 = sprakecs.SprakeCS(
            500,
            **{
                'storage_capacity': 5000.0,
                'storage_rte': 0.88
            },
            **{
                'ref_daily_consumption': 4.5,
                'seasonal_variance': 0.15,
            },
            name = 'Test'
        )

        sd1 = cs1.json_dumps()
        d2 = json.loads(sd1)

        cs2 = sprakecs.SprakeCS.from_none()
        cs2.update(d2)

        self.assertEqual(cs1.n_units, cs2.n_units)
        self.assertDictEqual(cs1.get_storage_params(), cs2.get_storage_params())
        self.assertEqual(cs1.get_dhw_params()['n_households'], cs2.get_dhw_params()['n_households'])
        self.assertEqual(cs2.n_units, cs2.get_dhw_params()['n_households'])
        self.assertEqual(cs2.name, cs2.name)
