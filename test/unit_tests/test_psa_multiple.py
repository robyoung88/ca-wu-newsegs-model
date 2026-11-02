"""
Unit tests for the whole-project (multiple metamodel) PSA of newsegssensitivity/psa
"""
from typing import get_args
import unittest

import numpy as np
import pandas as pd

from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import psa

from test.unit_tests.test_dsa_multiple import make_sprake_metamodel

STORAGE_CAPACITY = 'stor_input.storage_capacity.0'
WIND_CAPEX = 'gen_costs.wind_capex_per_kw.0'
PV_CAPEX = 'gen_costs.pv_capex_per_kw.0'
HLP = 'bc_input.hlp.0'
GFA = 'bc_input.gfa.0'

STATISTICS = list(get_args(psa.PSA_FLOAT_STATISTIC))


def select_only(mm: NewsegsMetaModel, varids):
    for varid, v in mm.variables.items():
        v.psa_selected = varid in varids

def mm_rows(results: pd.DataFrame, mm: NewsegsMetaModel) -> pd.DataFrame:
    return results.loc[results['metamodel'] == mm.id, :].set_index('draw')


class TestSynchronisePSASelection(unittest.TestCase):
    """Synchronisation of the PSA selection across metamodels"""

    def test_union_of_selection(self):
        mm_a = make_sprake_metamodel()
        mm_b = make_sprake_metamodel()
        select_only(mm_a, [WIND_CAPEX])
        select_only(mm_b, [HLP])

        varids = psa.synchronise_psa_selection([mm_a, mm_b])

        # Order of first appearance in the metamodels, not order of selection
        order = list(mm_a.variables.keys())
        self.assertEqual(varids, sorted([WIND_CAPEX, HLP], key = order.index))
        for mm in (mm_a, mm_b):
            self.assertTrue(mm.variables[WIND_CAPEX].psa_selected)
            self.assertTrue(mm.variables[HLP].psa_selected)
            self.assertFalse(mm.variables[PV_CAPEX].psa_selected)

    def test_unselectable_variables_unchanged(self):
        mm_a = make_sprake_metamodel()
        mm_b = make_sprake_metamodel()
        select_only(mm_a, [WIND_CAPEX])
        select_only(mm_b, [])
        mm_b.variables[WIND_CAPEX].psa_selectable = False

        varids = psa.synchronise_psa_selection([mm_a, mm_b])

        self.assertEqual(varids, [WIND_CAPEX])
        self.assertFalse(mm_b.variables[WIND_CAPEX].psa_selected)


