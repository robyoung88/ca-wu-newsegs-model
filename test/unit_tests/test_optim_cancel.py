"""
Unit tests of cancelling an optimisation (`optim.run_optimisation`), for every method offered (#152).

scipy ignores a callback returning True, so cancellation used to take effect only when the optimiser finished. It is
now checked before each run of the models, which stops every method within one run.

The metamodel is a fake whose statistic is a function of its variables, so no model is run.
"""
from typing import get_args
import unittest

import numpy as np

from newsegsmodelframework.newsegsmetamodel.optim_component import OPTIMISATION_METHOD
from newsegsmodelframework.newsegssensitivity import optim

class _Variable:
    def __init__(self, value: float):
        self.parameters = (value,)

    def set_parameters(self, *parameters):
        self.parameters = tuple(parameters)

    def get_deterministic_value(self):
        return self.parameters[0]

class _Finance:
    """The NPV is highest at (1, 2, 3)"""
    def __init__(self, mm):
        self.mm = mm

    def run(self):
        pass

    def get_net_present_value_discounted(self):
        x = np.asarray([v.parameters[0] for v in self.mm.variables.values()])
        return -float(np.sum((x - np.asarray([1., 2., 3.]))**2))

class _Model:
    def __init__(self):
        self.runs = 0

    def run(self):
        self.runs += 1

class _MetaModel:
    def __init__(self):
        self.variables = {f'v{i}': _Variable(5.) for i in range(3)}
        self.model = _Model()
        self.finance = _Finance(self)

    def sync_model_with_changed_variables_deterministic(self):
        pass

    def update_model_from_variable_deterministic(self, varid):
        pass

def _variables(mm) -> list[optim.OptimVariable]:
    return [optim.OptimVariable(varid, lower = -10., upper = 10.) for varid in mm.variables]

class TestCancel(unittest.TestCase):

    def test_every_method_stops_within_a_run(self):
        for method in get_args(OPTIMISATION_METHOD):
            with self.subTest(method = method):
                mm = _MetaModel()
                requested_at = None
                def cancel_status():
                    nonlocal requested_at
                    # Cancelled once the models have run 5 times
                    if requested_at is None and mm.model.runs >= 5:
                        requested_at = mm.model.runs
                    return requested_at is not None

                with self.assertRaises(InterruptedError):
                    optim.run_optimisation(mm, _variables(mm), method = method, cancel_status = cancel_status)
                # No run of the models after the request
                self.assertEqual(mm.model.runs, requested_at)

    def test_cancelled_before_starting(self):
        mm = _MetaModel()
        with self.assertRaises(InterruptedError):
            optim.run_optimisation(mm, _variables(mm), cancel_status = lambda: True)
        self.assertEqual(mm.model.runs, 0)

    def test_runs_to_the_end_without_cancellation(self):
        for method in get_args(OPTIMISATION_METHOD):
            with self.subTest(method = method):
                mm = _MetaModel()
                progress = []
                opt = optim.run_optimisation(
                    mm, _variables(mm), method = method,
                    progress = lambda i, n: progress.append(i), cancel_status = lambda: False,
                )
                self.assertTrue(opt.success, opt.message)
                np.testing.assert_allclose(
                    [v.parameters[0] for v in mm.variables.values()], [1., 2., 3.], atol = 1e-2
                )
                self.assertTrue(progress)
