"""
Unit tests of the storage of the optimisation settings of variables and metamodels in the database
"""
import os
from pathlib import Path
import tempfile
from typing import cast
import unittest

import sqlalchemy as sa

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db import read_transaction, write_transaction
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelframework import register_plugins # noqa: F401 - registers the project factories
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.optim_component import OptimComponent
from newsegsmodelframework.newsegsvariable.variable import variable_uid

from config import settings


class TestOptimConfigStorage(unittest.TestCase):

    def setUp(self):
        self.db_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        self.engine = db.get_engine(writer = True)
        tbls.create_all_tables(self.engine)

        self.provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        self.proj = PROJECT_FACTORIES['sprake']()
        self.mm = cast(NewsegsMetaModel, self.proj.metamodels[0])
        self.optim_vars = [x for x in self.mm.variables.values() if x.optim_possible and x.optim_selectable]

        self.mm.optim_config.method = 'Powell'
        self.mm.optim_config.statistic = 'net_present_value_undiscounted'
        var = self.optim_vars[0]
        var.optim_min = 5.
        var.optim_max = 500.
        var.optim_plot_intervals = 15
        self.varid = variable_uid(var)

        self.provider.add_component(self.proj)

    def tearDown(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()
        self.db_dir.cleanup()

    def _check_settings(self, mm: NewsegsMetaModel):
        self.assertEqual(mm.optim_config.method, 'Powell')
        self.assertEqual(mm.optim_config.statistic, 'net_present_value_undiscounted')
        var = mm.variables[self.varid]
        self.assertEqual(var.get_optim_bounds(), (5., 500.))
        self.assertEqual(var.optim_plot_intervals, 15)

    def test_round_trip(self):
        proj = self.provider.get_project(self.proj.id)
        mm = cast(NewsegsMetaModel, proj.metamodels[0])
        self._check_settings(mm)
        self.assertEqual(mm.optim_config.id, self.mm.optim_config.id)

        # Unset bounds use the limits of the input field
        other = mm.variables[variable_uid(self.optim_vars[1])]
        self.assertEqual(other.get_optim_bounds(), (other.interface_min, other.interface_max))

    def test_variable_version_recorded(self):
        var_id = self.mm.variables[self.varid].id
        with read_transaction(self.engine) as conn:
            version = conn.execute(
                sa.select(tbls.variable_configs.c.component_version).where(tbls.variable_configs.c.id == var_id)
            ).scalar()
        self.assertEqual(version, self.mm.variables[self.varid].version)

    def test_lightweight(self):
        lproj = self.provider.get_lightweight_project(self.proj.id)
        lmm = lproj.metamodels[0]
        self.assertIsNotNone(lmm.optim_config)
        self.assertEqual(lmm.optim_config.id, self.mm.optim_config.id)

        var_id = lmm.variables[self.varid]
        lvar = self.provider.variable_provider.get_full_lightweight_variable(var_id)
        self.assertEqual(lvar.optim_min, 5.)
        self.assertEqual(lvar.optim_max, 500.)
        self.assertEqual(lvar.optim_plot_intervals, 15)

    def test_variable_change_is_stored(self):
        proj = self.provider.get_project(self.proj.id)
        var = proj.metamodels[0].variables[self.varid]
        var.optim_min = 7.
        var.optim_plot_intervals = 4
        self.provider.variable_provider.upsert_variable(var)

        restored = self.provider.variable_provider.get_variable(var.id)
        self.assertEqual(restored.get_optim_bounds(), (7., 500.))
        self.assertEqual(restored.optim_plot_intervals, 4)

    def test_duplicate_variable(self):
        var_id = self.mm.variables[self.varid].id
        dup = self.provider.variable_provider.duplicate_variable(var_id)
        self.assertNotEqual(dup.id, var_id)
        restored = self.provider.variable_provider.get_variable(dup.id)
        self.assertEqual(restored.get_optim_bounds(), (5., 500.))
        self.assertEqual(restored.optim_plot_intervals, 15)

    def test_duplicate_metamodel(self):
        dup = cast(NewsegsMetaModel, self.provider.metamodel_provider.duplicate_component(self.mm.id))
        self.assertNotEqual(dup.optim_config.id, self.mm.optim_config.id)
        self.assertEqual(dup.optim_config.method, 'Powell')

    def test_snapshot_restore(self):
        snapshot_id = self.provider.create_project_snapshot(self.proj.id, 'snap')

        # Change the live settings: the snapshot keeps the old ones
        proj = self.provider.get_project(self.proj.id)
        mm = cast(NewsegsMetaModel, proj.metamodels[0])
        mm.optim_config.method = 'TNC'
        mm.variables[self.varid].optim_min = 1.
        self.provider.upsert_component(proj)

        restored = self.provider.load_project_snapshot(self.proj.id, snapshot_id)
        restored_mm = cast(NewsegsMetaModel, restored.metamodels[0])
        self._check_settings(restored_mm)
        self.assertNotEqual(restored_mm.optim_config.id, self.mm.optim_config.id)

    def test_metamodel_without_optim_config_gets_default(self):
        # As saved before metamodels held optimisation settings
        with write_transaction(self.engine) as conn:
            conn.execute(
                tbls.metamodels.update()
                .where(tbls.metamodels.c.id == self.mm.id)
                .values(optim_config_id = None)
            )

        lproj = self.provider.get_lightweight_project(self.proj.id)
        self.assertIsNone(lproj.metamodels[0].optim_config)

        proj = self.provider.get_project(self.proj.id)
        mm = cast(NewsegsMetaModel, proj.metamodels[0])
        self.assertIsInstance(mm.optim_config, OptimComponent)
        self.assertEqual(mm.optim_config.method, 'Nelder-Mead')
        default_id = mm.optim_config.id

        self.provider.upsert_component(proj, force = True)
        with read_transaction(self.engine) as conn:
            stored_id = conn.execute(
                sa.select(tbls.metamodels.c.optim_config_id).where(tbls.metamodels.c.id == self.mm.id)
            ).scalar()
        self.assertEqual(stored_id, default_id)

    def test_get_optim_config(self):
        mm_provider = self.provider.metamodel_provider
        optim_config = mm_provider.get_optim_config(self.mm.id)
        self.assertEqual(optim_config.id, self.mm.optim_config.id)
        self.assertEqual(optim_config.method, 'Powell')

    def test_get_optim_config_stores_default(self):
        with write_transaction(self.engine) as conn:
            conn.execute(
                tbls.metamodels.update()
                .where(tbls.metamodels.c.id == self.mm.id)
                .values(optim_config_id = None)
            )
        mm_provider = self.provider.metamodel_provider
        optim_config = mm_provider.get_optim_config(self.mm.id, project_id = self.proj.id)
        self.assertEqual(optim_config.method, 'Nelder-Mead')

        # A change to it is a change to the metamodel's settings
        optim_config.method = 'TNC'
        self.provider._component_provider.upsert_component(optim_config)
        self.assertEqual(mm_provider.get_optim_config(self.mm.id).id, optim_config.id)
        proj = self.provider.get_project(self.proj.id)
        self.assertEqual(proj.metamodels[0].optim_config.method, 'TNC')
        self.assertEqual(len(proj.metamodels[0].variables), len(self.mm.variables))

    def test_not_pruned(self):
        from newsegsmodelapp.backend.pruning import prune_orphan_configurations
        prune_orphan_configurations(self.engine)
        with read_transaction(self.engine) as conn:
            count = conn.execute(
                sa.select(sa.func.count())
                .select_from(tbls.component_configs)
                .where(tbls.component_configs.c.id == self.mm.optim_config.id)
            ).scalar()
        self.assertEqual(count, 1)


if __name__ == '__main__':
    unittest.main()
