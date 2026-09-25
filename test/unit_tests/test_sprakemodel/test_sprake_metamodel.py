"""
Unit tests for newsegsmetamodel using Sprake settings
"""

from typing import cast
import unittest

from newsegsmodelframework.core.constructors.constructors import find_constructor
import newsegsmodelframework.newsegsmetamodel as newsegsmetamodel
from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

from newsegsmodelframework.newsegsmodel import sprakemodel
from newsegsmodelframework.newsegsfinance import sprakefinance

class TestMetaModelSprake(unittest.TestCase):
    def test_name(self):
        mdl = sprakemodel.SprakeModel.from_none()
        fnc = sprakefinance.SprakeFinance.from_none()
        fnc.set_model(mdl)

        mm = newsegsmetamodel.NewsegsMetaModel(mdl, fnc)

        self.assertIsInstance(mm.name, str)
        mm1 = mm.name

        mm.name = 'spam'
        self.assertEqual(mm.name, 'spam')

    def test_serialisation(self):
        proj = PROJECT_FACTORIES['sprake']()

        mm1 = proj.metamodels[0]

        d1 = mm1.to_dict_repr()

        constr = find_constructor(d1['constructor_class'], d1['class'])

        mm2 = cast(newsegsmetamodel.NewsegsMetaModel, constr(d1))

        for k, v in mm1.__dict__.items():
            if not isinstance(v, object):
                self.assertEqual(getattr(mm1, k), getattr(mm2, k))

        for k in mm1.variables.keys():
            self.assertEqual(mm1.variables[k]._config, mm2.variables[k]._config)
            self.assertEqual(mm1.variables[k].deterministic_value, mm2.variables[k].deterministic_value)
            var1 = mm1.variables[k]
            var2 = mm2.variables[k]
            for k, v in var1.__dict__.items():
                if not isinstance(v, object):
                    self.assertEqual(getattr(var1, k), getattr(var2, k))

        mdl1 = mm1.model
        mdl2 = mm2.model
        for k, v in mdl1.__dict__.items():
            if not isinstance(v, object):
                self.assertEqual(getattr(mdl1, k), getattr(mdl2, k))

        fnc1 = mm1.finance
        fnc2 = mm2.finance
        for k, v in fnc1.__dict__.items():
            if not isinstance(v, object):
                self.assertEqual(getattr(fnc1, k), getattr(fnc2, k))
                