class TestRunPSAMultiple(unittest.TestCase):
    """Behaviour of run_psa_multiple: two configurations with independent, identically distributed variables"""

    SAMPLES = 12

    @classmethod
    def setUpClass(cls):
        cls.mm_a = make_sprake_metamodel()
        cls.mm_b = make_sprake_metamodel(storage_capacity = 2000.0)
        select_only(cls.mm_a, [WIND_CAPEX, HLP])
        select_only(cls.mm_b, [WIND_CAPEX])
        cls.results = psa.run_psa_multiple([cls.mm_a, cls.mm_b], samples = cls.SAMPLES, seed = 42)
        cls.wind_capex = cls.mm_a.variables[WIND_CAPEX].name
        cls.hlp = cls.mm_a.variables[HLP].name

    def test_shape_and_order(self):
        res = self.results
        self.assertEqual(len(res), 2 * (self.SAMPLES + 1))
        self.assertEqual(list(res.columns[:3 + len(STATISTICS)]), psa.PSA_MULTIPLE_INDEX_COLUMNS + STATISTICS)
        # In the order of the variables of the metamodels
        self.assertEqual(psa.psa_variable_columns(res), [self.hlp, self.wind_capex])

        # The deterministic runs first, then every metamodel for each draw in turn
        self.assertEqual(list(res['draw'].iloc[:2]), [0, 0])
        self.assertTrue(res['deterministic'].iloc[:2].all())
        self.assertFalse(res['deterministic'].iloc[2:].any())
        self.assertEqual(list(res['metamodel'].iloc[2:6]), [self.mm_a.id, self.mm_b.id] * 2)
        self.assertEqual(list(res['draw'].iloc[2:6]), [1, 1, 2, 2])

        # The selection has been synchronised onto the metamodels
        self.assertTrue(self.mm_b.variables[HLP].psa_selected)

    def test_common_random_numbers(self):
        # Independent instances with the same distribution take the same value in every draw
        a = mm_rows(self.results, self.mm_a)
        b = mm_rows(self.results, self.mm_b)
        for column in (self.wind_capex, self.hlp):
            np.testing.assert_allclose(a[column].to_numpy(dtype = float), b[column].to_numpy(dtype = float))
            # ... and the draws vary
            self.assertEqual(len(set(a.loc[1:, column])), self.SAMPLES)

        # Different variables are drawn independently: not perfectly correlated
        sampled = a.loc[1:, :]
        self.assertLess(abs(np.corrcoef(sampled[self.wind_capex], sampled[self.hlp])[0, 1]), 0.9)

    def test_outputs_vary_with_draws(self):
        for mm in (self.mm_a, self.mm_b):
            sampled = mm_rows(self.results, mm).loc[1:, :]
            self.assertEqual(len(set(sampled['total_present_costs_discounted'])), self.SAMPLES)

    def test_deterministic_rows_match_single_psa(self):
        for mm in (self.mm_a, self.mm_b):
            single = psa.run_psa(mm, STATISTICS, samples = 0)
            det = mm_rows(self.results, mm).loc[0, STATISTICS]
            np.testing.assert_allclose(det.to_numpy(dtype = float), single.loc[0, STATISTICS].to_numpy(dtype = float))

    def test_variables_restored(self):
        for mm in (self.mm_a, self.mm_b):
            for v in mm.variables.values():
                self.assertFalse(v.psa_active)
            # The models are left at their deterministic values
            after = psa.make_psa_result(mm, mm.model, mm.finance, STATISTICS)
            det = mm_rows(self.results, mm).loc[0, STATISTICS]
            np.testing.assert_allclose([after[x] for x in STATISTICS], det.to_numpy(dtype = float))

    def test_reproducible(self):
        again = psa.run_psa_multiple([self.mm_a, self.mm_b], samples = 2, seed = 42)
        pd.testing.assert_frame_equal(
            again.reset_index(drop = True),
            self.results.loc[self.results['draw'] <= 2, :].reset_index(drop = True),
        )
        other = psa.run_psa_multiple([self.mm_a, self.mm_b], samples = 1, seed = 7, include_deterministic = False)
        self.assertNotEqual(other[self.wind_capex].iloc[0], mm_rows(self.results, self.mm_a).loc[1, self.wind_capex])

    def test_for_metamodel(self):
        single = psa.psa_multiple_for_metamodel(self.results, self.mm_b.id)
        self.assertEqual(len(single), self.SAMPLES + 1)
        self.assertEqual(list(single.columns), [self.hlp, self.wind_capex] + STATISTICS + ['deterministic', 'draw'])
        # In the form of the results of run_psa, which the PSA summaries take
        table, _ = psa.basic_psa_stats(single)
        self.assertEqual(list(table.index), STATISTICS)
        with self.assertRaises(KeyError):
            psa.psa_multiple_for_metamodel(self.results, 'nonexistent')

    def test_metamodel_without_variable(self):
        mm_a = make_sprake_metamodel()
        mm_b = make_sprake_metamodel()
        select_only(mm_a, [WIND_CAPEX, HLP])
        select_only(mm_b, [WIND_CAPEX])
        mm_b.variables[HLP].psa_selectable = False
        res = psa.run_psa_multiple([mm_a, mm_b], samples = 2, seed = 1)

        b = mm_rows(res, mm_b)
        self.assertTrue(b[self.hlp].isna().all())
        self.assertNotIn(self.hlp, psa.psa_multiple_for_metamodel(res, mm_b.id).columns)
        # mm_b still follows the shared draw of the wind capex
        np.testing.assert_allclose(
            b[self.wind_capex].to_numpy(dtype = float), mm_rows(res, mm_a)[self.wind_capex].to_numpy(dtype = float)
        )

    def test_progress_and_cancel(self):
        calls = []
        psa.run_psa_multiple(
            [self.mm_a, self.mm_b], [STATISTICS[0]], samples = 1, seed = 1,
            progress = lambda i, n: calls.append((i, n))
        )
        self.assertEqual(calls[0], (0, 4))
        self.assertEqual(calls[-1], (4, 4))

        n_checks = 0
        def cancel_after_first_sample():
            nonlocal n_checks
            n_checks += 1
            return n_checks > 2
        with self.assertRaises(InterruptedError):
            psa.run_psa_multiple(
                [self.mm_a, self.mm_b], [STATISTICS[0]], samples = 3, seed = 1,
                cancel_status = cancel_after_first_sample
            )
        for mm in (self.mm_a, self.mm_b):
            for v in mm.variables.values():
                self.assertFalse(v.psa_active)

    def test_precomputed_deterministic(self):
        for mm in (self.mm_a, self.mm_b):
            mm.model.run()
            mm.finance.run()
        res = psa.run_psa_multiple([self.mm_a, self.mm_b], samples = 1, seed = 3, precomputed_deterministic = True)
        res_full = psa.run_psa_multiple([self.mm_a, self.mm_b], samples = 1, seed = 3)
        pd.testing.assert_frame_equal(res, res_full)


