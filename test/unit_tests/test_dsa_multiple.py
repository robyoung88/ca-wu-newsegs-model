"""
Unit tests for the whole-project (multiple metamodel) DSA of newsegssensitivity/dsa
"""
import json
from typing import get_args
import unittest

from pathlib import Path

import numpy as np
import pandas as pd

from newsegsmodelframework.newsegsmodel import SprakeModel
from newsegsmodelframework.newsegsfinance.sprakefinance import SprakeFinance
from newsegsmodelframework.newsegsvariable import variable
from newsegsmodelframework.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import dsa

from test.unit_tests.common import get_data_dir

_CWD = Path().resolve()
_DATA_DIR = get_data_dir(_CWD)

STORAGE_CAPACITY = 'stor_input.storage_capacity.0'
RESIDENT_TARIFF = 'sales_costs.resident_var_per_unit.0'
BESS_CAPEX = 'stor_costs.bess_capex_per_kwh.0'

STATISTICS = list(get_args(dsa.DSA_FLOAT_STATISTIC))


def load_sprake_variables():
    with open(_DATA_DIR / 'sprake-validation-variable-config.json') as f:
        var_conf_list = json.load(f)
    return [variable.variable_from_dict(x) for x in var_conf_list]

def make_sprake_metamodel(variables = None, storage_capacity: float | None = None):
    """A Sprake metamodel; each call has its own (independent) variable instances unless given variables."""
    mdl = SprakeModel.from_none()
    fnc = SprakeFinance.from_none()
    fnc.set_model(mdl)
    if variables is None:
        variables = load_sprake_variables()
    mm = NewsegsMetaModel(mdl, fnc, variables)
    if storage_capacity is not None:
        mm.variables[STORAGE_CAPACITY].set_parameters(storage_capacity)
    for v in mm.variables.values():
        v.update_model(mdl)
        v.update_model(fnc)
    return mm

def select_only(mm: NewsegsMetaModel, varids):
    for varid, v in mm.variables.items():
        v.dsa_selected = varid in varids


class TestSynchroniseDSASelection(unittest.TestCase):
    """Synchronisation of the DSA selection across metamodels"""

    def test_union_of_selection(self):
        mm_a = make_sprake_metamodel()
        mm_b = make_sprake_metamodel()
        select_only(mm_a, [STORAGE_CAPACITY])
        select_only(mm_b, [RESIDENT_TARIFF])

        varids = dsa.synchronise_dsa_selection([mm_a, mm_b])

        # Order of first appearance in the metamodels, not order of selection
        order = list(mm_a.variables.keys())
        self.assertEqual(varids, sorted([STORAGE_CAPACITY, RESIDENT_TARIFF], key = order.index))
        for mm in (mm_a, mm_b):
            self.assertTrue(mm.variables[STORAGE_CAPACITY].dsa_selected)
            self.assertTrue(mm.variables[RESIDENT_TARIFF].dsa_selected)
            self.assertFalse(mm.variables[BESS_CAPEX].dsa_selected)

    def test_unselectable_variables_unchanged(self):
        mm_a = make_sprake_metamodel()
        mm_b = make_sprake_metamodel()
        select_only(mm_a, [])
        select_only(mm_b, [])
        # A variable which may not be selected in one metamodel is neither changed nor counted
        mm_a.variables[STORAGE_CAPACITY].dsa_selected = True
        mm_b.variables[STORAGE_CAPACITY].dsa_selectable = False

        varids = dsa.synchronise_dsa_selection([mm_a, mm_b])

        self.assertEqual(varids, [STORAGE_CAPACITY])
        self.assertFalse(mm_b.variables[STORAGE_CAPACITY].dsa_selected)

    def test_shared_instance_consistent(self):
        mm_a = make_sprake_metamodel()
        mm_b = make_sprake_metamodel()
        mm_b.variables[STORAGE_CAPACITY] = mm_a.variables[STORAGE_CAPACITY]
        # Deselecting through mm_b first, then selecting through mm_a, changes the one shared instance
        select_only(mm_b, [])
        select_only(mm_a, [STORAGE_CAPACITY])

        varids = dsa.synchronise_dsa_selection([mm_a, mm_b])

        self.assertEqual(varids, [STORAGE_CAPACITY])
        self.assertIs(mm_a.variables[STORAGE_CAPACITY], mm_b.variables[STORAGE_CAPACITY])
        self.assertTrue(mm_b.variables[STORAGE_CAPACITY].dsa_selected)


