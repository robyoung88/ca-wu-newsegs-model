

import copy
import os
from pathlib import Path
import tempfile
import unittest

from config import settings

from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelframework.newsegsproject.newsegsproject import NewsegsProject

class TestStalenessUpdates(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(cls.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        
        # Create all tables
        db_tables.create_all_tables(db.get_engine(writer = True))

    @classmethod
    def tearDownClass(cls):
        from newsegsmodelapp.backend import db

        for writer in (True, False):
            engine = db.get_engine(writer = writer, db_path = cls.db_path)
            engine.dispose()

        cls.db_dir.cleanup()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        from newsegsmodelapp.backend import db
        for writer in (True, False):
            engine = db.get_engine(writer = writer)
            engine.dispose()
        self.temp_dir.cleanup()

    @staticmethod
    def get_revision_details(obj):
        return dict(
            revision = obj.revision,
            n_children = len(obj._children)
        )

    @staticmethod
    def get_project_revision_dict(proj: NewsegsProject):
        grd = TestStalenessUpdates.get_revision_details
        odict = {}
        odict['project'] = grd(proj)
        odict['project_table'] = grd(proj.table_config)
        #odict['metamodel_container'] = grd(proj.metamodels) # Don't care about the metamodel container, as it is never saved
        metamodel_revisions = []
        for mm in proj.metamodels:
            mm_dict = {}
            mm_dict['metamodel'] = grd(mm)
            mm_dict['metamodel_table'] = grd(mm.table_config)
            #mm_dict['variable_container'] = grd(mm.variables) # Also don't care about the variable container for same reason as mm container
            var_revisions = {}
            for varid, var in mm.variables.items():
                var_revisions[varid] = grd(var)
            mm_dict['variables'] = var_revisions

            mdl = mm.model
            mm_dict['model'] = grd(mdl)
            mm_dict['model_table'] = grd(mdl.table_config)
            mm_dict['model_grid'] = grd(mdl.grid)
            mm_dict['model_generation'] = grd(mdl.generation)
            mm_dict['model_consumption_storage'] = grd(mdl.consumption_storage)

            fnc = mm.finance
            mm_dict['finance'] = grd(fnc)
            mm_dict['finance_table'] = grd(fnc.table_config)

            metamodel_revisions.append(mm_dict)

        odict['dsa'] = grd(proj.dsa_config)
        odict['psa'] = grd(proj.psa_config)
        return odict


    def test_variable_updates(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)

        proj = PROJECT_FACTORIES['sprake']()

        projid = proj.id

        rev_0 = self.get_project_revision_dict(proj)

        r0 = proj.revision
        self.assertEqual(r0, 0)
        
        proj_provider.add_component(proj)

        self.assertFalse(proj.modified)
        self.assertFalse(proj.chain_modified)

        proj_r = proj_provider.get_project(projid)

        rev_postload = self.get_project_revision_dict(proj_r)
        # Cannot assert dictionaries equal as the psa configuration
        # statistics list will have become an observable list
        # through the serialisation process.
        test_dict_reference = copy.copy(rev_0)
        test_dict_new = copy.copy(rev_postload)
        del test_dict_reference['psa']['n_children']
        del test_dict_new['psa']['n_children']
        self.assertDictEqual(test_dict_new, test_dict_reference)

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

        # Check revisions survive an upload
        rev_preup = self.get_project_revision_dict(proj_r)
        # Copy isn't really doing anything as editing nested - should get rid
        test_dict_preup = copy.copy(rev_preup)
        del test_dict_preup['psa']['n_children']
        with self.assertRaises(AssertionError):
            self.assertDictEqual(test_dict_preup, test_dict_new)
        proj_provider.upsert_component(proj_r)
        proj_r2 = proj_provider.get_project(projid)
        rev_postload_modified = self.get_project_revision_dict(proj_r2)
        del rev_postload_modified['psa']['n_children']
        self.assertDictEqual(rev_postload_modified, test_dict_preup)

    def test_upsert_parsimony(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)

        proj = PROJECT_FACTORIES['sprake']()

        projid = proj.id
        
        proj_provider.add_component(proj)

