"""
Unit tests of the feedback shown after an optimisation (`optim_feedback`), and of the statistics of
`optim` that it is built from.
"""
from types import SimpleNamespace
import unittest
from unittest import mock

from dash import html

from newsegsmodelapp.plugins.models.aaa_default.processes.output import optim_feedback as of
from newsegsmodelframework.newsegssensitivity import optim

def _result(status = 'success', start = 150000., final = 162345., **kwargs) -> dict:
    result = {
        'status': status,
        'success': status == 'success',
        'statistic': 'net_present_value_discounted',
        'maximised': True,
        'start_value': start,
        'final_value': final,
        'variables': [{'varid': 'gen_input.wind_capacity.0', 'label': 'Wind capacity', 'before': 100., 'after': 135.5, 'lower': 50., 'upper': 200.}],
        'metamodel_name': 'Site A',
        'new_metamodel_id': 'metam-2' if status == 'success' else None,
        'new_metamodel_name': 'Site A - Opt' if status == 'success' else None,
        'message': 'Optimization terminated successfully.',
        'opt': SimpleNamespace(fun = -final),
    }
    result.update(kwargs)
    return result

def _text(component) -> str:
    """All the text of a component and its children"""
    if component is None:
        return ''
    if isinstance(component, (str, int, float)):
        return str(component)
    if isinstance(component, (list, tuple)):
        return ' '.join(_text(x) for x in component)
    return _text(getattr(component, 'children', None))

class TestStatistics(unittest.TestCase):

    def test_statistic_from_objective(self):
        # The NPV is maximised by minimising its negative
        self.assertEqual(optim.statistic_from_objective('net_present_value_discounted', -1500.), 1500.)
        self.assertEqual(optim.statistic_from_objective('net_present_value_undiscounted', 200.), -200.)
        self.assertTrue(optim.statistic_is_maximised('net_present_value_discounted'))

    def test_evaluate_statistic(self):
        mm = mock.MagicMock()
        mm.finance.get_net_present_value_discounted.return_value = 1234.
        self.assertEqual(optim.evaluate_statistic(mm, 'net_present_value_discounted'), 1234.)
        mm.sync_model_with_changed_variables_deterministic.assert_called_once()
        mm.model.run.assert_called_once()
        mm.finance.run.assert_called_once()

class TestFormatting(unittest.TestCase):

    def test_money(self):
        self.assertEqual(of.format_money(12345.4), '£12,345')
        self.assertEqual(of.format_money(-12345.6), '−£12,346')
        self.assertEqual(of.format_money(-0.2), '£0')

    def test_value(self):
        self.assertEqual(of.format_value(135.5), '135.5')
        self.assertEqual(of.format_value(1234567.), '1,234,567')
        self.assertEqual(of.format_value(0.000123456), '0.000123456')
        self.assertEqual(of.format_value(20.), '20')
        self.assertEqual(of.format_value(0.), '0')
        self.assertEqual(of.format_value(float('inf')), 'none')

    def test_is_improvement(self):
        self.assertTrue(of.is_improvement(100., 101., maximised = True))
        self.assertFalse(of.is_improvement(100., 99., maximised = True))
        self.assertTrue(of.is_improvement(100., 99., maximised = False))
        # Rounding error is not an improvement
        self.assertFalse(of.is_improvement(150000., 150000. + 1e-7, maximised = True))

class TestImprovementSummary(unittest.TestCase):

    def test_improved(self):
        self.assertEqual(
            of.improvement_summary(_result()),
            'NPV (discounted) improved by £12,345 (+8.2%), from £150,000 to £162,345.'
        )

    def test_no_relative_change_from_a_start_at_or_below_zero(self):
        self.assertEqual(
            of.improvement_summary(_result(start = -5000., final = 2000.)),
            'NPV (discounted) improved by £7,000, from −£5,000 to £2,000.'
        )
        self.assertNotIn('%', of.improvement_summary(_result(start = 0., final = 2000.)))

    def test_not_improved(self):
        self.assertEqual(
            of.improvement_summary(_result(final = 150000.)),
            'NPV (discounted) did not improve: the configuration is already at or near its best within the bounds (£150,000).'
        )

class TestFeedback(unittest.TestCase):

    def test_success(self):
        children = of.create_optimisation_feedback(_result())
        text = _text(children)
        self.assertIn('Optimisation complete', text)
        self.assertIn('improved by £12,345 (+8.2%)', text)
        # The variable, before and after, and its bounds
        for value in ('Wind capacity', '100', '135.5', '50', '200'):
            self.assertIn(value, text)
        self.assertIn('Site A - Opt', text)
        # The optimiser's result is in a closed Details
        details = [x for x in children if isinstance(x, html.Details)]
        self.assertEqual(len(details), 1)
        self.assertFalse(getattr(details[0], 'open', False))

    def test_success_without_improvement(self):
        text = _text(of.create_optimisation_feedback(_result(final = 150000.)))
        self.assertIn('did not improve', text)
        self.assertNotIn('new configuration', text)

    def test_failure(self):
        result = _result('failure', final = 155000., message = 'Maximum number of iterations has been exceeded.')
        text = _text(of.create_optimisation_feedback(result))
        self.assertIn('Optimisation did not succeed', text)
        self.assertIn('Maximum number of iterations has been exceeded.', text)
        self.assertIn('£155,000', text)
        self.assertIn('has not been saved', text)
        self.assertIn('Try another optimisation method.', text)

    def test_failure_without_improvement(self):
        text = _text(of.create_optimisation_feedback(_result('failure', final = 140000.)))
        self.assertNotIn('has not been saved', text)

    def test_not_run(self):
        text = _text(of.create_optimisation_feedback({'status': 'not_run', 'success': False, 'message': 'x'}))
        self.assertIn('Optimisation not run', text)
        self.assertIn('No variables are selected', text)

    def test_result_saved_before_the_feedback(self):
        for success in (True, False):
            children = of.create_optimisation_feedback({'success': success, 'opt': SimpleNamespace(message = 'old')})
            self.assertTrue(children)
