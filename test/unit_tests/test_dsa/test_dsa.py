"""
Unit tests for newsegssensitivity/dsa
"""
import json
import unittest

from unit_tests.common import setup_test_env
setup_test_env()

from newsegsmodel import SprakeModel
from newsegsfinance import SprakeFinance
from newsegsvariable import variable
from newsegsmetamodel import NewsegsMetaModel
from newsegssensitivity import dsa

class TestDSA(unittest.TestCase):
    """
    Test behaviour of dsa
    """

    def load_sprake_variables(self):
        with open('data/sprake-variable-config.json') as f:
            var_conf_list = json.load(f)
        return [variable.variable_from_dict(x) for x in var_conf_list]
    
    def make_sprake_metamodel(self):
        mdl = SprakeModel.from_none()
        fnc = SprakeFinance.from_none()
        fnc.set_model(mdl)
        variables = self.load_sprake_variables()
        for v in variables:
            v.update_model(mdl)
            v.update_model(fnc)
        mm = NewsegsMetaModel(mdl, fnc, variables)
        return mm
    
    def test_short_dsa(self):
        mm = self.make_sprake_metamodel()
        for v in mm.variables.values():
            if v.model_parameter == 'storage_capacity' or v.model_parameter == 'storage_rte':
                v.dsa_selected = True
            else:
                v.dsa_selected = False

        dsa_results = dsa.run_dsa(
            mm, 
            [
                'total_present_costs_undiscounted',
                'net_present_value_discounted', 
                'net_present_value_undiscounted'
            ]
        )

        self.assertEqual(
            len(dsa_results),
            5
        )

        dsa_results = dsa_results.set_index(['variable', 'bound'])
        #det_npv = dsa_results.loc[('deterministic', 'central'), 'net_present_value_discounted']
        det_cost = float(dsa_results.loc[('deterministic', 'central'), 'total_present_costs_undiscounted']) # pyright: ignore[reportArgumentType]

        # NB -these tests are specific to a low impact storage set-up. If the storage makes a large impact, then
        # it could reduce imports enough to offset its cost.
        self.assertLess(
            float(dsa_results.loc[('Storage capacity','lower'),'total_present_costs_undiscounted']), # pyright: ignore[reportArgumentType]
            det_cost
        )
        self.assertGreater(
            float(dsa_results.loc[('Storage capacity','upper'),'total_present_costs_undiscounted']), # pyright: ignore[reportArgumentType]
            det_cost
        )

    def test_long_dsa(self):
        mm = self.make_sprake_metamodel()
        dsa_variable_count = 0
        for v in mm.variables.values():
            if v.dsa_possible and v.dsa_selectable:
                v.dsa_selected = True
                dsa_variable_count += 1

        dsa_results = dsa.run_dsa(
            mm
        )

        self.assertEqual(
            len(dsa_results),
            2 * dsa_variable_count + 1
        )


    