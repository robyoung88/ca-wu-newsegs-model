

import os
from pathlib import Path
import tempfile
import unittest

from config import settings

from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider

class TestStalenessUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(cls.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        
        # Create all tables
        db_tables.create_all_tables(db.get_engine())

    @classmethod
    def tearDownClass(cls):
        cls.db_dir.cleanup()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        self.temp_dir.cleanup()

    def test_variable_updates(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)

        proj = PROJECT_FACTORIES['sprake']()

        projid = proj.id

        r0 = proj.revision
        self.assertEqual(r0, 0)
        
        proj_provider.add_component(proj)

        self.assertFalse(proj.modified)
        self.assertFalse(proj.chain_modified)

        proj_r = proj_provider.get_project(projid)
        self.assertEqual(proj_r.revision, r0)

        self.assertEqual(proj_r.revision, proj.revision)
        self.assertEqual(len(proj_r._children), len(proj._children))
        self.assertEqual(proj_r.metamodels.revision, proj.metamodels.revision) # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(len(proj_r.metamodels._children), len(proj.metamodels._children)) # pyright: ignore[reportAttributeAccessIssue]
        self.assertEqual(proj_r.metamodels[0].revision, proj.metamodels[0].revision)
        self.assertEqual(len(proj_r.metamodels[0]._children), len(proj.metamodels[0]._children))

        self.assertEqual(len(proj_r.metamodels[0].variables), len(proj.metamodels[0].variables))
        self.assertEqual(proj_r.metamodels[0].variables.revision, proj.metamodels[0].variables.revision)

        for varid in proj_r.metamodels[0].variables.keys():
            self.assertEqual(proj_r.metamodels[0].variables[varid].revision, proj.metamodels[0].variables[varid].revision)

        self.assertEqual(proj_r.metamodels[0].model.revision, proj.metamodels[0].model.revision)
        self.assertEqual(len(proj_r.metamodels[0].model._children), len(proj.metamodels[0].model._children))
        
        self.assertEqual(proj_r.metamodels[0].finance.revision, proj.metamodels[0].finance.revision)
        self.assertEqual(len(proj_r.metamodels[0].finance._children), len(proj.metamodels[0].finance._children))

        self.assertEqual(proj_r.metamodels[0].model.grid.revision, proj.metamodels[0].model.grid.revision)
        self.assertEqual(proj_r.metamodels[0].model.generation.revision, proj.metamodels[0].model.generation.revision)
        self.assertEqual(proj_r.metamodels[0].model.consumption_storage.revision, proj.metamodels[0].model.consumption_storage.revision)

        # Does a variable modification chain through?
        mm_r = proj_r.metamodels[0]
        var0 = mm_r.variables['gen_input.wind_capacity.0']

        mm_r0 = mm_r.revision
        var0_r0 = var0.revision
        self.assertFalse(var0.modified)

        par0 = var0.raw_parameters
        var0.set_single_parameter(par0[0] * 2, 0, 0) # type: ignore
        self.assertTrue(var0.modified)
        self.assertEqual(var0.revision, var0_r0 + 1)

        # Metamodel will show modification within its variables OrderedDict,
        # The metamodel config should be a subscriber and so be modified.
        self.assertTrue(mm_r.chain_modified)
        self.assertTrue(mm_r.modified)
        self.assertEqual(mm_r.revision, mm_r0 + 1)

        # Project should also be modified due to modification of the metamodel
        self.assertTrue(proj_r.chain_modified)
        self.assertTrue(proj_r.modified)
        self.assertEqual(proj_r.revision, r0 + 1)      