class TestRunDSAMultiple(unittest.TestCase):
    """Behaviour of run_dsa_multiple"""

    def setUp(self):
        self.mm_a = make_sprake_metamodel()
        self.mm_b = make_sprake_metamodel(storage_capacity = 2000.0)
        select_only(self.mm_a, [STORAGE_CAPACITY, RESIDENT_TARIFF])
        select_only(self.mm_b, [STORAGE_CAPACITY])

    def test_shape_and_order(self):
        res = dsa.run_dsa_multiple([self.mm_a, self.mm_b])

        # Both are synchronised to 2 variables: (1 central + 2 variables x 2 bounds) x 2 metamodels
        self.assertEqual(len(res), 2 * (1 + 2 * 2))
        self.assertEqual(list(res.columns), dsa.DSA_MULTIPLE_INDEX_COLUMNS + STATISTICS)

        # Central runs first, then each variable at each bound, for every metamodel in turn
        self.assertEqual(list(res['bound'].iloc[:2]), ['central', 'central'])
        self.assertEqual(list(res['metamodel'].iloc[:2]), [self.mm_a.id, self.mm_b.id])
        order = list(self.mm_a.variables.keys())
        expected_varids = sorted([STORAGE_CAPACITY, RESIDENT_TARIFF], key = order.index)
        body = res.iloc[2:]
        self.assertEqual(
            list(zip(body['varid'], body['bound'], body['metamodel'])),
            [
                (varid, bound, mm_id)
                for varid in expected_varids
                for bound in ('lower', 'upper')
                for mm_id in (self.mm_a.id, self.mm_b.id)
            ]
        )
        self.assertTrue(body['varied'].all())
        # The selection has been synchronised onto the metamodels
        self.assertTrue(self.mm_b.variables[RESIDENT_TARIFF].dsa_selected)

    def test_bounds_differ_where_variables_independent(self):
        res = dsa.run_dsa_multiple([self.mm_a, self.mm_b]).set_index(['metamodel', 'varid', 'bound'])

        # Relative bounds of 0.9 and 1.1 about each metamodel's own storage capacity
        self.assertAlmostEqual(float(res.loc[(self.mm_a.id, STORAGE_CAPACITY, 'lower'), 'value']), 3600.0)
        self.assertAlmostEqual(float(res.loc[(self.mm_b.id, STORAGE_CAPACITY, 'lower'), 'value']), 1800.0)
        self.assertAlmostEqual(float(res.loc[(self.mm_b.id, STORAGE_CAPACITY, 'upper'), 'value']), 2200.0)

    def test_matches_single_metamodel_dsa(self):
        res = dsa.run_dsa_multiple([self.mm_a, self.mm_b], synchronise = True)

        for storage_capacity, mm in ((4000.0, self.mm_a), (2000.0, self.mm_b)):
            single_mm = make_sprake_metamodel(storage_capacity = storage_capacity)
            select_only(single_mm, [STORAGE_CAPACITY, RESIDENT_TARIFF])
            single = dsa.run_dsa(single_mm).set_index(['variable', 'bound'])
            multiple = dsa.dsa_multiple_for_metamodel(res, mm.id).set_index(['variable', 'bound'])

            self.assertEqual(list(multiple.index), list(single.index))
            pd.testing.assert_frame_equal(
                multiple.loc[:, STATISTICS], single.loc[:, STATISTICS], check_dtype = False
            )

    def test_metamodel_without_variable(self):
        # mm_b shares nothing with the selection: its variable is not DSA-possible for this run
        self.mm_b.variables[RESIDENT_TARIFF].dsa_selectable = False
        res = dsa.run_dsa_multiple([self.mm_a, self.mm_b])

        b = res.loc[res['metamodel'] == self.mm_b.id, :].set_index(['varid', 'bound'])
        central = b.loc[('', 'central'), STATISTICS]
        for bound in ('lower', 'upper'):
            row = b.loc[(RESIDENT_TARIFF, bound)]
            self.assertFalse(row['varied'])
            self.assertEqual(row['value'], '-')
            np.testing.assert_allclose(row[STATISTICS].to_numpy(dtype = float), central.to_numpy(dtype = float))
            # The variable is still labelled, so the metamodels line up
            self.assertEqual(row['variable'], self.mm_a.variables[RESIDENT_TARIFF].name)

        # The variable is left out of the individual results of mm_b
        single_b = dsa.dsa_multiple_for_metamodel(res, self.mm_b.id)
        self.assertNotIn(self.mm_a.variables[RESIDENT_TARIFF].name, list(single_b['variable']))
        all_b = dsa.dsa_multiple_for_metamodel(res, self.mm_b.id, varied_only = False)
        self.assertEqual(len(all_b), 5)

    def test_shared_variable(self):
        mm_c = make_sprake_metamodel()
        mm_c.variables[RESIDENT_TARIFF] = self.mm_a.variables[RESIDENT_TARIFF]
        select_only(mm_c, [RESIDENT_TARIFF])
        res = dsa.run_dsa_multiple([self.mm_a, mm_c])

        self.assertEqual(len(res), 2 * (1 + 2 * 2))
        # Both metamodels are the same apart from sharing the variable, so their results agree
        a = res.loc[res['metamodel'] == self.mm_a.id, STATISTICS].reset_index(drop = True)
        c = res.loc[res['metamodel'] == mm_c.id, STATISTICS].reset_index(drop = True)
        pd.testing.assert_frame_equal(a, c)
        self.assertFalse(self.mm_a.variables[RESIDENT_TARIFF].dsa_active)

    def test_progress_and_cancel(self):
        calls = []
        dsa.run_dsa_multiple(
            [self.mm_a, self.mm_b], [STATISTICS[0]],
            progress = lambda i, n: calls.append((i, n))
        )
        self.assertEqual(calls[0], (0, 10))
        self.assertEqual(calls[-1], (10, 10))

        n_checks = 0
        def cancel_after_first_variable():
            nonlocal n_checks
            n_checks += 1
            return n_checks > 2
        with self.assertRaises(InterruptedError):
            dsa.run_dsa_multiple([self.mm_a, self.mm_b], [STATISTICS[0]], cancel_status = cancel_after_first_variable)
        for mm in (self.mm_a, self.mm_b):
            for v in mm.variables.values():
                self.assertFalse(v.dsa_active)
                self.assertFalse(v.dsa_focussed)

    def test_precomputed_deterministic(self):
        for mm in (self.mm_a, self.mm_b):
            mm.model.run()
            mm.finance.run()
        res = dsa.run_dsa_multiple([self.mm_a, self.mm_b], precomputed_deterministic = True)
        res_full = dsa.run_dsa_multiple([self.mm_a, self.mm_b])
        pd.testing.assert_frame_equal(res, res_full)


