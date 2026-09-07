"""
Unit tests for newsegsmodelapp/backend database
"""
import os
import pickle
import unittest
import uuid

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import inspect

from config import settings
from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelframework.newsegsvariable.variable import ScalarVariable
from newsegsmodelframework.newsegsvariable.variableprovider import InMemoryVariableProvider, RecoverableInMemoryVariableProvider
from test.unit_tests import variable_helpers

class TestDatabaseStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DYNACONF_DB_PATH'] = ':memory:'
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        metadata = tbls.metadata
        sorted_tables = metadata.sorted_tables

        seed_table_file = os.path.join(
            settings.get('SprakeDataLoc', ''),
            'test_app_database_tables.xlsx'
        )

        # Create all tables
        metadata.create_all(db.get_engine())

        # Load sheet names from Excel file
        xl_file = pd.ExcelFile(seed_table_file)
        sheet_names = xl_file.sheet_names

        # Create a mapping of sheet names (case-insensitive) for quick lookup
        sheet_name_map = {str(name).lower(): name for name in sheet_names}

        # Insert data from matching sheets into corresponding tables
        with db.get_engine().connect() as conn:
            for table in sorted_tables:
                table_name = table.name.lower()
                
                # Check if a matching sheet exists
                if table_name in sheet_name_map:
                    actual_sheet_name = sheet_name_map[table_name]
                    
                    # Read data from the matching sheet
                    df = pd.read_excel(seed_table_file, sheet_name=actual_sheet_name)
                    
                    # Insert the data into the table
                    if not df.empty:
                        # Convert appropriate columns to uuid
                        dtype_spec = {}
                        #for id_col in ['variable_config_id']:
                        #    if id_col in df.columns:
                        #        df[id_col] = df[id_col].apply(uuid.UUID) # type: ignore
                        #        dtype_spec[id_col] = sa.Uuid()
                        df.to_sql(table.name, conn, if_exists='append', index=False, dtype = dtype_spec)
            
            conn.commit()

    @classmethod
    def tearDownClass(cls):
        ...

    def test_tables_exist(self):
        from newsegsmodelapp.backend import db

        engine = db.get_engine()
        expected_tables = (
            'snapshots',
            'variable_configs',
            'snapshot_variable_configs',
            'component_configs',
            'snapshot_component_configs',
            'component_variables',
            'snapshot_component_variables',
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

        project_id = 1

        snapshot_id = db_snapshot.generic_snapshot_entity(
            db.get_engine(),
            tbls.metadata,
            'projects',
            project_id,
            'First snapshot',
            project_id
        )

        # Check that the snapshot has been created
        with db.get_engine().connect() as conn:
            result = conn.execute(
                tbls.snapshot_projects.select()
                .where(tbls.snapshot_projects.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 1)

            result = conn.execute(
                tbls.snapshot_metamodels.select()
                .where(tbls.snapshot_metamodels.c.metamodel_id == 1)
            )
            self.assertEqual(len(result.fetchall()), 1)

            result = conn.execute(
                tbls.snapshot_project_metamodels.select()
                .where(tbls.snapshot_project_metamodels.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 1)

            result = conn.execute(
                tbls.snapshot_em_configs.select()
                .where(tbls.snapshot_em_configs.c.em_config_id == 1)
            )
            self.assertEqual(len(result.fetchall()), 1)

            result = conn.execute(
                tbls.snapshot_fm_configs.select()
                .where(tbls.snapshot_fm_configs.c.fm_config_id == 1)
            )
            self.assertEqual(len(result.fetchall()), 1)

            result = conn.execute(
                tbls.snapshot_component_configs.select()
                .where(tbls.snapshot_component_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 10)

            result = conn.execute(
                tbls.snapshot_variable_configs.select()
                .where(tbls.snapshot_variable_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 8)

            result = conn.execute(
                tbls.snapshot_component_variables.select()
                .where(tbls.snapshot_component_variables.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 8)

            result = conn.execute(
                tbls.snapshot_results.select()
                .where(tbls.snapshot_results.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 4)

        # Restore the snapshot
        new_ids = db_snapshot.generic_restore_snapshot(
            db.get_engine(),
            tbls.metadata,
            snapshot_id
        )

        new_project_id = list(new_ids['projects'].values())[0]

        with db.get_engine().connect() as conn:
            r0 = conn.execute(
                tbls.projects.select()
                .where(tbls.projects.c.project_id == project_id)
            ).fetchall()
            r1 = conn.execute(
                tbls.projects.select()
                .where(tbls.projects.c.project_id == new_project_id)
            ).fetchall()
            for row0, row1 in zip(r0, r1):
                for colname in ('model_type', 'model_version', 'label'):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname])

            for module_name in ('table_config_id', 'dsa_component_config_id', 'psa_component_config_id'):
                col = tbls.projects.columns[module_name]
                r0 = conn.execute(
                    tbls.component_configs.select()
                    .where(
                        tbls.component_configs.c.component_config_id.in_(
                            sa.select(col)
                            .where(tbls.projects.c.project_id == project_id)
                        )
                    )
                ).fetchall()
                r1 = conn.execute(
                    tbls.component_configs.select()
                    .where(
                        tbls.component_configs.c.component_config_id.in_(
                            sa.select(col)
                            .where(tbls.projects.c.project_id == new_project_id)
                        )
                    )
                ).fetchall()
                for row0, row1 in zip(r0, r1):
                    for colname in ('component_type', 'component_class', 'component_version', 'config_payload', 'revision', 'last_result_id', 'label'):
                        self.assertEqual(row0._mapping[colname], row1._mapping[colname])

            metamodel_ids_0 = conn.execute(
                sa.select(tbls.project_metamodels.c.metamodel_id)
                .where(tbls.project_metamodels.c.project_id == project_id)
            ).fetchall()

            metamodel_ids_1 = conn.execute(
                sa.select(tbls.project_metamodels.c.metamodel_id)
                .where(tbls.project_metamodels.c.project_id == new_project_id)
            ).fetchall()

            r0 = conn.execute(
                tbls.metamodels.select()
                .where(tbls.metamodels.c.metamodel_id.in_([x[0] for x in metamodel_ids_0]))
            ).fetchall()
            r1 = conn.execute(
                tbls.metamodels.select()
                .where(tbls.metamodels.c.metamodel_id.in_([x[0] for x in metamodel_ids_1]))
            ).fetchall()
            for row0, row1 in zip(r0, r1):
                for colname in ('revision', 'label', 'lat', 'lon', 'n_units'):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname])

            em_config_ids_0 = [
                x[0] for x in 
                conn.execute(
                    sa.select(tbls.metamodels.c.em_config_id)
                    .where(tbls.metamodels.c.metamodel_id.in_([x[0] for x in metamodel_ids_0]))
                ).fetchall()
            ]
            em_config_ids_1 = [
                x[0] for x in 
                conn.execute(
                    sa.select(tbls.metamodels.c.em_config_id)
                    .where(tbls.metamodels.c.metamodel_id.in_([x[0] for x in metamodel_ids_1]))
                ).fetchall()
            ]

            r0 = conn.execute(
                tbls.em_configs.select()
                .where(tbls.em_configs.c.em_config_id.in_(em_config_ids_0))
            ).fetchall()
            r1 = conn.execute(
                tbls.em_configs.select()
                .where(tbls.em_configs.c.em_config_id.in_(em_config_ids_1))
            ).fetchall()
            for row0, row1 in zip(r0, r1):
                for colname in ('model_class', 'model_version', 'config_payload', 'revision', 'label'):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname])

            fm_config_ids_0 = [
                x[0] for x in 
                conn.execute(
                    sa.select(tbls.metamodels.c.fm_config_id)
                    .where(tbls.metamodels.c.metamodel_id.in_([x[0] for x in metamodel_ids_0]))
                ).fetchall()
            ]
            fm_config_ids_1 = [
                x[0] for x in 
                conn.execute(
                    sa.select(tbls.metamodels.c.fm_config_id)
                    .where(tbls.metamodels.c.metamodel_id.in_([x[0] for x in metamodel_ids_1]))
                ).fetchall()
            ]

            r0 = conn.execute(
                tbls.fm_configs.select()
                .where(tbls.fm_configs.c.fm_config_id.in_(fm_config_ids_0))
            ).fetchall()
            r1 = conn.execute(
                tbls.fm_configs.select()
                .where(tbls.fm_configs.c.fm_config_id.in_(fm_config_ids_1))
            ).fetchall()
            for row0, row1 in zip(r0, r1):
                for colname in ('model_class', 'model_version', 'config_payload', 'revision', 'label'):
                    self.assertEqual(row0._mapping[colname], row1._mapping[colname])

    def test_project_save(self):
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls

        from newsegsmodelframework.newsegsmodel import sprakemodel
        from newsegsmodelframework.newsegsfinance import sprakefinance
        import newsegsmodelframework.newsegsmetamodel as newsegsmetamodel
        import newsegsmodelframework.newsegsproject as newsegsproject

        mdl = sprakemodel.SprakeModel.from_none()
        fnc = sprakefinance.SprakeFinance.from_none()
        fnc.set_model(mdl)

        mm = newsegsmetamodel.NewsegsMetaModel(mdl, fnc)

        proj = newsegsproject.NewsegsProject([mm])

        with db.get_engine().begin() as conn:
            project_id = db.save_project(proj, conn)

        self.assertIsInstance(project_id, int)
        self.assertNotEqual(project_id, 1)

        with db.get_engine().connect() as conn:
            result = conn.execute(
                sa.select(tbls.projects.c.project_id)
                .where(tbls.projects.c.project_id == project_id)
            )
            self.assertEqual(len(result.fetchall()),1)


        # Also test load
        with db.get_engine().connect() as conn:
            proj_dup = db.load_project(project_id, conn)
            self.assertEqual(proj.id, proj_dup.id)
            self.assertEqual(proj.metamodels[0].id, proj_dup.metamodels[0].id)
            self.assertEqual(len(proj.metamodels[0].variables), len(proj_dup.metamodels[0].variables))
        
    def test_db_variable_provider(self):
        from newsegsmodelapp.backend import db
        import numpy.testing as nptest
        one_of_each = variable_helpers.one_of_every_variable()

        for var in one_of_each.values():
            self.assertIsNotNone(var.deterministic_value)
        
        backend_var_provider = FromDatabaseVariableProvider(db.get_engine)
        frontend_var_provider = RecoverableInMemoryVariableProvider(list(one_of_each.values()))

        # Initial sync
        for var in one_of_each.values():
            self.assertTrue(var.modified)

        backend_var_provider.synchronise_variable(list(frontend_var_provider._variables_by_uid.values()))

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
                        prm[1] = prm[1] + 5
                    else:
                        prm[0] = prm[0] + 1
                else:
                    prm[0] = prm[0] + 0.1
                v1.set_parameters(*prm)
                self.assertNotEqual(v1.deterministic_value, dv1, f'{v1.name}')
                self.assertTrue(v1.modified)
                v2 = fvp2.get_variable(id)
                self.assertNotEqual(v1.deterministic_value, v2.deterministic_value)
            else:
                dv1 = v1.deterministic_value
                prm = list(v1.raw_parameters)
                if isinstance(prm[0][0], str):
                    prm[0][0] = prm[0][0] + str(0.1)
                elif v1.distribution.distribution == 'dirichlet':
                    if v1.parameterisation_index == 0:
                        prm[0][0] = prm[0][0] + 10
                    else:
                        prm[0][0] = 0.75
                        prm[0][1] = 0.25
                else:
                    prm[0][0] = prm[0][0] + 0.1
                v1.set_parameters(*prm)
                with self.assertRaises(AssertionError, msg=f'{v1.name}'):
                    nptest.assert_array_equal(v1.deterministic_value, dv1)
                self.assertTrue(v1.modified)
                v2 = fvp2.get_variable(id)
                with self.assertRaises(AssertionError):
                    nptest.assert_array_equal(
                        v1.deterministic_value,
                        v2.deterministic_value
                    )

        # Synchronise via backend
        backend_var_provider.synchronise_variable(
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
