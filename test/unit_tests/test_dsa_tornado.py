"""Unit tests of the multiple-configuration DSA tornado plot (`newsegsmodelapp.components.stats.multi_tornado_plot`)."""
import unittest

import numpy as np
import pandas as pd

from newsegsmodelapp.components import stats

STATISTIC = 'net_present_value_undiscounted'

def _dsa_df(central: float, deltas: dict) -> pd.DataFrame:
    """DSA table of one configuration with the (lower, upper) change from the central value of each variable"""
    rows = {
        (var, STATISTIC): {
            ('absolute', 'central'): central,
            ('absolute', 'lower'): central + low,
            ('absolute', 'upper'): central + up,
            ('absolute', 'interval'): up - low,
        }
        for var, (low, up) in deltas.items()
    }
    df = pd.DataFrame.from_dict(rows, orient = 'index')
    df.columns = pd.MultiIndex.from_tuples(df.columns)
    df.index = pd.MultiIndex.from_tuples(df.index, names = ['variable', 'statistic'])
    return df

class TestMultiTornadoCentered(unittest.TestCase):
    def setUp(self):
        self.dfs = {
            'A': _dsa_df(1000., {'x': (-50., 80.), 'y': (-10., 20.)}),
            'B': _dsa_df(5000., {'x': (-30., 40.), 'y': (-5., 15.)}),
        }

    def _bars(self, centered):
        fig = stats.multi_tornado_plot(self.dfs, STATISTIC, centered = centered)
        return fig, {t.name: t for t in fig.data}

    def test_uncentered_bars_start_at_central_value(self):
        _, bars = self._bars(False)
        np.testing.assert_array_equal(bars['B - lower'].base, [5000., 5000.])
        np.testing.assert_array_equal(bars['A - upper'].base, [1000., 1000.])

    def test_centered_bars_start_at_zero_with_same_variation(self):
        fig, bars = self._bars(True)
        _, uncentered = self._bars(False)
        for name, bar in bars.items():
            self.assertEqual(bar.base, 0)
            np.testing.assert_array_equal(bar.x, uncentered[name].x)
        np.testing.assert_array_equal(bars['A - lower'].x, [-50., -10.])
        np.testing.assert_array_equal(bars['B - upper'].x, [40., 15.])
        self.assertIn('from the central value', fig.layout.xaxis.title.text)

    def test_hover_has_absolute_result(self):
        _, bars = self._bars(True)
        np.testing.assert_array_equal(bars['B - upper'].customdata, [5040., 5015.])

    def test_default_is_uncentered(self):
        fig = stats.multi_tornado_plot(self.dfs, STATISTIC)
        self.assertNotEqual(fig.data[0].base[0], 0)
