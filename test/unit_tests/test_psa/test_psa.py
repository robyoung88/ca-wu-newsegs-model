"""
Unit tests for newsegssensitivity/psa
"""
import json
import unittest

from test.unit_tests.common import setup_test_env
setup_test_env()

from newsegsmodel import SprakeModel
from newsegsfinance import SprakeFinance
from newsegsvariable import variable
from newsegsmetamodel import NewsegsMetaModel
from newsegssensitivity import psa

class TestPSA(unittest.TestCase):
    """
    Test behaviour of psa
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
    
    def test_short_psa(self):
        mm = self.make_sprake_metamodel()
        mdl = mm.model
        fnc = mm.finance
        for v in mm.variables.values():
            v.update_model(mdl)
            v.update_model(fnc)
            if v.model_parameter == 'hlp' or v.model_parameter == 'efficiency_reduction':
                v.psa_selectable = True
                v.psa_selected = True
            else:
                v.psa_selected = False

        mdl.run()
        fnc.run()
        det_costs = fnc.get_total_present_costs_undiscounted()
        det_value = fnc.get_net_present_value_undiscounted()
        
        psa_results = psa.run_psa(
            mm,
            [   
                'total_present_costs_undiscounted',
                'net_present_value_undiscounted'
            ],
            10
        )

        self.assertEqual(
            len(psa_results),
            11
        )

        psa_results = psa_results.set_index('draw')

        self.assertEqual(
            psa_results.loc[0, 'total_present_costs_undiscounted'],
            det_costs
        )
        
        self.assertEqual(
            psa_results.loc[0, 'net_present_value_undiscounted'],
            det_value
        )

        self.assertEqual(
            len(set(psa_results.loc[:, 'net_present_value_undiscounted'].to_numpy())),
            11
        )

    def test_sample_return_psa(self):
        mm = self.make_sprake_metamodel()
        mdl = mm.model
        fnc = mm.finance
        for v in mm.variables.values():
            v.update_model(mdl)
            v.update_model(fnc)
            if v.model_parameter == 'hlp' or v.model_parameter == 'efficiency_reduction':
                v.psa_selectable = True
                v.psa_selected = True
            else:
                v.psa_selected = False
 
        psa_results = psa.run_psa(
            mm,
            [   
                'total_present_costs_undiscounted',
                'net_present_value_undiscounted'
            ],
            10,
            return_draws = True
        )

        self.assertEqual(
            len(psa_results),
            11
        )

        self.assertEqual(
            len(psa_results.columns),
            6 # 2 stats, 2 variables, 'draw' and 'deterministic'
        )

        psa_results = psa_results.set_index('draw')

        self.assertEqual(
            len(set(psa_results.loc[:, 'HLP'].to_numpy())),
            11
        )

    def test_longer_psa(self):
        mm = self.make_sprake_metamodel()
        
        psa_results = psa.run_psa(
            mm,
            [   
                'total_present_costs_undiscounted',
                'net_present_value_undiscounted'
            ],
            200
        )

        self.assertEqual(
            len(psa_results),
            201
        )
        psa_results = psa_results.set_index('draw')
        npv_samples = psa_results.loc[slice(1, 201), 'net_present_value_undiscounted'].to_numpy()
        mean_npv = npv_samples.mean()
        std_npv = npv_samples.std()

        self.assertNotEqual(
            std_npv,
            0
        )

        det_npv = psa_results.loc[0, 'net_present_value_undiscounted']

        self.assertLess(
            det_npv - 2 * std_npv,
            mean_npv
        )

        self.assertGreater(
            det_npv + 2 * std_npv,
            mean_npv
        )