class TestPSACorrelation(unittest.TestCase):
    """The configurations share the draws of the cost variables, so their results are correlated"""

    SAMPLES = 15

    @classmethod
    def setUpClass(cls):
        cls.mm_a = make_sprake_metamodel()
        cls.mm_b = make_sprake_metamodel()
        cls.mm_c = make_sprake_metamodel()
        # mm_b: an independent wind capex twice as dear, with the same coefficient of variation (the same gamma shape)
        cls.mm_a.variables[WIND_CAPEX].set_parameters(1500.0, 300.0)
        cls.mm_b.variables[WIND_CAPEX].set_parameters(3000.0, 600.0)
        # mm_c: shares the instance of mm_a
        cls.mm_c.variables[WIND_CAPEX] = cls.mm_a.variables[WIND_CAPEX]
        for mm in (cls.mm_a, cls.mm_b, cls.mm_c):
            select_only(mm, [WIND_CAPEX])
            for v in mm.variables.values():
                v.update_model(mm.model)
                v.update_model(mm.finance)
        cls.results = psa.run_psa_multiple([cls.mm_a, cls.mm_b, cls.mm_c], samples = cls.SAMPLES, seed = 11)
        cls.wind_capex = cls.mm_a.variables[WIND_CAPEX].name

    def test_shared_instance_draws_identical(self):
        a = mm_rows(self.results, self.mm_a)
        c = mm_rows(self.results, self.mm_c)
        np.testing.assert_array_equal(a[self.wind_capex].to_numpy(), c[self.wind_capex].to_numpy())
        # The same configuration with the same draw has the same results
        np.testing.assert_allclose(
            a[STATISTICS].to_numpy(dtype = float), c[STATISTICS].to_numpy(dtype = float)
        )

    def test_independent_instance_draws_correspond(self):
        # Common random numbers: the draws of a distribution scaled by 2 are exactly twice the draws
        a = mm_rows(self.results, self.mm_a).loc[1:, self.wind_capex].to_numpy(dtype = float)
        b = mm_rows(self.results, self.mm_b).loc[1:, self.wind_capex].to_numpy(dtype = float)
        np.testing.assert_allclose(b, 2 * a)

    def test_costs_correlated(self):
        a = mm_rows(self.results, self.mm_a).loc[1:, :]
        b = mm_rows(self.results, self.mm_b).loc[1:, :]
        for stat in ('total_present_costs_discounted', 'all_capex_costs_undiscounted'):
            self.assertGreater(np.corrcoef(a[stat], b[stat])[0, 1], 0.99)
        # Only the capex varies: the opex is the same in every draw
        self.assertEqual(len(set(a['all_recurrent_costs_undiscounted'].round(6))), 1)

    def test_increments_less_variable_than_independent_draws(self):
        # The covariance of the shared draws reduces the variance of the increment
        pw = psa.psa_pairwise(self.results, self.mm_b.id, self.mm_a.id)
        sampled = pw.loc[~pw['deterministic'], :]
        a = mm_rows(self.results, self.mm_a).loc[1:, 'total_present_costs_discounted']
        b = mm_rows(self.results, self.mm_b).loc[1:, 'total_present_costs_discounted']
        self.assertLess(sampled['incremental_total_costs_discounted'].var(), a.var() + b.var())
        a_rate = mm_rows(self.results, self.mm_a).loc[1:, self.wind_capex].to_numpy(dtype = float)
        # The extra wind capex of mm_b is the wind capacity times the extra capex rate. The pairwise draws are
        # those of the comparator, mm_b, which are twice those of mm_a
        capacity = self.mm_a.variables['gen_input.wind_capacity.0'].deterministic_value
        np.testing.assert_allclose(
            sampled['incremental_all_capex_costs_undiscounted'].to_numpy(dtype = float),
            capacity * (sampled[self.wind_capex].to_numpy(dtype = float) - a_rate),
            rtol = 1e-9,
        )


