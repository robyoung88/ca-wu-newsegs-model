"""
Unit tests of the migration of the optimisation bounds from the project's components to its variables (9eeaede183f3)
"""
import datetime
import json
import os
from pathlib import Path
import tempfile
import unittest

from alembic import command
from alembic.config import Config as AlembicConfig
import sqlalchemy as sa

from config import settings

_PREVIOUS_REVISION = 'c7e2a9d41f05'
_REVISION = '9eeaede183f3'

_BOUNDS = {
    'optim_config': {
        'bounds': {
            'generation.wind.0': {'lower': 5, 'upper': 500, 'intervals': 15},
            'generation.solar.0': {'upper': 50},
        }
    }
}


class TestOptimConfigMigration(unittest.TestCase):

    def setUp(self):
        self.db_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.db_dir.name) / 'tempdb.db'
        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp import APP_ROOT
        from newsegsmodelapp.backend import db
        self.addCleanup(self._cleanup)
        self.alembic_cfg = AlembicConfig(APP_ROOT.parent / 'alembic.ini')
        command.upgrade(self.alembic_cfg, _PREVIOUS_REVISION)
        self.engine = db.get_engine(writer = True)

        self._insert_project()

    def _cleanup(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()
        self.db_dir.cleanup()

    def _insert_project(self):
        """A project as saved before the migration, with a snapshot of it."""
        meta = sa.MetaData()
        meta.reflect(self.engine)
        t = meta.tables
        table_payload = json.dumps({'class': 'TableConfigNewsegsComponent', **_BOUNDS})
        with self.engine.begin() as conn:
            conn.execute(t['component_configs'].insert(), [
                {'id': 'cmp-table', 'payload': table_payload},
                {'id': 'cmp-dsa', 'payload': json.dumps({'class': 'DSAComponent'})},
            ])
            conn.execute(t['projects'].insert().values(
                id = 'proj-1', model_type = 'x', model_version = '1',
                table_config_id = 'cmp-table', dsa_component_config_id = 'cmp-dsa',
            ))
            conn.execute(t['variable_configs'].insert(), [
                {'id': 'v-wind-a', 'varid': 'generation.wind.0', 'optim_min': '0'},
                {'id': 'v-wind-b', 'varid': 'generation.wind.0', 'optim_min': '0'},
                {'id': 'v-solar', 'varid': 'generation.solar.0', 'optim_min': '0'},
                {'id': 'v-other', 'varid': 'generation.other.0', 'optim_min': '0'},
            ])
            conn.execute(t['project_variables'].insert(), [
                {'project_id': 'proj-1', 'variable_config_id': x}
                for x in ('v-wind-a', 'v-wind-b', 'v-solar', 'v-other')
            ])

            snapshot_id = conn.execute(t['snapshots'].insert().values(
                project_id = 'proj-1', label = 'snap', created_at = datetime.datetime.now()
            )).inserted_primary_key[0]
            self.snapshot_id = snapshot_id
            conn.execute(t['snapshot_component_configs'].insert(), [
                {'snapshot_id': snapshot_id, 'id': 'cmp-table', 'payload': table_payload},
                {'snapshot_id': snapshot_id, 'id': 'cmp-dsa', 'payload': json.dumps({'class': 'DSAComponent'})},
            ])
            conn.execute(t['snapshot_projects'].insert().values(
                snapshot_id = snapshot_id, id = 'proj-1', model_type = 'x', model_version = '1',
                table_config_id = 'cmp-table', dsa_component_config_id = 'cmp-dsa',
            ))
            conn.execute(t['snapshot_variable_configs'].insert(), [
                {'snapshot_id': snapshot_id, 'id': 'v-wind-a', 'varid': 'generation.wind.0', 'optim_min': '0'},
                {'snapshot_id': snapshot_id, 'id': 'v-other', 'varid': 'generation.other.0', 'optim_min': '0'},
            ])
            conn.execute(t['snapshot_project_variables'].insert(), [
                {'snapshot_id': snapshot_id, 'project_id': 'proj-1', 'variable_config_id': x}
                for x in ('v-wind-a', 'v-other')
            ])

    def _variables(self, table_name: str) -> dict[str, tuple]:
        with self.engine.connect() as conn:
            rows = conn.execute(sa.text(
                f'SELECT id, optim_min, optim_max, optim_plot_intervals FROM {table_name}'
            )).fetchall()
        return {row.id: (row.optim_min, row.optim_max, row.optim_plot_intervals) for row in rows}

    def _payloads(self, table_name: str) -> list[dict]:
        with self.engine.connect() as conn:
            return [json.loads(x) for x in conn.execute(sa.text(f'SELECT payload FROM {table_name}')).scalars()]

    def test_upgrade_moves_bounds(self):
        command.upgrade(self.alembic_cfg, _REVISION)

        self.assertEqual(self._variables('variable_configs'), {
            # Every variable of the project with the varid is given its bounds
            'v-wind-a': ('5', '500', 15),
            'v-wind-b': ('5', '500', 15),
            # A bound that was not saved is unset, falling back to the input limits
            'v-solar': (None, '50', 10),
            'v-other': (None, None, 10),
        })
        self.assertEqual(self._variables('snapshot_variable_configs'), {
            'v-wind-a': ('5', '500', 15),
            'v-other': (None, None, 10),
        })
        for table_name in ('component_configs', 'snapshot_component_configs'):
            for payload in self._payloads(table_name):
                self.assertNotIn('optim_config', payload)

    def test_metamodel_columns_added(self):
        command.upgrade(self.alembic_cfg, _REVISION)
        inspector = sa.inspect(self.engine)
        for table_name in ('metamodels', 'snapshot_metamodels'):
            self.assertIn('optim_config_id', [x['name'] for x in inspector.get_columns(table_name)])
            fk_columns = [x['constrained_columns'] for x in inspector.get_foreign_keys(table_name)]
            self.assertTrue(any('optim_config_id' in x for x in fk_columns), table_name)

    def test_downgrade(self):
        command.upgrade(self.alembic_cfg, _REVISION)
        command.downgrade(self.alembic_cfg, _PREVIOUS_REVISION)
        inspector = sa.inspect(self.engine)
        for table_name in ('metamodels', 'snapshot_metamodels'):
            self.assertNotIn('optim_config_id', [x['name'] for x in inspector.get_columns(table_name)])
        for table_name in ('variable_configs', 'snapshot_variable_configs'):
            columns = [x['name'] for x in inspector.get_columns(table_name)]
            self.assertNotIn('optim_plot_intervals', columns)
            self.assertNotIn('component_version', columns)


if __name__ == '__main__':
    unittest.main()
