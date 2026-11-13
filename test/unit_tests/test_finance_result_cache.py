"""
Unit tests of the caching of results of runs: the finance results, cached on the finance model for the
current run (`NewsegsFinance.cached_result`), and the dataframes of module results, cached on the result.

Results were cached by module-level `lru_cache`s keyed on the finance model or the result, which kept
the results of every run, so memory grew with each run of the model.
"""
import copy
import pickle
import unittest
from unittest import mock

import newsegsmodelframework.register_plugins  # noqa: F401
from newsegsmodelframework.newsegsfinance import sprakefinance
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

class TestCachedResult(unittest.TestCase):
    """`cached_result` on a finance model without a model"""

    def setUp(self):
        self.fnc = sprakefinance.SprakeFinance.from_none()

    def test_computed_once(self):
        compute = mock.Mock(return_value = 1)
        for _ in range(3):
            self.assertEqual(self.fnc.cached_result('a', compute), 1)
        compute.assert_called_once()

    def test_emptied_by_run(self):
        compute = mock.Mock(side_effect = [1, 2])
        self.fnc.cached_result('a', compute)
        self.fnc.run()
        self.assertEqual(self.fnc.cached_result('a', compute), 2)

    def test_not_saved_or_copied(self):
        self.fnc.cached_result('a', lambda: 'cached')
        self.assertNotIn('_result_cache', self.fnc.to_dict())
        for other in (copy.deepcopy(self.fnc), pickle.loads(pickle.dumps(self.fnc))):
            compute = mock.Mock(return_value = 'recomputed')
            self.assertEqual(other.cached_result('a', compute), 'recomputed')

class TestFinanceResults(unittest.TestCase):
    """The finance results of the default Sprake configuration, over repeated runs"""

    @classmethod
    def setUpClass(cls):
        cls.mm = PROJECT_FACTORIES['sprake']().get_focussed_metamodel()

    def run_both(self):
        self.mm.model.run()
        self.mm.finance.run()
        return self.mm.finance.get_net_present_value_discounted()

    def test_results_of_the_current_run(self):
        npv = self.run_both()
        cache_size = len(self.mm.finance.__dict__['_result_cache'][1])
        self.assertGreater(cache_size, 1)

        # A change to the configuration changes the result
        self.mm.finance.resident_var_per_unit = self.mm.finance.resident_var_per_unit * 2
        self.assertNotEqual(self.run_both(), npv)

        # A change to the model changes the result
        npv = self.run_both()
        self.mm.model.generation.wind_capacity = self.mm.model.generation.wind_capacity + 50.
        self.assertNotEqual(self.run_both(), npv)

    def test_cache_holds_one_run(self):
        self.run_both()
        first = len(self.mm.finance.__dict__['_result_cache'][1])
        for _ in range(3):
            self.run_both()
        # The same results, of the last run only
        self.assertEqual(len(self.mm.finance.__dict__['_result_cache'][1]), first)

    def test_new_model_run_without_finance_run(self):
        # The results of an earlier run of the model are not returned, even if the finance model
        # is not run: the model's run changes the hash of the finance model
        npv = self.run_both()
        self.mm.model.generation.pv_capacity = self.mm.model.generation.pv_capacity + 50.
        self.mm.model.run()
        self.assertNotEqual(self.mm.finance.get_net_present_value_discounted(), npv)

    def test_run_empties_the_cache(self):
        self.run_both()
        self.assertTrue(self.mm.finance.__dict__['_result_cache'][1])
        self.mm.finance.run()
        self.assertFalse(self.mm.finance.__dict__['_result_cache'][1])

class TestModuleResultFrames(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        mm = PROJECT_FACTORIES['sprake']().get_focussed_metamodel()
        mm.model.run()
        cls.result = mm.model.get_consumption_storage_result()

    def test_cached_on_the_result(self):
        self.assertIs(self.result.meters_to_pandas(), self.result.meters_to_pandas())
        self.assertIs(self.result.dsm_to_pandas(), self.result.dsm_to_pandas())

    def test_not_pickled(self):
        self.result.meters_to_pandas()
        restored = pickle.loads(pickle.dumps(self.result))
        self.assertNotIn('_frame_cache', restored.__dict__)
        self.assertTrue(restored.meters_to_pandas().equals(self.result.meters_to_pandas()))