class TestDSAPairwise(unittest.TestCase):
    """Pairwise comparisons of a whole-project DSA"""

    @classmethod
    def setUpClass(cls):
        cls.mm_a = make_sprake_metamodel()
        cls.mm_b = make_sprake_metamodel(storage_capacity = 2000.0)
        select_only(cls.mm_a, [STORAGE_CAPACITY, RESIDENT_TARIFF])
        select_only(cls.mm_b, [])
        cls.results = dsa.run_dsa_multiple([cls.mm_a, cls.mm_b])

    def test_increments(self):
        pw = dsa.dsa_pairwise(self.results, self.mm_b.id, self.mm_a.id)

        self.assertEqual(list(pw.columns), ['variable', 'bound', 'value'] + list(get_args(dsa.DSA_PAIRWISE_STATISTIC)))
        self.assertEqual(len(pw), 1 + 2 * 2)
        self.assertEqual(tuple(pw.iloc[0][['variable', 'bound']]), ('deterministic', 'central'))

        comp = self.results.loc[self.results['metamodel'] == self.mm_b.id].reset_index(drop = True)
        ref = self.results.loc[self.results['metamodel'] == self.mm_a.id].reset_index(drop = True)
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
            np.testing.assert_allclose(pw[f'incremental_benefit_cost_ratio_{disc}'], d_benefits / d_costs)

        # Smaller storage costs less, so the comparator has negative incremental costs centrally
        self.assertLess(pw.loc[0, 'incremental_total_costs_undiscounted'], 0)
        self.assertIn(' | ', pw.loc[1, 'value'])

    def test_antisymmetric(self):
        ab = dsa.dsa_pairwise(self.results, self.mm_a.id, self.mm_b.id)
        ba = dsa.dsa_pairwise(self.results, self.mm_b.id, self.mm_a.id)
        np.testing.assert_allclose(
            ab['incremental_net_monetary_value_discounted'], -ba['incremental_net_monetary_value_discounted']
        )
        # The ratio is symmetric: both increments change sign
        np.testing.assert_allclose(
            ab['incremental_benefit_cost_ratio_discounted'], ba['incremental_benefit_cost_ratio_discounted']
        )

    def test_self_comparison(self):
        pw = dsa.dsa_pairwise(self.results, self.mm_a.id, self.mm_a.id)
        self.assertTrue((pw['incremental_total_costs_discounted'] == 0).all())
        self.assertTrue(pw['incremental_benefit_cost_ratio_discounted'].isna().all())

    def test_missing(self):
        with self.assertRaises(KeyError):
            dsa.dsa_pairwise(self.results, 'nonexistent', self.mm_a.id)
        with self.assertRaises(KeyError):
            dsa.dsa_pairwise(self.results.drop(columns = ['total_present_costs_discounted']), self.mm_b.id, self.mm_a.id)

    def test_safe_ratio(self):
        r = dsa._safe_ratio(pd.Series([1.0, -2.0, 0.0, 3.0]), pd.Series([0.0, 0.0, 0.0, 2.0]))
        self.assertEqual(r.iloc[0], np.inf)
        self.assertEqual(r.iloc[1], -np.inf)
        self.assertTrue(np.isnan(r.iloc[2]))
        self.assertEqual(r.iloc[3], 1.5)


