"""
Unit tests for newsegsmodelapp/backend database
"""
import os
from pathlib import Path
import pickle
import tempfile
import unittest
import uuid

import pandas as pd
import sqlalchemy as sa
from sqlalchemy import inspect

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

        proj2 = proj_provider.get_component(proj.id)

        proj.metamodels[0].model.run()
        proj2.metamodels[0].model.run()
        mm1 = proj.metamodels[0]
        mm2 = proj2.metamodels[0]

        nptest.assert_array_equal(
            mm1.finance.get_costs_series_discounted(),
            mm2.finance.get_costs_series_discounted()
        )

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
        request = request_creator(proj, db.get_engine()) # pyright: ignore[reportOptionalCall]

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

        proj = proj_provider.get_component(proj.id)

        grid = proj.metamodels[0].model.grid
        grid_res, verstring = result_provider.get_result('deterministic_grid', grid, True)

        self.assertEqual(grid.revision_string, verstring)

        generation = proj.metamodels[0].model.generation
        generation_res, verstring = result_provider.get_result('deterministic_generation', generation, True)

        self.assertEqual(generation.revision_string, verstring)
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

        for process_name in postprocess_list:
            proc = registers.get_postprocess_procedure(process_name, request)

            is_ok = proc(
                request,
                proj_provider,
                result_provider,
                run_id,
                update_progress,
                check_cancel_status
            )

            self.assertEqual(is_ok, 'ok')

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

        for table_section in table_section_list:
            proc = registers.get_table_draw(table_section, request)
            is_ok = proc(
                request,
                proj_provider,
                result_provider,
                run_id,
                update_progress,
                check_cancel_status,
                True
            )
            self.assertEqual(is_ok, 'ok')

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