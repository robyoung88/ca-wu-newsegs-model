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

        # The statistic before optimisation, without running the model
        self.evaluate = mock.patch.object(optim, 'evaluate_statistic', return_value = 1000.).start()
        self.addCleanup(mock.patch.stopall)
        self.result_provider = mock.MagicMock()

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
            self.result_provider,
            1,
            lambda *args: None,
            lambda: False,
        )

    @staticmethod
    def _fake_optimisation(mm, variables, target, method, progress, cancel_status):
        # Move each variable to its upper bound, as the optimiser would move it to its optimum. The
        # NPV is maximised, so the optimiser minimises its negative.
        for x in variables:
            mm.variables[x.varid].set_parameters(x.upper)
        return SimpleNamespace(success = True, fun = -1500., message = 'Optimization terminated successfully.')

    def _saved_result(self) -> dict:
        calls = [c for c in self.result_provider.upsert_result.call_args_list if c.args[0] == 'optimisation_result']
        self.assertEqual(len(calls), 1)
        return calls[0].args[2]

    def test_result_saved(self):
        with mock.patch.object(optim, 'run_optimisation', side_effect = self._fake_optimisation):
            self._run()
        result = self._saved_result()
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['statistic'], 'net_present_value_undiscounted')
        self.assertTrue(result['maximised'])
        # Evaluated on the copy, before optimising
        self.assertEqual(result['start_value'], 1000.)
        self.assertNotEqual(self.evaluate.call_args.args[0].id, self.mm.id)
        # The sign of the objective is undone
        self.assertEqual(result['final_value'], 1500.)
        self.assertEqual(result['variables'], [{
            'varid': self.varid, 'label': self.var.label,
            'before': float(self.original_parameters[0]), 'after': 20., 'lower': 10., 'upper': 20.,
        }])
        self.assertEqual(result['metamodel_name'], self.mm.name)
        self.assertEqual(result['new_metamodel_name'], self.mm.name + ' - Opt')
        proj = self.provider.get_project(self.proj.id)
        self.assertEqual(result['new_metamodel_id'], proj.metamodels[1].id)

    def test_failure_saved(self):
        def fail(mm, variables, target, method, progress, cancel_status):
            return SimpleNamespace(success = False, fun = -1200., message = 'Maximum number of iterations has been exceeded.')
        with mock.patch.object(optim, 'run_optimisation', side_effect = fail):
            self.assertEqual(self._run(), 'ok')
        result = self._saved_result()
        self.assertEqual((result['status'], result['success']), ('failure', False))
        self.assertEqual(result['final_value'], 1200.)
        self.assertEqual(result['message'], 'Maximum number of iterations has been exceeded.')
        self.assertIsNone(result['new_metamodel_id'])
        # No configuration is added
        self.assertEqual(len(self.provider.get_project(self.proj.id).metamodels), 1)

    def _assert_configuration_kept(self, result: dict):
        # A success, but the project and its focus are as they were, and no configuration is named
        self.assertEqual((result['status'], result['success']), ('success', True))
        self.assertIsNone(result['new_metamodel_id'])
        self.assertIsNone(result['new_metamodel_name'])
        proj = self.provider.get_project(self.proj.id)
        self.assertEqual([x.id for x in proj.metamodels], [self.mm.id])
        self.assertEqual(proj.get_focussed_metamodel().id, self.mm.id)
        self.assertEqual(proj.metamodels[0].variables[self.varid].id, self.var.id)

    def test_no_improvement_keeps_the_configuration(self):
        def unchanged(mm, variables, target, method, progress, cancel_status):
            return SimpleNamespace(success = True, fun = -1000., message = 'Optimization terminated successfully.')
        with mock.patch.object(optim, 'run_optimisation', side_effect = unchanged):
            self.assertEqual(self._run(), 'ok')
        self._assert_configuration_kept(self._saved_result())

    def test_worse_than_a_start_outside_the_bounds_keeps_the_configuration(self):
        proj = self.provider.get_project(self.proj.id)
        var = proj.metamodels[0].variables[self.varid]
        var.set_parameters(5.) # Below the lower bound of 10
        self.provider.variable_provider.upsert_variable([var], force = True)
        with mock.patch.object(optim, 'run_optimisation', side_effect = self._fake_optimisation_to(-800.)):
            self.assertEqual(self._run(), 'ok')
        result = self._saved_result()
        self._assert_configuration_kept(result)
        self.assertEqual((result['start_value'], result['final_value']), (1000., 800.))
        self.assertEqual(result['variables'][0]['before'], 5.)
        self.assertEqual(self.provider.get_project(self.proj.id).metamodels[0].variables[self.varid].parameters[0], 5.)

    @staticmethod
    def _fake_optimisation_to(fun: float):
        def run(mm, variables, target, method, progress, cancel_status):
            for x in variables:
                mm.variables[x.varid].set_parameters(x.lower)
            return SimpleNamespace(success = True, fun = fun, message = 'Optimization terminated successfully.')
        return run

    def test_no_variables_selected(self):
        proj = self.provider.get_project(self.proj.id)
        var = proj.metamodels[0].variables[self.varid]
        var.optim_selected = False
        self.provider.variable_provider.upsert_variable([var], force = True)
        with mock.patch.object(optim, 'run_optimisation') as run:
            self.assertEqual(self._run(), optim_single_mm.NO_VARIABLES_MESSAGE)
        run.assert_not_called()
        self.assertEqual(self._saved_result()['status'], 'not_run')

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

    def test_optimised_configuration_focussed(self):
        with mock.patch.object(optim, 'run_optimisation', side_effect = self._fake_optimisation):
            self._run()
            self._run()
        proj = self.provider.get_project(self.proj.id)
        self.assertEqual(len(proj.metamodels), 3)
        # The latest optimised configuration is focussed, and each has its own name
        self.assertEqual(proj.get_focussed_metamodel().id, proj.metamodels[2].id)
        names = [x.name for x in proj.metamodels]
        self.assertEqual(len(set(names)), 3)
        self.assertEqual(names[1], self.mm.name + ' - Opt')

    def test_panel_saved_against_the_table_configuration(self):
        # The panel shown after an optimisation is saved where the results container reads it,
        # against the project's table configuration, and is read back as components
        from dash import html
        from dash.development.base_component import Component
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
        from newsegsmodelapp.plugins.models.aaa_default.processes.output import aaa_default_tables
        from newsegsmodelapp.registers import TableDrawRequest

        # A real result provider, which checks the component results are saved against, and saves
        # them to files as the app does
        result_provider = FromDatabaseResultProvider(db.get_engine, Path(self.db_dir.name) / 'results')
        self.result_provider = result_provider
        with mock.patch.object(optim, 'run_optimisation', side_effect = self._fake_optimisation):
            self._run()
        request = TableDrawRequest(project_id = self.proj.id, payload = json.dumps({'metamodel_id': self.mm.id}))
        self.assertEqual(
            aaa_default_tables._make_postopt_tables_sprake(
                request, self.provider, result_provider, 1, lambda *args: None, lambda: False
            ),
            'ok'
        )
        # Read as the results container reads it
        lproj = self.provider.get_lightweight_project(self.proj.id)
        panel, _ = result_provider.get_result('table_postopt_metamodel', lproj.table_config)
        self.assertIsInstance(panel, html.Div)
        self.assertTrue(panel.children)
        self.assertTrue(all(isinstance(x, Component) for x in panel.children))
        self.assertEqual(panel.children[0].children, 'Optimisation complete')

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
            mock.patch.object(aaa_default_tables.optim_plots, 'statistic_across_margin_plot'),
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
    test_no_improvement_keeps_the_configuration = None # pyright: ignore[reportAssignmentType]
    test_worse_than_a_start_outside_the_bounds_keeps_the_configuration = None # pyright: ignore[reportAssignmentType]


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
