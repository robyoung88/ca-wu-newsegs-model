"""
Unit tests of the plots of `newsegsmodelutils.plots`, and of the patches of the PSA plots in the app
(`newsegsmodelapp.components.psa_plots`), which update a drawn figure with the same values as its figure function.
"""
import json
import unittest

from dash import Patch
import matplotlib
matplotlib.use('Agg')
import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.utils

from newsegsmodelapp.components import psa_plots as app_psa_plots
from newsegsmodelutils.plots import apply_values, optim as optim_plots, psa as psa_plots, wind_resource

def _psa_data(seed: int, n: int = 100) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        'draw': np.arange(n + 1),
        'deterministic': [True] + [False] * n,
        'total_present_costs_discounted': np.r_[1000., rng.normal(1000, 200, n)],
        'total_present_benefits_discounted': np.r_[1100., rng.normal(1100, 300, n)],
        'net_present_value_discounted': np.r_[100., rng.normal(100, 350, n)],
    })

def _json(figure) -> dict:
    return json.loads(json.dumps(figure, cls = plotly.utils.PlotlyJSONEncoder))

PLOTS = {
    'scatter': (psa_plots.psa_scatter, psa_plots.psa_scatter_values, psa_plots.psa_scatter_cleared_values, app_psa_plots.psa_scatter_update, {}),
    'cdf': (psa_plots.psa_cdf, psa_plots.psa_cdf_values, psa_plots.psa_cdf_cleared_values, app_psa_plots.psa_cdf_update, {}),
    'convergence': (
        psa_plots.psa_convergence, psa_plots.psa_convergence_values, psa_plots.psa_convergence_cleared_values,
        app_psa_plots.psa_convergence_update, {'statistic': 'net_present_value_discounted'},
    ),
}

class TestApplyValues(unittest.TestCase):

    def test_figure(self):
        fig = go.Figure(go.Scatter(x = [1], y = [2]))
        fig.add_shape(type = 'line')
        apply_values(fig, [(('data', 0, 'x'), [3, 4]), (('layout', 'shapes', 0, 'x0'), 5), (('layout', 'xaxis', 'title', 'text'), 'X')])
        self.assertEqual(list(fig.data[0].x), [3, 4])
        self.assertEqual(fig.layout.shapes[0].x0, 5)
        self.assertEqual(fig.layout.xaxis.title.text, 'X')

    def test_patch(self):
        patch = apply_values(Patch(), [(('data', 0, 'x'), [3, 4]), (('layout', 'xaxis', 'range'), [0, 1])])
        operations = patch.to_plotly_json()['operations']
        self.assertEqual(
            [(x['operation'], x['location'], x['params']['value']) for x in operations],
            [('Assign', ['data', 0, 'x'], [3, 4]), ('Assign', ['layout', 'xaxis', 'range'], [0, 1])],
        )

class TestPSAPlots(unittest.TestCase):

    def test_values_update_a_drawn_figure_as_drawing_it(self):
        # A figure drawn with some results, updated with others, is the figure drawn with those others
        for name, (draw, values, _, _, kwargs) in PLOTS.items():
            with self.subTest(plot = name):
                updated = apply_values(draw(_psa_data(1), **kwargs), values(_psa_data(2), **kwargs))
                self.assertEqual(_json(updated), _json(draw(_psa_data(2), **kwargs)))

    def test_empty_plots(self):
        for name, (draw, _, _, _, kwargs) in PLOTS.items():
            with self.subTest(plot = name):
                self.assertIsInstance(draw(None, **kwargs), go.Figure)

    def test_cleared_values(self):
        for name, (draw, _, cleared, _, kwargs) in PLOTS.items():
            with self.subTest(plot = name):
                fig = apply_values(draw(_psa_data(1), **kwargs), cleared())
                traces = {p[1] for p, _ in cleared() if p[0] == 'data'}
                self.assertTrue(traces)
                for trace in traces:
                    self.assertEqual((len(fig.data[trace].x), len(fig.data[trace].y)), (0, 0))

    def test_patches_carry_the_values(self):
        for name, (_, values, cleared, update, kwargs) in PLOTS.items():
            with self.subTest(plot = name):
                for data, expected in ((_psa_data(2), values(_psa_data(2), **kwargs)), (None, cleared())):
                    operations = update(data, **kwargs).to_plotly_json()['operations']
                    self.assertEqual([x['location'] for x in operations], [list(p) for p, _ in expected])
                    self.assertEqual(
                        _json([x['params']['value'] for x in operations]),
                        _json([v for _, v in expected]),
                    )

    def test_scatter_without_proportion(self):
        values = psa_plots.psa_scatter_values(_psa_data(1), show_proportion_ce = False)
        self.assertFalse([p for p, _ in values if p[:2] == ('layout', 'annotations')])
        self.assertFalse(psa_plots.psa_scatter(_psa_data(1), show_proportion_ce = False).layout.annotations)

    def test_registry(self):
        self.assertEqual(set(app_psa_plots.psa_plots), {'Scatter plot', 'Cumulative probability', 'Convergence'})
        for funcs in app_psa_plots.psa_plots.values():
            self.assertEqual(set(funcs), {'draw', 'update', 'controls', 'arguments'})

class TestOptimPlot(unittest.TestCase):

    def test_statistic_across_margin(self):
        data = pd.DataFrame({'gen_input.wind_capacity.0': [0., 100., 200.], 'net_present_value_discounted': [-3., -2., -1.]})
        fig = optim_plots.statistic_across_margin_plot(data, 'Wind capacity')
        self.assertEqual(fig.layout.xaxis.title.text, 'Wind capacity')
        self.assertEqual(fig.layout.yaxis.title.text, 'NPV (discounted)')
        self.assertEqual(list(fig.data[0].y), [-3., -2., -1.])

class TestWindResourcePlots(unittest.TestCase):

    def setUp(self):
        rng = np.random.default_rng(1)
        self.speeds = rng.weibull(2, 1000) * 7
        self.directions = rng.uniform(0, 360, 1000)

    def tearDown(self):
        plt.close('all')

    def test_roses(self):
        self.assertIsInstance(wind_resource.draw_wind_rose(self.speeds, self.directions, 15), matplotlib.figure.Figure)
        self.assertIsInstance(wind_resource.draw_energy_rose(self.speeds**3, self.directions, 15), matplotlib.figure.Figure)

    def test_profile(self):
        profile = pd.DataFrame({'height': np.repeat([10, 50], 500), 'speed': self.speeds, 'source': np.repeat(['meso', 'micro'], 500)})
        self.assertIsInstance(wind_resource.wind_speed_profile_box(profile), matplotlib.figure.Figure)
