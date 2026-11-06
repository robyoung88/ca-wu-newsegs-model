"""
Loading a project whose metamodels have no optimisation settings stored (#168).

Migration 9eeaede183f3 leaves `metamodels.optim_config_id` null, so that the default settings are stored at the next
save of the metamodel, and snapshots taken before it have no settings either. The lightweight metamodel of such a row
has an `optim_config` of None. The cached project provider logs the state of each project it caches, which read the id
of `optim_config`, so loading the project failed with `AttributeError: 'NoneType' object has no attribute 'id'`.

The log's arguments are evaluated whatever the logging level, so these tests don't depend on it.
"""
import os
from pathlib import Path
import tempfile
from typing import cast
import unittest

import sqlalchemy as sa

from newsegsmodelapp.backend.db import db_tables as tbls
from newsegsmodelapp.backend.db.db import write_transaction
from newsegsmodelapp.backend.db.db_component_provider import (
    CachedFromDatabaseNewsegsProjectProvider, FromDatabaseNewsegsProjectProvider, get_project_critical_state,
)
from newsegsmodelframework import register_plugins # noqa: F401 - registers the project factories
from newsegsmodelframework.newsegsmetamodel.newsegsmetamodel import NewsegsMetaModel
from newsegsmodelframework.newsegsmetamodel.optim_component import OptimComponent

from config import settings


class TestProjectWithoutOptimConfig(unittest.TestCase):

    def setUp(self):
        self.db_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        self.db_path = Path(self.db_dir.name) / 'tempdb.db'
        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        self.engine = db.get_engine(writer = True)
        tbls.create_all_tables(self.engine)

        proj = PROJECT_FACTORIES['sprake']()
        FromDatabaseNewsegsProjectProvider(db.get_engine).add_component(proj)
        self.project_id = proj.id
        self.metamodel_ids = [mm.id for mm in proj.metamodels]

        # As left by the migration, or restored from a snapshot taken before it
        with write_transaction(self.engine) as conn:
            conn.execute(
                sa.update(tbls.metamodels)
                .where(tbls.metamodels.c.id.in_(self.metamodel_ids))
                .values(optim_config_id = None)
            )

    def tearDown(self):
        from newsegsmodelapp.backend import db
        for writer in (False, True):
            db.get_engine(writer = writer, db_path = self.db_path).dispose()
        self.db_dir.cleanup()

    def provider(self) -> CachedFromDatabaseNewsegsProjectProvider:
        from newsegsmodelapp.backend import db
        return CachedFromDatabaseNewsegsProjectProvider(db.get_engine)

    def test_lightweight_project(self):
        lproj = self.provider().get_lightweight_project(self.project_id)
        self.assertEqual(lproj.id, self.project_id)
        self.assertEqual([lmm.id for lmm in lproj.metamodels], self.metamodel_ids)
        for lmm in lproj.metamodels:
            self.assertIsNone(lmm.optim_config)

    def test_project_has_the_default_settings(self):
        provider = self.provider()
        provider.get_lightweight_project(self.project_id)
        proj = provider.get_project(self.project_id)
        mm = cast(NewsegsMetaModel, proj.metamodels[0])
        self.assertIsInstance(mm.optim_config, OptimComponent)
        self.assertEqual(mm.optim_config.method, OptimComponent().method)
        self.assertEqual(mm.optim_config.statistic, OptimComponent().statistic)

    def test_critical_state(self):
        # The state logged for a project without settings, whatever the logging level
        from newsegsmodelapp.backend import db
        lproj = FromDatabaseNewsegsProjectProvider(db.get_engine).get_lightweight_project(self.project_id)
        state = get_project_critical_state(lproj)
        self.assertIsNone(state['metamodel_0.optim_config'])
        self.assertIsNotNone(state['metamodel_0.table_config'])

    def test_loaded_again_in_another_process(self):
        # Each process has its own cache, so each loads the project from the database
        for _ in range(2):
            self.assertEqual(self.provider().get_lightweight_project(self.project_id).id, self.project_id)
