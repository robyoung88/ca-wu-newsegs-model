"""
Unit tests for newsegsmodelapp/backend database
"""
import os
from pathlib import Path
import pickle
import tempfile
from typing import cast
import unittest

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import inspect

from newsegsmodelapp.backend.db import db_tables
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel

from config import settings
from newsegsmodelapp import registers
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsComponentProvider, FromDatabaseNewsegsEMProvider, FromDatabaseNewsegsFMProvider, FromDatabaseNewsegsMetamodelProvider, FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.backend.db.db_variable_provider import FromDatabaseVariableProvider
from newsegsmodelframework.core.newsegscomponent import TableConfigNewsegsComponent
from newsegsmodelframework.newsegsvariable.variable import ScalarVariable
from newsegsmodelframework.newsegsvariable.variableprovider import InMemoryVariableProvider, RecoverableInMemoryVariableProvider
from test.unit_tests import variable_helpers

SEED_TABLES = False

class TestDatabaseStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        #os.environ['DYNACONF_DB_PATH'] = ':memory:'
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        metadata = tbls.metadata
        sorted_tables = metadata.sorted_tables

        seed_table_file = os.path.join(
            settings.get('SprakeDataLoc', ''),
            'test_app_database_tables.xlsx'
        )

        # Create all tables
        db_tables.create_all_tables(db.get_engine())
        #metadata.create_all(db.get_engine())

        if SEED_TABLES:
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

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        self.temp_dir.cleanup()

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

        proj_provider.add_component(proj)
        mm2 = proj_provider.metamodel_provider.duplicate_component(proj.metamodels[0])
        mm2.name = 'Second mm'
        mm2.revision += 1
        proj.metamodels.append(mm2) # pyright: ignore[reportArgumentType, reportAttributeAccessIssue]
        proj.revision += 1
        proj_provider.upsert_component(proj)
        

        project_id = proj.id

        snapshot_id = db_snapshot.generic_snapshot_entity(
            db.get_engine(),
            tbls.metadata,
            'projects',
            project_id,
            'First snapshot'
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

            result = conn.execute(
                tbls.snapshot_component_configs.select()
                .where(tbls.snapshot_component_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 19)

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
            db.get_engine(),
            tbls.metadata,
            snapshot_id
        )

        new_project_id = list(new_ids['projects'].values())[0]

        with db.get_engine().connect() as conn:
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
        for var in one_of_each.values():
            self.assertTrue(var.modified)

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
                dv1 = v1.deterministic_value
                prm = list(v1.raw_parameters)
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
                self.assertTrue(v1.modified)
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
        fnc2 = finance_provider.get_component(fnc1.id)
        fnc2.model = mdl2

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

    def test_modification_triggers(self):
        import time
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)

        #proj_list = proj_provider.list_projects()
        
        proj = PROJECT_FACTORIES['sprake']()
        proj_provider.add_component(proj)
        with db.get_engine().connect() as conn:

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
        with db.get_engine().connect() as conn:
        
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
        self.assertNotEqual(mm1.id, mm_dup.id)
        # Variables, however, should be maintained on a metamodel duplication
        self.assertEqual(
            list(mm1.variables.values())[0].id,
            list(mm_copy.variables.values())[0].id
        )

        # Check if the metamodel has NOT been connected to the project
        proj = proj_provider.get_project(proj.id)
        n_proj_metamodels_post_dup = len(proj.metamodels)
        self.assertEqual(n_proj_metamodels_post_dup, n_proj_metamodels)

        proj_dup = proj_provider.duplicate_component(proj.id)
        self.assertNotEqual(proj.id, proj_dup.id)
        self.assertNotEqual(proj.metamodels[0].id, proj_dup.metamodels[0].id)
        # Critically, the variables should have been duplicated and are nonequal
        self.assertNotEqual(
            list(proj.metamodels[0].variables.values())[0].id,
            list(proj_dup.metamodels[0].variables.values())[0].id
        )

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

        engine = db.get_engine()

        proj = PROJECT_FACTORIES['sprake']()
        proj_provider.add_component(proj)

        request_creator = registers.RUN_REQUEST_REGISTER.get('deterministic_run_metamodel')
        self.assertIsNotNone(request_creator)
        request = request_creator(proj.id, proj_provider) # pyright: ignore[reportOptionalCall]

        run_id = generate_claim_ticket(engine, request)

        request.run_id = run_id

        runner = registers.RUN_PROCEDURE_REGISTER.get(request.request_type)
        self.assertIsNotNone(runner)

        def update_progress(step, total, message):
            return

        def check_cancel_status():
            return False

        is_ok = runner(request, proj_provider, result_provider, run_id, update_progress, check_cancel_status) # pyright: ignore[reportOptionalCall]

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
            'postproc_model_grid',
            'postproc_model_generation',
            'postproc_model_consumption',
            'postproc_model_storage',
            'postproc_model_net',
            'postproc_finance_benefits',
            'postproc_finance_costs',
            'postproc_finance_value'
        ]

        postactions_from_reg = registers.POST_ACTION_REGISTER.get(request.request_type)
        self.assertIsNotNone(postactions_from_reg)
        self.assertTrue(all(x[0] in postprocess_list for x in postactions_from_reg.postprocess_procedures)) # pyright: ignore[reportOptionalMemberAccess]
        self.assertTrue(all(x in [y[0] for y in postactions_from_reg.postprocess_procedures] for x in postprocess_list)) # pyright: ignore[reportOptionalMemberAccess]

        table_draws_done = set()

        for process_name in postprocess_list:
            pp_req_provider = registers.POSTPROCESS_REQUEST_REGISTER.get(process_name)
            self.assertIsNotNone(pp_req_provider, msg = f'Postprocess request generator not found for {process_name}')
            pp_req = pp_req_provider(request) # pyright: ignore[reportOptionalCall]
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
                    td_req_func = registers.TABLE_DRAW_REQUEST_REGISTER.get(td_artist_name[0])
                    if td_req_func:
                        td_req = td_req_func(pp_req)
                    else:
                        td_req = pp_req

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
                        self.assertEqual(is_ok, 'ok')
                    table_draws_done.add(td_artist_name[0])
        
        result_getters = [
            (x, proj.metamodels[0].model.table_config if 'model' in x else proj.metamodels[0].finance.table_config) for x in postprocess_list
        ]

        for rg in result_getters:
            if rg[0] == 'postproc_model_grid':
                # No result expected
                continue
            res, rev = result_provider.get_result(rg[0], rg[1], True)
            self.assertIsNotNone(res, msg = f'No result for {rg[0]}, {rg[1]}')

        table_section_list = [
            'grid',
            'generation',
            'consumption',
            'storage',
            'net',
            'finance'
        ]
        self.assertTrue(all(x in table_section_list for x in table_draws_done))
        self.assertTrue(all(x in table_draws_done for x in table_section_list))

        project_tables = [
            'table_model_generation_wind',
            'table_model_generation_pv',
            'table_model_generation_combined',
            'table_model_consumption',
            'table_model_consumption_seasonal',
            'table_model_storage',
            'table_model_net_energy',
            'table_model_net_energy_seasonal',
            'table_finance_so_benefits',
            'table_finance_so_costs',
            'table_finance_so_value',
        ]
        for tbl in project_tables:
            res, rev = result_provider.get_result(tbl, proj.table_config, False)

            self.assertIsNotNone(res, msg = f'No table for {tbl}')