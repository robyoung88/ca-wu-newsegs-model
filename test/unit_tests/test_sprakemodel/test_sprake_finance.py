"""
Unit tests for newsegsfinance/sprakefinance
"""
import unittest
import json

from test.unit_tests.common import setup_test_env
setup_test_env()

from newsegsmodelframework.newsegsfinance import sprakefinance

class TestSprakeFinanceConfigEqualities(unittest.TestCase):

    def test_basic_construction(self):
        fnc1 = sprakefinance.SprakeFinance.from_none()
        self.assertEqual(fnc1.wind_capex_per_kw, 1500.0)
        self.assertEqual(fnc1.benefit_discount_rate, 0.0)

        fnc2 = sprakefinance.SprakeFinance(
            {
                'resident_var_per_unit': 0.2,
                'grid_export_var_per_unit': 0.07
            },
            cost_discount_rate = 0.035
        )

        self.assertEqual(fnc2.wind_capex_per_kw, 1500.0)
        self.assertEqual(fnc2.resident_var_per_unit, 0.2)
        self.assertEqual(fnc2.benefit_discount_rate, 0.0)
        self.assertEqual(fnc2.cost_discount_rate, 0.035)
    
    def test_copy_construction(self):
        fnc1 = sprakefinance.SprakeFinance(
            {
                'resident_var_per_unit': 0.2,
                'grid_export_var_per_unit': 0.07
            },
            cost_discount_rate = 0.035
        )

        fnc2 = sprakefinance.SprakeFinance(fnc1)
        self.assertEqual(fnc2.wind_capex_per_kw, 1500.0)
        self.assertEqual(fnc2.resident_var_per_unit, 0.2)
        self.assertEqual(fnc2.benefit_discount_rate, 0.0)
        self.assertEqual(fnc2.cost_discount_rate, 0.035)
        
        fnc2.benefit_discount_rate = 0.03
        self.assertEqual(fnc2.benefit_discount_rate, 0.03)
        self.assertEqual(fnc1.benefit_discount_rate, 0.0)
    
    def test_serialisation(self):
        fnc1 = sprakefinance.SprakeFinance(
            {
                'resident_var_per_unit': 0.2,
                'grid_export_var_per_unit': 0.07
            },
            cost_discount_rate = 0.035
        )

        d1 = fnc1.to_dict()

        fnc2 = sprakefinance.SprakeFinance.from_dict(d1)
        self.assertEqual(fnc2.wind_capex_per_kw, 1500.0)
        self.assertEqual(fnc2.resident_var_per_unit, 0.2)
        self.assertEqual(fnc2.benefit_discount_rate, 0.0)
        self.assertEqual(fnc2.cost_discount_rate, 0.035)

    def test_json_serialisation(self):
        fnc1 = sprakefinance.SprakeFinance(
            {
                'resident_var_per_unit': 0.2,
                'grid_export_var_per_unit': 0.07
            },
            cost_discount_rate = 0.035
        )

        sd1 = fnc1.json_dumps()
        d2 = json.loads(sd1)

        fnc2 = sprakefinance.SprakeFinance.from_none()
        fnc2.update(d2)
        self.assertEqual(fnc2.wind_capex_per_kw, 1500.0)
        self.assertEqual(fnc2.resident_var_per_unit, 0.2)
        self.assertEqual(fnc2.benefit_discount_rate, 0.0)
        self.assertEqual(fnc2.cost_discount_rate, 0.035)
