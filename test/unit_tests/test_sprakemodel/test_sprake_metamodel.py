"""
Unit tests for newsegsmetamodel using Sprake settings
"""

import unittest

import newsegsmetamodel
from test.unit_tests.common import setup_test_env
setup_test_env()

from newsegsmodel import sprakemodel
from newsegsfinance import sprakefinance

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