PV_CAPACITY = 'gen_input.pv_capacity.0'
WIND_CAPACITY = 'gen_input.wind_capacity.0'
PV_CAPEX = 'gen_costs.pv_capex_per_kw.0'
WIND_CAPEX = 'gen_costs.wind_capex_per_kw.0'
NOMINAL_CAPEX = 100.0
"""Nominal capex rate of wind (£/kW) and PV (£/kWp)."""


class TestDSAPairwiseCapex(unittest.TestCase):
    """Pairwise DSA of two configurations with independent generation capacities but shared capex rates.

    Config 1 is wind-heavy (10 kWp PV, 100 kW wind) and config 2 PV-heavy (100 kWp PV, 10 kW wind). The capex
    rates of wind and PV are shared, nominally 100 £/kW(p), and varied by +-10% (relative bounds).
    """

    @classmethod
    def setUpClass(cls):
        cls.mm_1 = make_sprake_metamodel()
        cls.mm_2 = make_sprake_metamodel()

        # Shared capex rates: one instance of each in both configurations
        for varid in (PV_CAPEX, WIND_CAPEX):
            v = cls.mm_1.variables[varid]
            v.set_parameters(NOMINAL_CAPEX, 0.2 * NOMINAL_CAPEX)
            v.dsa_bounds_type = 'relative'
            v.dsa_lower = 0.9
            v.dsa_upper = 1.1
            cls.mm_2.variables[varid] = v

        # Independent capacities
        cls.capacities = {
            cls.mm_1.id: {PV_CAPACITY: 10.0, WIND_CAPACITY: 100.0},
            cls.mm_2.id: {PV_CAPACITY: 100.0, WIND_CAPACITY: 10.0},
        }
        for mm in (cls.mm_1, cls.mm_2):
            for varid, capacity in cls.capacities[mm.id].items():
                mm.variables[varid].set_parameters(capacity)
            for v in mm.variables.values():
                v.update_model(mm.model)
                v.update_model(mm.finance)
            select_only(mm, [PV_CAPEX, WIND_CAPEX])

        cls.results = dsa.run_dsa_multiple([cls.mm_1, cls.mm_2])

    def _capex_changes(self, mm, statistic = 'all_capex_costs_undiscounted'):
        """Change in capex from the central run of a configuration, by (varid, bound)."""
        df = self.results.loc[self.results['metamodel'] == mm.id, :].set_index(['varid', 'bound'])
        return df[statistic] - df.loc[('', 'central'), statistic]

    def test_setup(self):
        self.assertIs(self.mm_1.variables[WIND_CAPEX], self.mm_2.variables[WIND_CAPEX])
        self.assertIsNot(self.mm_1.variables[WIND_CAPACITY], self.mm_2.variables[WIND_CAPACITY])
        res = self.results.set_index(['metamodel', 'varid', 'bound'])
        for mm in (self.mm_1, self.mm_2):
            for varid in (PV_CAPEX, WIND_CAPEX):
                self.assertAlmostEqual(float(res.loc[(mm.id, varid, 'lower'), 'value']), 0.9 * NOMINAL_CAPEX)
                self.assertAlmostEqual(float(res.loc[(mm.id, varid, 'upper'), 'value']), 1.1 * NOMINAL_CAPEX)

    def test_capex_increases_at_upper_bound(self):
        for statistic in ('all_capex_costs_undiscounted', 'all_capex_costs_discounted'):
            for mm in (self.mm_1, self.mm_2):
                changes = self._capex_changes(mm, statistic)
                for varid in (PV_CAPEX, WIND_CAPEX):
                    self.assertGreater(changes[(varid, 'upper')], 0)

    def test_capex_decreases_at_lower_bound(self):
        for statistic in ('all_capex_costs_undiscounted', 'all_capex_costs_discounted'):
            for mm in (self.mm_1, self.mm_2):
                changes = self._capex_changes(mm, statistic)
                for varid in (PV_CAPEX, WIND_CAPEX):
                    self.assertLess(changes[(varid, 'lower')], 0)

    def test_wind_capex_affects_config_1_more(self):
        changes_1 = self._capex_changes(self.mm_1)
        changes_2 = self._capex_changes(self.mm_2)
        for bound in ('lower', 'upper'):
            self.assertGreater(abs(changes_1[(WIND_CAPEX, bound)]), abs(changes_2[(WIND_CAPEX, bound)]))

    def test_pv_capex_affects_config_2_more(self):
        changes_1 = self._capex_changes(self.mm_1)
        changes_2 = self._capex_changes(self.mm_2)
        for bound in ('lower', 'upper'):
            self.assertGreater(abs(changes_2[(PV_CAPEX, bound)]), abs(changes_1[(PV_CAPEX, bound)]))

    def test_capex_changes_in_proportion_to_capacity(self):
        # All capex is incurred at the start, so each change is capacity x 10% of the nominal rate
        for mm in (self.mm_1, self.mm_2):
            changes = self._capex_changes(mm)
            for capex_varid, capacity_varid in ((PV_CAPEX, PV_CAPACITY), (WIND_CAPEX, WIND_CAPACITY)):
                expected = self.capacities[mm.id][capacity_varid] * 0.1 * NOMINAL_CAPEX
                self.assertAlmostEqual(changes[(capex_varid, 'upper')], expected, places = 6)
                self.assertAlmostEqual(changes[(capex_varid, 'lower')], -expected, places = 6)

    def test_pairwise_incremental_capex(self):
        # Config 1 (wind-heavy) against config 2 (PV-heavy)
        pw = dsa.dsa_pairwise(self.results, self.mm_1.id, self.mm_2.id)
        varids = self.results.loc[self.results['metamodel'] == self.mm_1.id, 'varid'].to_list()
        pw.index = pd.MultiIndex.from_arrays([varids, pw['bound']])

        for disc in ('undiscounted', 'discounted'):
            stat = f'incremental_all_capex_costs_{disc}'
            central = pw.loc[('', 'central'), stat]
            # Dearer wind widens config 1's extra capex; dearer PV narrows it
            self.assertGreater(pw.loc[(WIND_CAPEX, 'upper'), stat], central)
            self.assertLess(pw.loc[(WIND_CAPEX, 'lower'), stat], central)
            self.assertLess(pw.loc[(PV_CAPEX, 'upper'), stat], central)
            self.assertGreater(pw.loc[(PV_CAPEX, 'lower'), stat], central)
            # Opex does not depend on the capex rates
            opex = pw[f'incremental_all_recurrent_costs_{disc}']
            np.testing.assert_allclose(opex, opex.iloc[0])

        # The increment moves by the difference in capacity x 10% of the nominal rate: (100 - 10) x 10
        stat = 'incremental_all_capex_costs_undiscounted'
        central = pw.loc[('', 'central'), stat]
        self.assertAlmostEqual(pw.loc[(WIND_CAPEX, 'upper'), stat] - central, 900.0, places = 6)
        self.assertAlmostEqual(pw.loc[(PV_CAPEX, 'upper'), stat] - central, -900.0, places = 6)


if __name__ == '__main__':
    unittest.main()
