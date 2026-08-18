"""
Unit tests for newsegsmodelapp/backend database
"""
import os
import unittest

import pandas as pd
from sqlalchemy import inspect

from config import settings

class TestDatabaseStart(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ['DYNACONF_DB_PATH'] = ':memory:'
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend import db_tables as tbls
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
        sheet_name_map = {name.lower(): name for name in sheet_names}

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
                        df.to_sql(table.name, conn, if_exists='append', index=False)
            
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
            'module_configs',
            'snapshot_module_configs',
            'module_variables',
            'snapshot_module_variables',
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
        from newsegsmodelapp.backend import db_tables as tbls
        from newsegsmodelapp.backend import db_snapshot

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
                tbls.snapshot_module_configs.select()
                .where(tbls.snapshot_module_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 10)

            result = conn.execute(
                tbls.snapshot_variable_configs.select()
                .where(tbls.snapshot_variable_configs.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 8)

            result = conn.execute(
                tbls.snapshot_module_variables.select()
                .where(tbls.snapshot_module_variables.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 8)

            result = conn.execute(
                tbls.snapshot_results.select()
                .where(tbls.snapshot_results.c.snapshot_id == snapshot_id)
            )
            self.assertEqual(len(result.fetchall()), 4)


        