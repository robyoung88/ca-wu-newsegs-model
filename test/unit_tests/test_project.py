import copy
import unittest

from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES


class TestNewsegsProject(unittest.TestCase):

    def test_metamodel_duplication(self):
        proj = PROJECT_FACTORIES['sprake']()

        proj.chain_syncronise()
        # Test that copy works correctly externally
        mm_0 = proj.metamodels[0]

        mm_1 = copy.deepcopy(mm_0)

        # Check that the revisions are equal
        self.assertEqual(mm_1.revision, mm_0.revision, 'Immediately after copy')

        self.assertFalse(mm_1 is mm_0)
        self.assertFalse(mm_1.table_config is mm_0.table_config)
        self.assertFalse(mm_1.model is mm_0.model)
        self.assertFalse(mm_1.finance is mm_0.finance)
        for varid, var in mm_0.variables.items():
            self.assertIs(mm_1.variables[varid], var)
        
        # Check that the ids need anonymising
        self.assertEqual(mm_1.id, mm_0.id)
        self.assertEqual(mm_1.table_config.id, mm_0.table_config.id)
        self.assertEqual(mm_1.model.id, mm_0.model.id)
        self.assertEqual(mm_1.finance.id, mm_0.finance.id)
        for varid, var in mm_0.variables.items():
            self.assertEqual(mm_1.variables[varid].id, var.id)

        # Anonymise the ids
        mm_1.anonymise_ids()
        self.assertNotEqual(mm_1.id, mm_0.id)
        self.assertNotEqual(mm_1.table_config.id, mm_0.table_config.id)
        self.assertNotEqual(mm_1.model.id, mm_0.model.id)
        self.assertNotEqual(mm_1.finance.id, mm_0.finance.id)
        # The variables should be untouched
        for varid, var in mm_0.variables.items():
            self.assertEqual(mm_1.variables[varid].id, var.id)

        # Check that the revisions are equal
        self.assertEqual(mm_1.revision, mm_0.revision)

        # Replace one variable before attaching mm_1 to project
        varid0 = next(iter(mm_1.variables))
        vx = copy.deepcopy(mm_1.variables[varid0])
        vx.anonymise_ids()
        mm_1.variables[varid0] = vx

        n_vars_pre = len(proj._variables_by_uid)
        proj.metamodels.append(mm_1) # pyright: ignore[reportAttributeAccessIssue]
        n_vars_post = len(proj._variables_by_uid)
        self.assertEqual(n_vars_post, n_vars_pre + 1)

        # Test that revisioning works correctly
        self.assertTrue(proj.modified)
        self.assertFalse(mm_0.modified)
        self.assertTrue(mm_1.modified)
        proj.chain_syncronise()

        p0 = vx.raw_parameters
        vx.set_single_parameter(p0[0]+10, 0, 0) # type: ignore
        self.assertTrue(proj.modified)
        self.assertFalse(mm_0.modified)
        self.assertTrue(mm_1.modified)
        proj.chain_syncronise()

        it_ = iter(mm_1.variables)
        _ = next(it_)
        varid1 = next(it_)
        vy = mm_1.variables[varid1]
        
        p1 = vy.raw_parameters
        vy.set_single_parameter(p1[0]+10, 0, 0) # type: ignore
        self.assertTrue(proj.modified)
        self.assertTrue(mm_0.modified)
        self.assertTrue(mm_1.modified)
        proj.chain_syncronise()

        # Check that replacement of a variable bubbles up to project
        n_vars_pre = len(proj._variables_by_uid)
        vid_to_be_lost = mm_0.variables[varid0].id
        vz = copy.deepcopy(vx)
        vz.anonymise_ids()
        vid_to_be_gained = vz.id
        mm_0.variables[varid0] = vz
        self.assertEqual(len(proj._variables_by_uid), n_vars_pre)
        self.assertIn(vid_to_be_gained, set(proj._variables_by_uid.keys()))
        self.assertNotIn(vid_to_be_lost, set(proj._variables_by_uid.keys()))

        # Check that models are attached correctly
        proj.chain_syncronise()
        mdl_r0 = mm_1.revision
        mm_1.sync_model_with_changed_variables_deterministic()

        self.assertTrue(mm_1.model.chain_modified)
        self.assertTrue(mm_1.model.modified)
        self.assertTrue(mm_1.chain_modified)
        self.assertTrue(mm_1.modified)
        self.assertTrue(proj.chain_modified)
        self.assertTrue(proj.modified)
        self.assertFalse(mm_0.chain_modified)