class TestPSAPairwise(unittest.TestCase):
    """Pairwise comparisons of a whole-project PSA"""

    @classmethod
    def setUpClass(cls):
        cls.mm_a = make_sprake_metamodel()
        cls.mm_b = make_sprake_metamodel(storage_capacity = 2000.0)
        select_only(cls.mm_a, [WIND_CAPEX, PV_CAPEX])
        select_only(cls.mm_b, [])
        cls.results = psa.run_psa_multiple([cls.mm_a, cls.mm_b], samples = 4, seed = 5)

    def test_increments(self):
        pw = psa.psa_pairwise(self.results, self.mm_b.id, self.mm_a.id)
        variable_columns = psa.psa_variable_columns(self.results)
        self.assertEqual(
            list(pw.columns), ['draw', 'deterministic'] + list(get_args(psa.PSA_PAIRWISE_STATISTIC)) + variable_columns
        )
        self.assertEqual(len(pw), 5)

        comp = mm_rows(self.results, self.mm_b)
        ref = mm_rows(self.results, self.mm_a)
        pw = pw.set_index('draw')
        for disc in ('discounted', 'undiscounted'):
            d_costs = comp[f'total_present_costs_{disc}'] - ref[f'total_present_costs_{disc}']
            d_benefits = comp[f'total_present_benefits_{disc}'] - ref[f'total_present_benefits_{disc}']
            np.testing.assert_allclose(pw[f'incremental_total_costs_{disc}'], d_costs)
            np.testing.assert_allclose(pw[f'incremental_total_benefits_{disc}'], d_benefits)
            np.testing.assert_allclose(pw[f'incremental_net_monetary_value_{disc}'], d_benefits - d_costs)
            # Equivalent to the change in net present value
            np.testing.assert_allclose(
                pw[f'incremental_net_monetary_value_{disc}'],
                comp[f'net_present_value_{disc}'] - ref[f'net_present_value_{disc}'],
                rtol = 1e-9, atol = 1e-6
            )
            np.testing.assert_allclose(
                pw[f'incremental_all_capex_costs_{disc}'],
                comp[f'all_capex_costs_{disc}'] - ref[f'all_capex_costs_{disc}'],
            )
        # Less storage costs less capital
        self.assertTrue((pw['incremental_all_capex_costs_undiscounted'] < 0).all())

    def test_antisymmetric(self):
        ab = psa.psa_pairwise(self.results, self.mm_a.id, self.mm_b.id)
        ba = psa.psa_pairwise(self.results, self.mm_b.id, self.mm_a.id)
        np.testing.assert_allclose(
            ab['incremental_net_monetary_value_discounted'], -ba['incremental_net_monetary_value_discounted']
        )

    def test_self_comparison(self):
        pw = psa.psa_pairwise(self.results, self.mm_a.id, self.mm_a.id)
        self.assertTrue((pw['incremental_total_costs_discounted'] == 0).all())

    def test_missing(self):
        with self.assertRaises(KeyError):
            psa.psa_pairwise(self.results, 'nonexistent', self.mm_a.id)
        with self.assertRaises(KeyError):
            psa.psa_pairwise(self.results.drop(columns = ['total_present_costs_discounted']), self.mm_b.id, self.mm_a.id)


def synthetic_results(net_values: dict[str, list[float]]) -> pd.DataFrame:
    """Whole-project PSA results with no costs, whose benefits (and so net present values) are given by draw."""
    rows = []
    for mm_id, values in net_values.items():
        rows.append({
            'metamodel': mm_id, 'draw': 0, 'deterministic': True,
            'total_present_costs_discounted': 0., 'total_present_benefits_discounted': float(np.mean(values)),
        })
        for i, v in enumerate(values):
            rows.append({
                'metamodel': mm_id, 'draw': i + 1, 'deterministic': False,
                'total_present_costs_discounted': 0., 'total_present_benefits_discounted': v,
            })
    return pd.DataFrame(rows)


