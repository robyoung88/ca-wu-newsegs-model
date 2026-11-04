"""
Unit tests for newsegsmodelapp/backend database
"""
import copy
import os
from pathlib import Path
import pickle
import tempfile
from typing import cast
import unittest

import sqlalchemy as sa
from sqlalchemy import inspect

from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db.db_request_handler import FromDatabaseRequestHandler
from newsegsmodelframework.newsegsfinance.newsegsfinance import NewsegsFinance
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

from config import settings
from newsegsmodelapp import registers
from newsegsmodelapp.backend.db.db_component_provider import CachedFromDatabaseNewsegsProjectProvider, FromDatabaseNewsegsComponentProvider, FromDatabaseNewsegsEMProvider, FromDatabaseNewsegsFMProvider, FromDatabaseNewsegsMetamodelProvider, FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db.db_result_provider import CachedFromDatabaseResultProvider, FromDatabaseResultProvider
from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelframework.core.newsegscomponent import TableConfigNewsegsComponent
from newsegsmodelframework.newsegsvariable.variable import ScalarVariable
from newsegsmodelframework.newsegsvariable.variableprovider import RecoverableInMemoryVariableProvider
from test.unit_tests import variable_helpers



class TestDatabaseStart(unittest.TestCase):
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

        for writer in (False, True):
            engine = db.get_engine(writer = writer, db_path = cls.db_path)
            engine.dispose()
        
        cls.db_dir.cleanup()

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            engine = db.get_engine(writer = writer)
            engine.dispose()

        self.temp_dir.cleanup()

    def component_ids_unequal(self, mdl1, mdl2):
        self.assertNotEqual(mdl1.id, mdl2.id)
        component_names_1 = mdl1.get_component_attributes()
        component_names_2 = mdl2.get_component_attributes()
        self.assertSetEqual(set(component_names_1), set(component_names_2))
        #self.assertEqual(len(component_names_1), 5)
        for cmpname in component_names_1:
            if hasattr(getattr(mdl1, cmpname), 'id'):
                comp1 = getattr(mdl1, cmpname)
                comp2 = getattr(mdl2, cmpname)
                self.assertIsNotNone(comp2, f'{cmpname}, {type(mdl1)}')
                self.assertNotEqual(getattr(mdl1, cmpname).id, getattr(mdl2, cmpname).id, cmpname)

    def metamodel_ids_unequal(self, mm1, mm2, include_variables = False):
        self.component_ids_unequal(mm1, mm2)
        #self.assertNotEqual(mm1.id, mm2.id)

        self.component_ids_unequal(mm1.model, mm2.model)
        self.component_ids_unequal(mm1.finance, mm2.finance)

        if include_variables:
            for nm, var1 in mm1.variables.items():
                var2 = mm2.variables[nm]
                self.assertNotEqual(var1.id, var2.id, nm)
        else:
            for nm, var1 in mm1.variables.items():
                var2 = mm2.variables[nm]
                self.assertEqual(var1.id, var2.id, nm)


    def test_tables_exist(self):
        from newsegsmodelapp.backend import db

        engine = db.get_engine()
        expected_tables = (
            'snapshots',
            'variable_configs',
            'snapshot_variable_configs',
            'component_configs',
            'snapshot_component_configs',
            'results',
            'snapshot_results',
            'em_configs',
            'snapshot_em_configs',
            'fm_configs',
            'snapshot_fm_configs',
            'metamodels',
            'snapshot_metamodels',
            'projects',
            'snapshot_projects',
            'project_metamodels',
            'snapshot_project_metamodels',
            'project_variables',
            'snapshot_project_variables',
            'metamodel_variables',
            'snapshot_metamodel_variables',
            'runs',
            'sessions',
        )
        
        # Get all table names from the database
        inspector = inspect(engine)
        actual_tables = set(inspector.get_table_names())
        
        # Assert that all expected tables are present
        for table_name in expected_tables:
            self.assertIn(
                table_name,
                actual_tables,
                f"Expected table '{table_name}' not found in database"
            )

    def test_snapshot_logic(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        from newsegsmodelapp.backend.db import db_snapshot

        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        proj = PROJECT_FACTORIES['sprake']()

        proj_2 = PROJECT_FACTORIES['sprake']()
        for varid in proj.metamodels[0].variables.keys():
            self.assertNotEqual(
                proj.metamodels[0].variables[varid].id,
                proj_2.metamodels[0].variables[varid].id
            )
        self.assertNotEqual(
            proj.metamodels[0].id,
            proj_2.metamodels[0].id
        )

        self.assertNotEqual(
            proj.metamodels[0].model.id,
            proj_2.metamodels[0].model.id
        )

        self.assertNotEqual(
            proj.metamodels[0].finance.id,
            proj_2.metamodels[0].finance.id
        )

        with read_transaction(db.get_engine())as conn:
            nrow_components_pre = conn.execute(
                sa.select(sa.func.count())
                .select_from(tbls.component_configs)
            ).scalar()
        
        proj_provider.upsert_component(proj)

        proj_provider.add_component(proj)
        mm2 = proj_provider.metamodel_provider.duplicate_component(proj.metamodels[0])
        mm2.name = 'Second mm'
        mm2.revision += 1
        proj.metamodels.append(mm2) # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        proj.revision += 1
        proj_provider.upsert_component(proj)        

        with read_transaction(db.get_engine())as conn:
            nrow_components_post = conn.execute(
                sa.select(sa.func.count())
                .select_from(tbls.component_configs)
            ).scalar()

        self.assertEqual(nrow_components_post - nrow_components_pre, 21)
        
        project_id = proj.id

        snapshot_id = db_snapshot.generic_snapshot_entity(
            db.get_engine(writer = True),
            tbls.metadata,
            'projects',
            project_id,
            'First snapshot'
        )

        # Check that the snapshot has been created
        with read_transaction(db.get_engine()) as conn:
           
            result = conn.execute(
                tbls.snapshot_projects.select()
                .where(tbls.snapshot_projects.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 1)

            result = conn.execute(
                tbls.snapshot_metamodels.select()
                .where(tbls.snapshot_metamodels.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 2)

            result = conn.execute(
                tbls.snapshot_project_metamodels.select()
                .where(tbls.snapshot_project_metamodels.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 2)

            result = conn.execute(
                tbls.snapshot_em_configs.select()
                .where(tbls.snapshot_em_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 2)

            result = conn.execute(
                tbls.snapshot_fm_configs.select()
                .where(tbls.snapshot_fm_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 2)

            mm1 = proj.metamodels[0]
            mm2 = proj.metamodels[1]
            self.assertEqual(len(mm1.get_component_attributes()), len(mm2.get_component_attributes()))
            self.assertEqual(len(mm1.get_component_attributes()), 5) # table_config + optim_config + model + finance + variable OrderedDict

            self.assertEqual(len(mm1.model.get_component_attributes()), len(mm2.model.get_component_attributes()))
            self.assertEqual(len(mm1.model.get_component_attributes()), 5) # model_data + table_config + grid + generation + consumption_storage

            self.assertEqual(len(mm1.finance.get_component_attributes()), len(mm2.finance.get_component_attributes()))
            self.assertEqual(len(mm1.finance.get_component_attributes()), 3) # finance_data + table_config + model

            self.assertEqual(len(proj.get_component_attributes()), 4) # table_config + dsa_config + psa_config + metamodels

            n_components = (
                5 * 2 # Modules in model
                + 2 * 2 # finance_data and table_config in finance
                + 2 * 2 # table_config and optim_config in metamodel
                + 3 # dsa_config, psa_config and table_config in finance
            )
            # Based on this, we expect 21 components
            result = conn.execute(
                tbls.snapshot_component_configs.select()
                .where(tbls.snapshot_component_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 21)

            result = conn.execute(
                tbls.snapshot_variable_configs.select()
                .where(tbls.snapshot_variable_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 26)

            result = conn.execute(
                tbls.snapshot_results.select()
                .where(tbls.snapshot_results.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 0)

        # Restore the snapshot
        new_ids = db_snapshot.generic_restore_snapshot(
            db.get_engine(writer = True),
            tbls.metadata,
            snapshot_id
        )

        new_project_id = list(new_ids['projects'].values())[0]

        with read_transaction(db.get_engine())as conn:
            r0 = conn.execute(
                tbls.projects.select()
                .where(tbls.projects.c.id == project_id)
            ).fetchall()
            r1 = conn.execute(
                tbls.projects.select()
                .where(tbls.projects.c.id == new_project_id)
            ).fetchall()
            for row0, row1 in zip(r0, r1):
                for colname in ('model_type', 'model_version', 'label'):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname])

            for module_name in ('table_config_id', 'dsa_component_config_id', 'psa_component_config_id'):
                col = tbls.projects.columns[module_name]
                r0 = conn.execute(
                    tbls.component_configs.select()
                    .where(
                        tbls.component_configs.c.id.in_(
                            sa.select(col)
                            .where(tbls.projects.c.id == project_id)
                        )
                    )
                ).fetchall()
                r1 = conn.execute(
                    tbls.component_configs.select()
                    .where(
                        tbls.component_configs.c.id.in_(
                            sa.select(col)
                            .where(tbls.projects.c.id == new_project_id)
                        )
                    )
                ).fetchall()
                for row0, row1 in zip(r0, r1):
                    for colname in ('component_type', 'component_class', 'component_version', 'payload', 'revision', 'last_result_id', 'label'):
                        self.assertEqual(row0._mapping[colname], row1._mapping[colname], f'{module_name}, {colname}')

            metamodel_id_subq_0 = (
                sa.select(
                    tbls.project_metamodels.c.metamodel_id,
                    tbls.project_metamodels.c.created_order,
                )
                .where(tbls.project_metamodels.c.project_id == project_id)
                .subquery()
            )

            metamodel_id_subq_1 = (
                sa.select(
                    tbls.project_metamodels.c.metamodel_id,
                    tbls.project_metamodels.c.created_order,
                )
                .where(tbls.project_metamodels.c.project_id == new_project_id)
                .subquery()
            )

            r0 = conn.execute(
                sa.select(tbls.metamodels)
                .join(
                    metamodel_id_subq_0,
                    tbls.metamodels.c.id == metamodel_id_subq_0.c.metamodel_id
                )
                .order_by(metamodel_id_subq_0.c.created_order)
            ).fetchall()
            r1 = conn.execute(
                sa.select(tbls.metamodels)
                .join(
                    metamodel_id_subq_1,
                    tbls.metamodels.c.id == metamodel_id_subq_1.c.metamodel_id
                )
                .order_by(metamodel_id_subq_1.c.created_order)
            ).fetchall()
            for row0, row1 in zip(r0, r1):
                for colname in ('label', 'lat', 'lon', 'n_units', 'revision',):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname], f'{colname} not equal')

            em_subq_0 = (
                sa.select(
                    tbls.metamodels.c.em_config_id,
                    metamodel_id_subq_0.c.created_order,
                )
                .join(
                    metamodel_id_subq_0,
                    tbls.metamodels.c.id == metamodel_id_subq_0.c.metamodel_id
                )
                .subquery()
            )
            em_subq_1 = (
                sa.select(
                    tbls.metamodels.c.em_config_id,
                    metamodel_id_subq_1.c.created_order,
                )
                .join(
                    metamodel_id_subq_1,
                    tbls.metamodels.c.id == metamodel_id_subq_1.c.metamodel_id
                )
                .subquery()
            )
            
            r0 = conn.execute(
                sa.select(tbls.em_configs)
                .join(
                    em_subq_0,
                    tbls.em_configs.c.id == em_subq_0.c.em_config_id
                )
                .order_by(em_subq_0.c.created_order)
            ).fetchall()
            r1 = conn.execute(
                sa.select(tbls.em_configs)
                .join(
                    em_subq_1,
                    tbls.em_configs.c.id == em_subq_1.c.em_config_id
                )
                .order_by(em_subq_1.c.created_order)
            ).fetchall()

            for row0, row1 in zip(r0, r1):
                for colname in ('label', 'model_class', 'model_version', 'revision', 'payload',):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname], f'{colname} not equal')

            fm_subq_0 = (
                sa.select(
                    tbls.metamodels.c.fm_config_id,
                    metamodel_id_subq_0.c.created_order,
                )
                .join(
                    metamodel_id_subq_0,
                    tbls.metamodels.c.id == metamodel_id_subq_0.c.metamodel_id
                )
                .subquery()
            )
            fm_subq_1 = (
                sa.select(
                    tbls.metamodels.c.fm_config_id,
                    metamodel_id_subq_1.c.created_order,
                )
                .join(
                    metamodel_id_subq_1,
                    tbls.metamodels.c.id == metamodel_id_subq_1.c.metamodel_id
                )
                .subquery()
            )

            r0 = conn.execute(
                sa.select(tbls.fm_configs)
                .join(
                    fm_subq_0,
                    tbls.fm_configs.c.id == fm_subq_0.c.fm_config_id
                )
                .order_by(fm_subq_0.c.created_order)
            ).fetchall()
            r1 = conn.execute(
                sa.select(tbls.fm_configs)
                .join(
                    fm_subq_1,
                    tbls.fm_configs.c.id == fm_subq_1.c.fm_config_id
                )
                .order_by(fm_subq_1.c.created_order)
            ).fetchall()

            for row0, row1 in zip(r0, r1):
                for colname in ('model_class', 'model_version', 'payload', 'revision', 'label'):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname])
        
    def test_db_variable_provider(self):
        from newsegsmodelapp.backend import db
        import numpy.testing as nptest
        one_of_each = variable_helpers.one_of_every_variable()

        for var in one_of_each.values():
            self.assertIsNotNone(var.deterministic_value)
        
        backend_var_provider = FromDatabaseVariableProvider(db.get_engine)
        frontend_var_provider = RecoverableInMemoryVariableProvider(list(one_of_each.values()))

        # Initial sync
        #for var in one_of_each.values():
        #    self.assertFalse(var.modified)

        backend_var_provider.upsert_variable(list(frontend_var_provider._variables_by_uid.values()))

        for var in one_of_each.values():
            self.assertFalse(var.modified)

        # Frontend recovery
        collapsed = pickle.dumps(frontend_var_provider)

        fvp2 = pickle.loads(collapsed)
        fvp2.reattach_variables(backend_var_provider)

        for var in one_of_each.values():
            id = var.id
            v1 = frontend_var_provider.get_variable(id)
            v2 = fvp2.get_variable(id)
            if isinstance(v1, ScalarVariable):
                self.assertEqual(v1.deterministic_value, v2.deterministic_value)
            else:
                nptest.assert_array_equal(
                    v1.deterministic_value, 
                    v2.deterministic_value
                )

        # Assert that because the backend has intervened, there is no sync
        # between variables in both frontends
        for var in one_of_each.values():
            id = var.id
            v1 = frontend_var_provider.get_variable(id)
            if isinstance(v1, ScalarVariable):
                dv1 = v1.deterministic_value
                prm = list(v1.raw_parameters)
                if isinstance(prm[0], str):
                    prm[0] = prm[0] + str(0.1)
                elif v1.distribution.distribution == 'binomial':
                    if v1.parameterisation_index == 0:
                        prm[1] = prm[1] + 5 # pyright: ignore[reportOperatorIssue]
                    else:
                        prm[0] = prm[0] + 1 # pyright: ignore[reportOperatorIssue]
                else:
                    prm[0] = prm[0] + 0.1 # pyright: ignore[reportOperatorIssue]
                v1.set_parameters(*prm)
                self.assertNotEqual(v1.deterministic_value, dv1, f'{v1.name}')
                self.assertTrue(v1.modified)
                v2 = fvp2.get_variable(id)
                self.assertNotEqual(v1.deterministic_value, v2.deterministic_value)
            else:
                # CAUTION! NP arrays are not tracked!
                dv1 = v1.deterministic_value
                prm = list(copy.copy(x) for x in v1.raw_parameters)
                if isinstance(prm[0][0], str): # pyright: ignore[reportIndexIssue]
                    prm[0][0] = prm[0][0] + str(0.1) # pyright: ignore[reportIndexIssue,reportOperatorIssue]
                elif v1.distribution.distribution == 'dirichlet':
                    if v1.parameterisation_index == 0:
                        prm[0][0] = prm[0][0] + 10 # pyright: ignore[reportIndexIssue,reportOperatorIssue]
                    else:
                        prm[0][0] = 0.75 # pyright: ignore[reportIndexIssue, reportOperatorIssue]
                        prm[0][1] = 0.25 # pyright: ignore[reportIndexIssue,reportOperatorIssue]
                else:
                    prm[0][0] = prm[0][0] + 0.1 # pyright: ignore[reportIndexIssue,reportOperatorIssue]
                v1.set_parameters(*prm)
                with self.assertRaises(AssertionError, msg=f'{v1.name}'):
                    nptest.assert_array_equal(v1.deterministic_value, dv1)
                self.assertTrue(v1.modified, var.distribution.distribution)
                v2 = fvp2.get_variable(id)
                with self.assertRaises(AssertionError):
                    nptest.assert_array_equal(
                        v1.deterministic_value,
                        v2.deterministic_value
                    )

        # Synchronise via backend
        backend_var_provider.upsert_variable(
            list(frontend_var_provider._variables_by_uid.values())
        )

        fvp2.reattach_variables(backend_var_provider)
        for var in one_of_each.values():
            id = var.id
            v1 = frontend_var_provider.get_variable(id)
            v2 = fvp2.get_variable(id)
            if isinstance(v1, ScalarVariable):
                self.assertEqual(v1.deterministic_value, v2.deterministic_value)
            else:
                nptest.assert_array_equal(
                    v1.deterministic_value, 
                    v2.deterministic_value
                )

    def test_db_lightweight_variable_provider(self):
        from newsegsmodelapp.backend import db
        one_of_each = variable_helpers.one_of_every_variable()

        for var in one_of_each.values():
            self.assertIsNotNone(var.deterministic_value)
        
        backend_var_provider = FromDatabaseVariableProvider(db.get_engine)
 
        backend_var_provider.upsert_variable(list(one_of_each.values()))

        for var in one_of_each.values():
            self.assertFalse(var.modified)

        varids = [x.id for x in one_of_each.values()]

        def full_recovery(varids):
            return backend_var_provider.get_variable(varids)

        def lightweight_recovery(varids):
            return backend_var_provider.get_lightweight_variable(varids)

        def full_lightweight_recovery(varids):
            return backend_var_provider.get_full_lightweight_variable(varids)

        vars = full_recovery(varids)
        self.assertEqual(len(vars), len(one_of_each))

        vars = lightweight_recovery(varids)
        self.assertEqual(len(vars), len(one_of_each))

        vars = full_lightweight_recovery(varids)
        self.assertEqual(len(vars), len(one_of_each))

        TEST_RELATIVE_TIME = False
        if TEST_RELATIVE_TIME:
            import timeit
            REPS = 100

            t_full = timeit.timeit(lambda: full_recovery(varids), number = REPS, globals = globals())

            t_light = timeit.timeit(lambda: lightweight_recovery(varids), number = REPS, globals = globals())

            t_full_light = timeit.timeit(lambda: full_lightweight_recovery(varids), number = REPS, globals = globals())

            print(t_full, t_full / t_full)

            print(t_light, t_light / t_full)

            print(t_full_light, t_full_light / t_full)

    def test_project_variable_syncronisation(self):
        import numpy.testing as nptest

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj = PROJECT_FACTORIES['sprake']()

        backend_var_provider = FromDatabaseVariableProvider(db.get_engine)

        mm1 = proj.metamodels[0]

        mm2 = proj.duplicate_metamodel(mm1.id)

        self.assertEqual(
            list(mm1.variables.values())[0].deterministic_value,
            list(mm2.variables.values())[0].deterministic_value
        )

        mm1.variables['gen_input.wind_capacity.0'].set_single_parameter(999, 0)
        self.assertEqual(
            mm1.variables['gen_input.wind_capacity.0'].parameters[0],
            mm2.variables['gen_input.wind_capacity.0'].parameters[0],
        )

        # Change one variable source
        mm2.variables['gen_input.pv_capacity.0'] = proj.duplicate_variable(mm2.variables['gen_input.pv_capacity.0'].id)
        self.assertEqual(
            mm1.variables['gen_input.pv_capacity.0'].parameters[0],
            mm2.variables['gen_input.pv_capacity.0'].parameters[0],
        )
        mm2.variables['gen_input.pv_capacity.0'].set_single_parameter(555, 0)
        self.assertNotEqual(
            mm1.variables['gen_input.pv_capacity.0'].parameters[0],
            mm2.variables['gen_input.pv_capacity.0'].parameters[0],
        )

        # Save out variables
        proj.variable_to_store(
            backend_var_provider,
            (x.id for x in mm1.variables.values()), # pyright: ignore[reportArgumentType]
        )

        # Test reconstruction - deliberately recover from the wrong one so we check the variable sync
        mm3 = proj.duplicate_metamodel(mm2.id)
        mm3.variables.clear()
        mm3._variable_ids = mm1.variable_ids
        mm3.reattach_variables(backend_var_provider)

        mm1.sync_model_with_changed_variables_deterministic()
        mm2.sync_model_with_changed_variables_deterministic()
        mm3.sync_model_with_changed_variables_deterministic()
        mm1.model.run()
        mm2.model.run()
        mm3.model.run()

        nptest.assert_array_equal(
            mm1.model.get_generation_result().meters,
            mm3.model.get_generation_result().meters
        )

        with self.assertRaises(AssertionError):
            nptest.assert_array_equal(
                mm1.model.get_generation_result().meters,
                mm2.model.get_generation_result().meters
            )

    def test_component_provider(self):
        from newsegsmodelapp.backend import db

        component_provider = FromDatabaseNewsegsComponentProvider(db.get_engine)

        comp1 = TableConfigNewsegsComponent()

        comp1.name = 'My Table'

        component_provider.add_component(comp1)

        comp2 = component_provider.get_component(comp1.id)

        self.assertEqual(
            comp1.name,
            comp2.name
        )

    def test_model_provider(self):
        import numpy.testing as nptest
        
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        model_provider = FromDatabaseNewsegsEMProvider(db.get_engine)

        proj = PROJECT_FACTORIES['sprake']()

        mm1 = proj.metamodels[0]
        mdl1 = mm1.model

        model_provider.add_component(mdl1)

        mdl2 = model_provider.get_component(mdl1.id)

        mdl1.run()
        mdl2.run()
        nptest.assert_array_equal(
            mdl1.get_generation_result().meters,
            mdl2.get_generation_result().meters
        )

        nptest.assert_array_equal(
            mdl1.get_consumption_storage_result().meters,
            mdl2.get_consumption_storage_result().meters
        )

    def test_finance_provider(self):
        import numpy.testing as nptest

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        model_provider = FromDatabaseNewsegsEMProvider(db.get_engine)
        finance_provider = FromDatabaseNewsegsFMProvider(db.get_engine)

        proj = PROJECT_FACTORIES['sprake']()
        
        mm1 = proj.metamodels[0]
        mdl1 = mm1.model
        fnc1 = mm1.finance
        fnc1.cost_discount_rate = 0.1

        model_provider.add_component(mdl1)
        finance_provider.add_component(fnc1)

        mdl2 = model_provider.get_component(mdl1.id)
        fnc2 = cast(NewsegsFinance, finance_provider.get_component(fnc1.id))
        fnc2.model = mdl2

        self.assertEqual(fnc1.cost_discount_rate, fnc2.cost_discount_rate)

        mdl1.run()
        mdl2.run()
        nptest.assert_array_equal(
            fnc1.get_costs_series_discounted(),
            fnc2.get_costs_series_discounted()
        )

    def test_metamodel_provider(self):
        import numpy.testing as nptest

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        mm_provider = FromDatabaseNewsegsMetamodelProvider(db.get_engine)

        proj = PROJECT_FACTORIES['sprake']()

        mm1 = proj.metamodels[0]
        mm1.model.generation.wind_capacity = 0.1
        mm1.finance.resident_var_per_unit = 0.1

        mm_provider.add_component(mm1)

        mm2 = mm_provider.get_component(mm1.id)
        mm1.model.run()
        mm2.model.run()
        nptest.assert_array_equal(
            mm1.finance.get_costs_series_discounted(),
            mm2.finance.get_costs_series_discounted()
        )

    def test_project_provider(self):
        import numpy.testing as nptest
        
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)

        #proj_list = proj_provider.list_projects()
        
        proj = PROJECT_FACTORIES['sprake']()

        mm1 = proj.metamodels[0]
        mm1.model.generation.wind_capacity = 0.1
        mm1.finance.resident_var_per_unit = 0.1

        proj_provider.add_component(proj)

        proj2 = proj_provider.get_project(proj.id)

        proj.metamodels[0].model.run()
        proj2.metamodels[0].model.run()
        mm1 = proj.metamodels[0]
        mm2 = proj2.metamodels[0]

        nptest.assert_array_equal(
            mm1.finance.get_costs_series_discounted(),
            mm2.finance.get_costs_series_discounted()
        )

    def test_lightweight_provider(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
        
        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        proj = PROJECT_FACTORIES['sprake']()

        proj_provider.add_component(proj)

        proj2 = proj_provider.get_project(proj.id)
        lproj2 = proj_provider.get_lightweight_project(proj.id)

        self.assertEqual(proj2.id, lproj2.id)
        self.assertEqual(proj2.revision, lproj2.revision)
        self.assertEqual(proj2.metamodels[0].id, lproj2.metamodels[0].id)
        self.assertEqual(proj2.metamodels[0].revision, lproj2.metamodels[0].revision)
        self.assertEqual(proj2.metamodels[0].model.id, lproj2.metamodels[0].model.id)
        self.assertEqual(proj2.metamodels[0].model.revision, lproj2.metamodels[0].model.revision)
        self.assertEqual(proj2.metamodels[0].model.grid.id, lproj2.metamodels[0].model.grid.id)
        self.assertEqual(proj2.metamodels[0].model.grid.revision, lproj2.metamodels[0].model.grid.revision)
        self.assertEqual(proj2.metamodels[0].model.generation.id, lproj2.metamodels[0].model.generation.id)
        self.assertEqual(proj2.metamodels[0].model.generation.revision, lproj2.metamodels[0].model.generation.revision)
        self.assertEqual(proj2.metamodels[0].model.consumption_storage.id, lproj2.metamodels[0].model.consumption_storage.id)
        self.assertEqual(proj2.metamodels[0].model.consumption_storage.revision, lproj2.metamodels[0].model.consumption_storage.revision)
        self.assertEqual(proj2.metamodels[0].finance.id, lproj2.metamodels[0].finance.id)
        self.assertEqual(proj2.metamodels[0].finance.revision, lproj2.metamodels[0].finance.revision)

        self.assertEqual(len(proj._variables_by_uid), len(proj2._variables_by_uid))
        self.assertEqual(len(proj.metamodels[0].variables), len(proj2.metamodels[0].variables))
        self.assertEqual(len(lproj2.metamodels[0].variables), len(proj2.metamodels[0].variables))

        TEST_RELATIVE_TIME = True
        if TEST_RELATIVE_TIME:
            import timeit
            REPS = 10

            t_full = timeit.timeit(lambda: proj_provider.get_project(proj.id), number = REPS, globals = globals())
            
            t_light = timeit.timeit(lambda: proj_provider.get_lightweight_project(proj.id), number = REPS, globals = globals())

            print(t_full, t_full / t_full)
            
            print(t_light, t_light / t_full)

    # def test_metadata_revision(self):
    #     """Ensure revised metadata increment revisions appropriately and are maintained on reconstruction."""
    #     from newsegsmodelapp.backend import db
    #     from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
        
    #     proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
    #     proj = PROJECT_FACTORIES['sprake']()

    #     proj_provider.add_component(proj)

    #     lproj = proj_provider.get_lightweight_project(proj.id)

    #     mm_revision = lproj.metamodels[0].revision
    #     proj_provider
        
            

    def test_modification_triggers(self):
        import time
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)

        #proj_list = proj_provider.list_projects()
        
        proj = PROJECT_FACTORIES['sprake']()
        proj_provider.add_component(proj)
        with read_transaction(db.get_engine()) as conn:

            init_values = tuple(conn.execute(
                sa.select(
                    tbls.projects.c.revision,
                    tbls.projects.c.modified_at,
                    tbls.projects.c.modified_order
                )
                .where(
                    tbls.projects.c.id == proj.id
                )
            ).fetchone()) # pyright: ignore[reportArgumentType]

        time.sleep(2)
        proj.revision += 1
        proj_provider.upsert_component(proj)
        with read_transaction(db.get_engine()) as conn:
        
            updated_values = tuple(conn.execute(
                sa.select(
                    tbls.projects.c.revision,
                    tbls.projects.c.modified_at,
                    tbls.projects.c.modified_order
                )
                .where(
                    tbls.projects.c.id == proj.id
                )
            ).fetchone()) # pyright: ignore[reportArgumentType]

        self.assertNotEqual(init_values[0], updated_values[0], 'revision')
        self.assertNotEqual(init_values[1], updated_values[1], 'modified_at')
        self.assertNotEqual(init_values[2], updated_values[2], 'modified_order')

    def test_duplication_and_deletion(self):
        import numpy.testing as nptest
        
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)#
        mm_provider = proj_provider.metamodel_provider

        proj = PROJECT_FACTORIES['sprake']()

        mm1 = proj.metamodels[0]
        mm1.model.generation.wind_capacity = 0.1
        mm1.finance.resident_var_per_unit = 0.1

        proj_provider.add_component(proj)

        mm_copy = cast(NewsegsMetaModel, mm_provider.get_component(proj.metamodels[0].id))
        # Straight from the mm provider, there will be no variables attached
        mm_copy.reattach_variables(proj)
        self.assertEqual(mm1.id, mm_copy.id)
        self.assertEqual(
            list(mm1.variables.values())[0].id,
            list(mm_copy.variables.values())[0].id
        )

        n_proj_metamodels = len(proj.metamodels)

        mm_dup = mm_provider.duplicate_component(proj.metamodels[0].id)
        mm_dup.reattach_variables(proj)
        self.metamodel_ids_unequal(proj.metamodels[0], mm_dup, False)

        # Check if the metamodel has NOT been connected to the project
        proj = proj_provider.get_project(proj.id)
        n_proj_metamodels_post_dup = len(proj.metamodels)
        self.assertEqual(n_proj_metamodels_post_dup, n_proj_metamodels)

        proj_dup = proj_provider.duplicate_component(proj.id)
        self.assertNotEqual(proj.id, proj_dup.id)
        for mm1, mm2 in zip(proj.metamodels, proj_dup.metamodels):
            self.metamodel_ids_unequal(mm1, mm2, True)
       
        all_projects = proj_provider.list_projects()
        n_proj = len(all_projects)
        proj_provider.delete_component(proj_dup.id)

        all_projects_now = proj_provider.list_projects()
        n_proj_2 = len(all_projects_now)
        self.assertEqual(n_proj, n_proj_2 + 1)

    def test_process_and_results(self):
        import newsegsmodelapp.register_plugins
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        result_provider = FromDatabaseResultProvider(db.get_engine, self.test_dir)
        request_handler = FromDatabaseRequestHandler(db.get_engine)

        engine = db.get_engine(writer = True)

        proj = PROJECT_FACTORIES['sprake']()

        # Test variable syncronisation increments revisions
        mm = proj.metamodels[0]
        mm.sync_model_with_changed_variables_deterministic()
        proj.chain_syncronise()
        mm.variables['gen_input.pv_capacity.0'].set_parameters((201.1))
        mm.sync_model_with_changed_variables_deterministic()
        self.assertTrue(mm.model.generation.modified)
        self.assertTrue(mm.model.chain_modified)
        self.assertFalse(mm.model.consumption_storage.modified)

        proj_provider.add_component(proj)

        request = request_handler.add_request(
            'deterministic_run_metamodel',
            proj.id,
            proj_provider,
            'run'
        )

        run_id, exists = generate_claim_ticket(engine, request)

        request.run_id = run_id

        runner = registers.RUN_PROCEDURE_REGISTER.get(request.request_type)
        self.assertIsNotNone(runner)

        def update_progress(step, total, message):
            return

        def check_cancel_status():
            return False

        is_ok = runner(
            request, proj_provider, result_provider, 
            run_id, update_progress, check_cancel_status
        ) # pyright: ignore[reportOptionalCall]

        self.assertEqual(is_ok, 'ok')

        proj = proj_provider.get_project(proj.id)

        grid = proj.metamodels[0].model.grid
        grid_res, verstring = result_provider.get_result('deterministic_grid', grid, True)

        self.assertEqual(grid.revision, verstring)

        generation = proj.metamodels[0].model.generation
        generation_res, verstring = result_provider.get_result('deterministic_generation', generation, True)

        self.assertEqual(generation.revision, verstring)
        self.assertGreater(len(generation_res.meters_to_pandas()), 8760) # pyright: ignore[reportOptionalMemberAccess]

        postprocess_list = [
            'postproc_grid',
            'postproc_generation',
            'postproc_consumption',
            'postproc_storage',
            'postproc_net',
            'postproc_finance_benefits',
            'postproc_finance_costs',
            'postproc_finance_value'
        ]

        postactions_from_reg = registers.POST_ACTION_REGISTER.get(request.request_type)
        self.assertIsNotNone(postactions_from_reg)
        self.assertTrue(all(x[0] in postprocess_list for x in postactions_from_reg.postprocess_procedures)) # pyright: ignore[reportOptionalMemberAccess]
        self.assertTrue(all(x in [y[0] for y in postactions_from_reg.postprocess_procedures] for x in postprocess_list)) # pyright: ignore[reportOptionalMemberAccess]

        table_draws_done = set()
        finance_pp_counter = 0

        for process_name in postprocess_list:
            pp_req = request_handler.add_request(
                process_name,
                proj.id,
                proj_provider,
                'postprocess',
                triggering_request = request
            )
            self.assertIsInstance(pp_req, registers.PostprocessRequest)

            proc = registers.get_postprocess_procedure(process_name, pp_req)

            is_ok = proc(
                pp_req,
                proj_provider,
                result_provider,
                run_id,
                update_progress,
                check_cancel_status
            )
            

            self.assertEqual(is_ok, 'ok')

            postactions_from_reg = registers.POST_ACTION_REGISTER.get(pp_req.request_type)
            if postactions_from_reg is not None:
                for td_artist_name in postactions_from_reg.table_draw_artists:
                    td_req = request_handler.add_request(
                        td_artist_name[0],
                        proj.id,
                        proj_provider,
                        'tabledraw',
                        triggering_request= pp_req
                    )

                    td_artist = registers.get_table_draw(td_artist_name[0], pp_req)
                    if td_artist:
                        is_ok = td_artist(
                            td_req,
                            proj_provider,
                            result_provider,
                            run_id,
                            update_progress,
                            check_cancel_status,
                        )

                        if not td_artist_name[0] == 'table_finance':
                            self.assertEqual(is_ok, 'ok')
                        elif finance_pp_counter == 2 and td_artist_name[0] == 'table_finance':
                            self.assertEqual(is_ok, 'ok')
                        else:
                            finance_pp_counter += 1
                            self.assertEqual(is_ok, 'missing')
                    table_draws_done.add(td_artist_name[0])
        
        result_getters = [
            (x, proj.metamodels[0].finance.table_config if 'finance' in x else proj.metamodels[0].model.table_config) for x in postprocess_list
        ]

        for rg in result_getters:
            if rg[0] == 'postproc_grid':
                # No result expected
                continue
            res, rev = result_provider.get_result(rg[0], rg[1], True)
            self.assertIsNotNone(res, msg = f'No result for {rg[0]}, {rg[1]}')

        table_section_list = [
            'table_grid',
            'table_generation',
            'table_consumption',
            'table_storage',
            'table_net',
            'table_finance'
        ]
        self.assertTrue(all(x in table_section_list for x in table_draws_done))
        self.assertTrue(all(x in table_draws_done for x in table_section_list))

        project_tables = [
            'table_generation_wind_ann',
            'table_generation_pv_ann',
            'table_generation_combined_ann',
            'table_consumption_ann',
            'table_consumption_seasonal_ann',
            'table_storage_ann',
            'table_net_ann',
            'table_net_seasonal_ann',
            'table_finance_so_benefits_ann',
            'table_finance_so_costs_ann',
            'table_finance_so_value_ann',
        ]
        for tbl in project_tables:
            res, rev = result_provider.get_result(tbl, proj.table_config, False)

            self.assertIsNotNone(res, msg = f'No table for {tbl}')

    @staticmethod
    def get_project_revision_state(project):
        odict = {}
        odict.update(
            {
                'project': project.revision,
                'project.table_config': project.table_config.revision,
                'project.dsa_config': project.dsa_config.revision,
                'project.psa_config': project.psa_config.revision,
                'project.metamodels_container': project.metamodels.revision,
            }
        )
        for idx, mm in enumerate(project.metamodels):
            mdl = mm.model
            fnc = mm.finance
            mm_dict = {
                f'metamodel_{idx}': mm.revision,
                f'metamodel_{idx}.table_config': mm.table_config.revision,
                f'model_{idx}': mdl.revision,
                f'model_{idx}.table_config': mdl.table_config.revision,
                f'model_{idx}.grid': mdl.grid.revision,
                f'model_{idx}.generation': mdl.generation.revision,
                f'model_{idx}.consumption_storage': mdl.consumption_storage.revision,
                f'finance_{idx}': fnc.revision,
                f'finance_{idx}.table_config': fnc.table_config.revision,
            }
            odict.update(mm_dict)

        return odict

    @staticmethod
    def get_project_modification_state(project):
        odict = {}
        odict.update(
            {
                'project': project.modified,
                'project.table_config': project.table_config.modified,
                'project.dsa_config': project.dsa_config.modified,
                'project.psa_config': project.psa_config.modified,
                'project.metamodels_container': project.metamodels.modified,
            }
        )
        for idx, mm in enumerate(project.metamodels):
            mdl = mm.model
            fnc = mm.finance
            mm_dict = {
                f'metamodel_{idx}': mm.modified,
                f'metamodel_{idx}.table_config': mm.table_config.modified,
                f'model_{idx}': mdl.modified,
                f'model_{idx}.table_config': mdl.table_config.modified,
                f'model_{idx}.grid': mdl.grid.modified,
                f'model_{idx}.generation': mdl.generation.modified,
                f'model_{idx}.consumption_storage': mdl.consumption_storage.modified,
                f'finance_{idx}': fnc.modified,
                f'finance_{idx}.table_config': fnc.table_config.modified,
            }
            odict.update(mm_dict)

        return odict

    def test_process_revisions(self):
        """Ensure that revisions are being incremented correctly through a process"""
        import newsegsmodelapp.register_plugins
        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)
        result_provider = CachedFromDatabaseResultProvider(db.get_engine, self.test_dir)
        request_handler = FromDatabaseRequestHandler(db.get_engine)

        write_engine = db.get_engine(writer = True)

        proj = PROJECT_FACTORIES['sprake']()

        revisions = self.get_project_revision_state(proj)
        modification_state = self.get_project_modification_state(proj)
        for k, v in revisions.items():
            self.assertEqual(v, 0, f'{k} revision incorrect.')
        for k, v in modification_state.items():
            self.assertTrue(v, f'{k} modification status incorrect.')

        # Start from a fully synchronised system
        mm = proj.metamodels[0]
        mm.sync_model_with_changed_variables_deterministic()

        new_revisions = self.get_project_revision_state(proj)
        for k, v in new_revisions.items():
            self.assertEqual(v, 0, f'{k} revision incorrect.')
        
        proj_provider.add_component(proj)

        for i in range(2):
            if i == 1:
                # Alter some variables
                var1 = proj.metamodels[0].variables['gen_input.wind_capacity.0']
                var1.set_parameters((212.12,))

                var2 = proj.metamodels[0].variables['import_costs.grid_import_var_per_unit.0']
                var2.set_parameters(0.31, 0.1*0.31)

                proj_provider.variable_provider.upsert_variable(var1)
                proj_provider.variable_provider.upsert_variable(var2)
                # Need to manually invalidate the project cache - this could cause issues!
                proj_provider.invalidate_cache_for_component(proj.id)

            proj_recovered = proj_provider.get_project(proj.id)
            recovered_revisions = self.get_project_revision_state(proj_recovered)

            # Don't expect any modification of the model or finance until syncronisation
            for k, v in recovered_revisions.items():
                self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrect')

            request = request_handler.add_request(
                'deterministic_run_metamodel',
                proj.id,
                proj_provider,
                'run'
            )
            
            run_id, exists = generate_claim_ticket(write_engine, request)

            request.run_id = run_id
            
            runner = registers.RUN_PROCEDURE_REGISTER.get(request.request_type)

            def update_progress(step, total, message):
                return

            def check_cancel_status():
                return False

            # Initial run - deterministic single metamodel
            is_ok = runner(
                request, proj_provider, result_provider, 
                run_id, update_progress, check_cancel_status
            )

            self.assertEqual(is_ok, 'ok')

            # Recover project
            proj_recovered = proj_provider.get_project(proj.id)
            recovered_revisions = self.get_project_revision_state(proj_recovered)

            if i == 0:
                # Do not expect a revision in any component, as there are no valid results yet.
                for k, v in recovered_revisions.items():
                    self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrectly incremented')
            else:
                # Expect a revision in everything downstream of generation.
                for k, v in recovered_revisions.items():
                    if k in (
                        'project.table_config',
                        'metamodel_0.table_config',
                        'model_0',
                        'model_0.table_config',
                        'finance_0',
                        'finance_0.table_config',
                        #'model_0.grid',
                        'model_0.generation',
                        #'model_0.consumption_storage'
                    ):
                        self.assertEqual(v, new_revisions[k] + 1, f'{k} recovered revision not incremented')
                    else:
                        self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrectly incremented')

            postactions_from_reg = cast(
                registers.Postactions,
                registers.POST_ACTION_REGISTER.get(request.request_type)
            )

            finance_pp_counter = 0

            for pp_proc in postactions_from_reg.postprocess_procedures:
                procedure_name = pp_proc[0]
                new_req = request_handler.add_request(
                    procedure_name,
                    proj.id,
                    proj_provider,
                    'postprocess',
                    triggering_request = request
                )
                procedure = registers.get_postprocess_procedure(procedure_name, new_req)

                pp_run_id, exists = generate_claim_ticket(write_engine, new_req)
                new_req.run_id = pp_run_id

                is_ok = procedure(
                    new_req, proj_provider, result_provider,
                    pp_run_id, update_progress, check_cancel_status
                )
                self.assertEqual(is_ok, 'ok')

                # Recover project
                proj_recovered = proj_provider.get_project(proj.id)
                recovered_revisions = self.get_project_revision_state(proj_recovered)

                if i == 0:
                    # Again, expect no revisions
                    for k, v in recovered_revisions.items():
                        self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrectly incremented')
                else:
                    # Expect a revision in everything downstream of generation.
                    for k, v in recovered_revisions.items():
                        if k in (
                            'project.table_config',
                            'metamodel_0.table_config',
                            'model_0',
                            'model_0.table_config',
                            'finance_0',
                            'finance_0.table_config',
                            #'model_0.grid',
                            'model_0.generation',
                            #'model_0.consumption_storage'
                        ):
                            self.assertEqual(v, new_revisions[k] + 1, f'{k} recovered revision not incremented')
                        else:
                            self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrectly incremented')

                output_actions = cast(
                    registers.Postactions,
                    registers.POST_ACTION_REGISTER.get(new_req.request_type)
                )

                for output_proc in output_actions.table_draw_artists:
                    op_proc_name = output_proc[0]
                    op_req = request_handler.add_request(
                        op_proc_name,
                        proj.id,
                        proj_provider,
                        'tabledraw',
                        triggering_request= new_req
                    )

                    op_procedure = registers.get_table_draw(op_proc_name, op_req)

                    op_run_id, exists = generate_claim_ticket(write_engine, op_req)
                    op_req.run_id = op_run_id

                    is_ok = op_procedure(
                        op_req, proj_provider, result_provider,
                        run_id, update_progress, check_cancel_status
                    )
                    # Finance tables will not be immediately ok - will require all upstream postprocs to
                    # be run first
                    if not op_proc_name == 'table_finance':
                        self.assertEqual(is_ok, 'ok')
                    elif finance_pp_counter == 2 and op_proc_name == 'table_finance':
                        self.assertEqual(is_ok, 'ok')
                    else:
                        finance_pp_counter += 1
                        self.assertEqual(is_ok, 'missing')

                    # Recover project
                    proj_recovered = proj_provider.get_project(proj.id)
                    recovered_revisions = self.get_project_revision_state(proj_recovered)

                    if i == 0:
                        # Again, expect no revisions
                        for k, v in recovered_revisions.items():
                            self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrectly incremented')
                    else:
                        # Expect a revision in everything downstream of generation.
                        for k, v in recovered_revisions.items():
                            if k in (
                                'project.table_config',
                                'metamodel_0.table_config',
                                'model_0',
                                'model_0.table_config',
                                'finance_0',
                                'finance_0.table_config',
                                #'model_0.grid',
                                'model_0.generation',
                                #'model_0.consumption_storage'
                            ):
                                self.assertEqual(v, new_revisions[k] + 1, f'{k} recovered revision not incremented')
                            else:
                                self.assertEqual(v, new_revisions[k], f'{k} recovered revision incorrectly incremented')

            # Check that outputs are for the correct revision
            project_tables = [
                'table_generation_wind_ann',
                'table_generation_pv_ann',
                'table_generation_combined_ann',
                'table_consumption_ann',
                'table_consumption_seasonal_ann',
                'table_storage_ann',
                'table_net_ann',
                'table_net_seasonal_ann',
                'table_finance_so_benefits_ann',
                'table_finance_so_costs_ann',
                'table_finance_so_value_ann',
            ]
            current_proj = proj_provider.get_lightweight_project(proj.id)
            for tbl in project_tables:
                res, rev = result_provider.get_result(tbl, current_proj.table_config, False)
                self.assertIsNotNone(res, msg = f'No table for {tbl}')
