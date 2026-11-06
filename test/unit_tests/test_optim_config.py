"""
Unit tests of the optimisation configuration held by variables and by the OptimComponent of a metamodel
"""
import copy
import json
from typing import cast
import unittest

from newsegsmodelframework import register_plugins # noqa: F401 - registers the project factories
from newsegsmodelframework.core.constructors.constructors import find_constructor
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.optim_component import OptimComponent
from newsegsmodelframework.newsegsvariable.variable import Variable
from newsegsmodelframework.util import jsonfuncs


def _optim_variable(**kwargs) -> Variable:
    return Variable(
        'optim_variable',
        distribution = 'numeric_constant',
        interface_section = 'section',
        interface_key = 'key',
        default_parameters = [5.],
        interface_min = 1.,
        interface_max = 100.,
        optim_selectable = True,
        **kwargs
    )

def _round_trip(component):
    """Restore a component from its JSON, as from storage or a download."""
    odict = json.loads(json.dumps(component.to_dict(), cls = jsonfuncs.NumpyEncoder))
    return find_constructor(odict['constructor_class'], odict['class'])(odict)


class TestVariableOptimConfig(unittest.TestCase):

    def test_bounds_fall_back_to_interface_limits(self):
        var = _optim_variable()
        self.assertIsNone(var.optim_min)
        self.assertIsNone(var.optim_max)
        self.assertEqual(var.get_optim_bounds(), (1., 100.))
        self.assertEqual(var.optim_plot_intervals, 10)

        var.optim_min = 10.
        self.assertEqual(var.get_optim_bounds(), (10., 100.))
        var.optim_max = 20.
        self.assertEqual(var.get_optim_bounds(), (10., 20.))

    def test_settings_are_revision_tracked(self):
        var = _optim_variable()
        for att, value in (('optim_min', 2.), ('optim_max', 50.), ('optim_plot_intervals', 15)):
            var._syncronise()
            r0 = var.revision
            setattr(var, att, value)
            self.assertGreater(var.revision, r0, att)

    def test_serialisation_round_trip(self):
        var = _optim_variable()
        var.optim_min = 2.
        var.optim_max = 50.
        var.optim_plot_intervals = 15

        restored = cast(Variable, _round_trip(var))
        self.assertEqual(restored.get_optim_bounds(), (2., 50.))
        self.assertEqual(restored.optim_plot_intervals, 15)

    def test_deepcopy_carries_settings(self):
        var = _optim_variable()
        var.optim_min = 2.
        var.optim_plot_intervals = 15

        var_copy = copy.deepcopy(var)
        self.assertEqual(var_copy.get_optim_bounds(), (2., 100.))
        self.assertEqual(var_copy.optim_plot_intervals, 15)

        # The copy is independent of the original
        var_copy.optim_min = 3.
        self.assertEqual(var.optim_min, 2.)

    def test_version_is_recorded(self):
        var = _optim_variable()
        self.assertEqual(var.to_dict()['version'], Variable._version)

    def test_unversioned_payload_loads_with_defaults(self):
        var = _optim_variable()
        var.optim_min = 2.
        var.optim_plot_intervals = 15
        odict = json.loads(var.json_dumps())
        # As saved before the optimisation settings were held by the variable
        del odict['version']
        for k in ('optim_min', 'optim_max', 'optim_plot_intervals'):
            odict['_config'].pop(k, None)

        restored = cast(Variable, find_constructor(odict['constructor_class'], odict['class'])(odict))
        self.assertEqual(restored.get_optim_bounds(), (1., 100.))
        self.assertEqual(restored.optim_plot_intervals, 10)

    def test_newer_version_is_rejected(self):
        odict = json.loads(_optim_variable().json_dumps())
        odict['version'] = '99.0.0'
        with self.assertRaisesRegex(ValueError, 'newer than the version'):
            find_constructor(odict['constructor_class'], odict['class'])(odict)


class TestOptimComponent(unittest.TestCase):

    def setUp(self):
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
        self.proj = PROJECT_FACTORIES['sprake']()
        self.mm = cast(NewsegsMetaModel, self.proj.metamodels[0])

    def test_defaults(self):
        self.assertIsInstance(self.mm.optim_config, OptimComponent)
        self.assertEqual(self.mm.optim_config.method, 'Nelder-Mead')
        self.assertEqual(self.mm.optim_config.statistic, 'net_present_value_discounted')
        self.assertIn(self.mm.optim_config, self.mm.get_components(component_group = 'component_configs'))

    def test_round_trip(self):
        comp = OptimComponent()
        comp.method = 'Powell'
        comp.statistic = 'net_present_value_undiscounted'
        restored = cast(OptimComponent, _round_trip(comp))
        self.assertEqual(restored.id, comp.id)
        self.assertEqual(restored.method, 'Powell')
        self.assertEqual(restored.statistic, 'net_present_value_undiscounted')

    def test_change_dirties_metamodel(self):
        self.mm._chain_syncronise()
        self.assertFalse(self.mm.chain_modified)
        self.mm.optim_config.method = 'Powell'
        self.assertTrue(self.mm.chain_modified)

    def test_metamodel_deepcopy_with_new_ids(self):
        self.mm.optim_config.method = 'Powell'
        mm_copy = copy.deepcopy(self.mm)
        self.assertIsNot(mm_copy.optim_config, self.mm.optim_config)
        self.assertEqual(mm_copy.optim_config.method, 'Powell')

        mm_copy.anonymise_ids()
        self.assertNotEqual(mm_copy.optim_config.id, self.mm.optim_config.id)

        mm_copy.optim_config.method = 'TNC'
        self.assertEqual(self.mm.optim_config.method, 'Powell')

    def test_metamodel_representation_round_trip(self):
        self.mm.optim_config.method = 'Powell'
        odict = json.loads(json.dumps(self.mm.to_dict_repr(), cls = jsonfuncs.NumpyEncoder))
        restored = cast(NewsegsMetaModel, find_constructor(odict['constructor_class'], odict['class'])(odict))
        self.assertEqual(restored.optim_config.method, 'Powell')

    def test_old_metamodel_payload_gets_defaults(self):
        self.mm.optim_config.method = 'Powell'
        odict = json.loads(json.dumps(self.mm.to_dict_repr(), cls = jsonfuncs.NumpyEncoder))
        # As saved before the metamodel held an OptimComponent
        del odict['_optim_config']
        del odict['version']
        restored = cast(NewsegsMetaModel, find_constructor(odict['constructor_class'], odict['class'])(odict))
        self.assertIsInstance(restored.optim_config, OptimComponent)
        self.assertEqual(restored.optim_config.method, 'Nelder-Mead')
        # The default is kept, rather than made anew on each access
        self.assertIs(restored.optim_config, restored.optim_config)


if __name__ == '__main__':
    unittest.main()