class TestPSACEAC(unittest.TestCase):
    """Cost-effectiveness acceptability curves and frontier"""

    def test_probabilities_and_frontier(self):
        # 'a' has the greater mean, but 'b' is better in 3 of the 4 draws
        res = synthetic_results({'a': [10., 1., 1., 1.], 'b': [0., 2., 2., 2.]})
        ceac = psa.psa_ceac(res, ['a', 'b'], [1.])

        self.assertAlmostEqual(ceac.loc[1., 'a'], 0.25)
        self.assertAlmostEqual(ceac.loc[1., 'b'], 0.75)
        # The frontier follows the expected net benefit, not the probability
        self.assertEqual(ceac.loc[1., 'frontier'], 'a')
        self.assertAlmostEqual(ceac.loc[1., 'frontier_probability'], 0.25)

    def test_switch_with_benefit_value(self):
        # 'a' costs more but brings more benefit: it is chosen when benefits are valued highly enough
        rows = []
        for mm_id, cost, benefit in (('a', 10., 15.), ('b', 2., 6.)):
            for i, noise in enumerate([-1., 0., 1.]):
                rows.append({
                    'metamodel': mm_id, 'draw': i + 1, 'deterministic': False,
                    'total_present_costs_discounted': cost,
                    'total_present_benefits_discounted': benefit + noise,
                })
        res = pd.DataFrame(rows)
        ceac = psa.psa_ceac(res, ['a', 'b'], [0.5, 3.])
        np.testing.assert_allclose(ceac[['a', 'b']].sum(axis = 1), 1.)
        self.assertEqual(ceac.loc[0.5, 'frontier'], 'b')
        self.assertEqual(ceac.loc[3., 'frontier'], 'a')
        self.assertEqual(ceac.loc[3., 'frontier_probability'], 1.)

    def test_net_benefit(self):
        res = synthetic_results({'a': [1., 2.]})
        nb = psa.psa_net_benefit(res, ['a'], 2.)
        self.assertEqual(list(nb.index), [1, 2])
        np.testing.assert_allclose(nb['a'], [2., 4.])
        with self.assertRaises(KeyError):
            psa.psa_net_benefit(res, ['missing'])
        with self.assertRaises(ValueError):
            psa.psa_ceac(res, [], [1.])


class TestPSAMarginal(unittest.TestCase):
    """Marginal (univariate) sensitivity of a statistic to a variable"""

    def test_linear_relation(self):
        rng = np.random.default_rng(0)
        x = rng.uniform(0, 10, 200)
        res = pd.DataFrame({
            'deterministic': [True] + [False] * 200,
            'draw': range(201),
            'Wind Capex': np.concatenate([[5.], x]),
            'total_present_costs_discounted': np.concatenate([[1e9], 3 * x + 2 + rng.normal(0, 0.1, 200)]),
        })
        m = psa.psa_marginal(res, 'Wind Capex', 'total_present_costs_discounted', bins = 5)

        # The deterministic run is left out
        self.assertEqual(len(m.points), 200)
        self.assertAlmostEqual(m.slope, 3, places = 1)
        self.assertAlmostEqual(m.intercept, 2, places = 0)
        self.assertGreater(m.spearman, 0.99)
        self.assertGreater(m.r_squared, 0.99)
        self.assertEqual(len(m.binned), 5)
        self.assertEqual(int(m.binned['count'].sum()), 200)
        self.assertTrue(m.binned['x'].is_monotonic_increasing)
        self.assertTrue((m.binned['y_lower'] <= m.binned['y']).all())

    def test_constant_variable(self):
        res = pd.DataFrame({'x': [1., 1., 1., 1.], 'y': [1., 2., 3., 4.]})
        m = psa.psa_marginal(res, 'x', 'y')
        self.assertTrue(np.isnan(m.slope))
        self.assertTrue(np.isnan(m.spearman))
        self.assertEqual(len(m.binned), 1)

    def test_missing(self):
        res = pd.DataFrame({'x': [1., 2.], 'y': [1., 2.]})
        with self.assertRaises(KeyError):
            psa.psa_marginal(res, 'z', 'y')
        with self.assertRaises(KeyError):
            psa.psa_marginal(res, 'x', 'z')


if __name__ == '__main__':
    unittest.main()
