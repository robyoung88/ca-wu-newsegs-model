"""
Unit tests of the optimisation run of a single metamodel, with the optimiser replaced so that no model is run
"""
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
from typing import cast
import unittest
from unittest import mock

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.plugins.pages.processes import optim_single_mm
from newsegsmodelframework import register_plugins # noqa: F401 - registers the project factories
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegssensitivity import optim
from newsegsmodelframework.newsegsvariable.variable import variable_uid

from config import settings


class TestOptimRun(unittest.TestCase):

    def setUp(self):
        self.db_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.db_dir.name) / 'tempdb.db'
        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
        self.addCleanup(self._cleanup)
        tbls.create_all_tables(db.get_engine(writer = True))

        self.provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        self.proj = PROJECT_FACTORIES['sprake']()
        self.mm = cast(NewsegsMetaModel, self.proj.metamodels[0])
        self.mm.optim_config.method = 'Powell'
        self.mm.optim_config.statistic = 'net_present_value_undiscounted'

        optim_vars = [x for x in self.mm.variables.values() if x.optim_possible and x.optim_selectable]
        for x in optim_vars:
            x.optim_selected = False
        self.var = optim_vars[0]
        self.var.optim_selected = True
        self.var.optim_min = 10.
        self.var.optim_max = 20.
        self.varid = variable_uid(self.var)
        self.other_var = optim_vars[1]

        self.provider.add_component(self.proj)
        self.original_parameters = self.var.parameters

    def _cleanup(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()
        self.db_dir.cleanup()

    def _run(self):
        request = optim_single_mm.OptimRunMetamodelRunRequest(
            project_id = self.proj.id,
            payload = json.dumps({'metamodel_id': self.mm.id}),
        )
        return optim_single_mm.execute_optim_single_mm_run(
            request,
            self.provider,
            mock.MagicMock(),
            1,
            lambda *args: None,
            lambda: False,
        )

    @staticmethod
    def _fake_optimisation(mm, variables, target, method, progress, cancel_status):
        # Move each variable to its upper bound, as the optimiser would move it to its optimum
        for x in variables:
            mm.variables[x.varid].set_parameters(x.upper)
        return SimpleNamespace(success = True)

    def test_settings_are_passed_to_the_optimiser(self):
        with mock.patch.object(optim, 'run_optimisation', side_effect = self._fake_optimisation) as run:
            self.assertEqual(self._run(), 'ok')

        kwargs = run.call_args.kwargs
        self.assertEqual(kwargs['method'], 'Powell')
        self.assertEqual(kwargs['target'], 'net_present_value_undiscounted')
        variables = run.call_args.args[1]
        self.assertEqual([(x.varid, x.lower, x.upper) for x in variables], [(self.varid, 10., 20.)])

    def test_acts_on_a_copy(self):
        with mock.patch.object(optim, 'run_optimisation', side_effect = self._fake_optimisation):
            self._run()

        proj = self.provider.get_project(self.proj.id)
        self.assertEqual(len(proj.metamodels), 2)
        original, optimised = cast(list[NewsegsMetaModel], list(proj.metamodels))

        # The original metamodel and its variables are unchanged
        self.assertEqual(original.id, self.mm.id)
        self.assertEqual(original.variables[self.varid].id, self.var.id)
        self.assertEqual(original.variables[self.varid].parameters, self.original_parameters)

        # The new metamodel has its own copy of the variable, which keeps the settings
        new_var = optimised.variables[self.varid]
        self.assertNotEqual(new_var.id, self.var.id)
        self.assertEqual(new_var.parameters[0], 20.)
        self.assertEqual(new_var.get_optim_bounds(), (10., 20.))
        self.assertNotEqual(optimised.optim_config.id, original.optim_config.id)
        self.assertEqual(optimised.optim_config.method, 'Powell')

    def test_invalid_bounds_are_reported(self):
        proj = self.provider.get_project(self.proj.id)
        mm = proj.metamodels[0]
        var = mm.variables[self.varid]
        var.optim_min = 30. # Above the upper bound
        other = mm.variables[variable_uid(self.other_var)]
        other.optim_selected = True
        other.interface_max = None # No upper bound to fall back to
        self.provider.variable_provider.upsert_variable([var, other], force = True)

        with mock.patch.object(optim, 'run_optimisation') as run:
            with self.assertRaises(optim.InvalidOptimBoundsError) as cm:
                self._run()
        run.assert_not_called()
        message = str(cm.exception)
        self.assertIn(var.label, message)
        self.assertIn('not below', message)
        self.assertIn(other.label, message)
        self.assertIn('no upper bound', message)
        self.assertFalse(optim.InvalidOptimBoundsError.retryable)


class TestMarginalPlot(TestOptimRun):
    """The marginal plot of the statistic, with the evaluation replaced so that no model is run"""

    def _plot(self):
        from newsegsmodelapp.plugins.models.aaa_default.processes.output import aaa_default_tables
        from newsegsmodelapp.registers import TableDrawRequest
        self.var.optim_plot_intervals = 50 # Beyond the limit of 20
        self.provider.variable_provider.upsert_variable(self.var)
        request = TableDrawRequest(
            project_id = self.proj.id,
            payload = json.dumps({'metamodel_id': self.mm.id, 'varid': self.varid}),
        )
        with (
            mock.patch.object(optim, 'evaluate_statistic_across_margin') as evaluate,
            mock.patch.object(optim, 'statistic_across_margin_plot'),
        ):
            rval = aaa_default_tables._trigger_plot_marginal_optim(
                request, self.provider, mock.MagicMock(), 1, lambda *args: None, lambda: False,
            )
        return rval, evaluate

    def test_settings_are_used(self):
        rval, evaluate = self._plot()
        self.assertEqual(rval, 'ok')
        _, varid, stat, lower, upper, res = evaluate.call_args.args
        self.assertEqual((varid, stat, lower, upper, res), (self.varid, 'net_present_value_undiscounted', 10., 20., 20))

    def test_invalid_bounds_are_reported(self):
        self.var.optim_min = 30.
        with self.assertRaisesRegex(optim.InvalidOptimBoundsError, self.var.label):
            self._plot()

    # The run tests are not repeated
    test_settings_are_passed_to_the_optimiser = None # pyright: ignore[reportAssignmentType]
    test_acts_on_a_copy = None # pyright: ignore[reportAssignmentType]


class TestOptimBoundsCheck(unittest.TestCase):

    def test_problems(self):
        from newsegsmodelframework.newsegsvariable.variable import Variable
        var = Variable('v', distribution = 'numeric_constant', default_parameters = [1.], interface_min = 0., interface_max = 10.)
        self.assertIsNone(optim.optim_bounds_problem(var))
        var.optim_min = 10.
        self.assertIn('not below', optim.optim_bounds_problem(var))
        var.optim_min = None
        var.interface_min = None
        self.assertEqual(optim.optim_bounds_problem(var), 'no lower bound')
        optim.check_optim_bounds([]) # Nothing to complain about


if __name__ == '__main__':
    unittest.main()
