"""
Unit tests of the handling of failed jobs: failures that running again will not cure are not
retried, and abandoned jobs are reported as failed in the results containers.
"""
import os
from pathlib import Path
import tempfile
import unittest

from dash import no_update
import sqlalchemy as sa

from config import settings
# The plugins import the action callbacks, so are loaded first, as by the app
import newsegsmodelapp.register_plugins  # noqa: F401
from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_jobs import is_retryable, prevent_request_retry
from newsegsmodelapp.backend.db.db_request_handler import FromDatabaseRequestHandler
from newsegsmodelapp.components.callbacks.action_callbacks import results_status
from newsegsmodelframework.core.environment.environment_servers import EnvironmentDataUnavailableError


class TestRetry(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        cls.db_path = Path(cls.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(cls.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        db_tables.create_all_tables(db.get_engine(writer = True))

        cls.proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        cls.proj = PROJECT_FACTORIES['sprake']()
        cls.proj_provider.add_component(cls.proj)
        cls.request_handler = FromDatabaseRequestHandler(db.get_engine)

    @classmethod
    def tearDownClass(cls):
        from newsegsmodelapp.backend import db

        for writer in (False, True):
            db.get_engine(writer = writer, db_path = cls.db_path).dispose()

        cls.db_dir.cleanup()

    def _add_request(self):
        return self.request_handler.add_request(
            'deterministic_run_metamodel', self.proj.id, self.proj_provider, 'run'
        )

    def _request_status(self, request_id):
        from newsegsmodelapp.backend import db
        with read_transaction(db.get_engine()) as conn:
            return conn.execute(
                sa.select(db_tables.requests.c.status)
                .where(db_tables.requests.c.request_id == request_id)
            ).scalar()

    def test_failure_retried(self):
        request = self._add_request()
        self.assertTrue(self.request_handler.increment_failure(request.request_id))
        self.assertEqual(self._request_status(request.request_id), 'AWAITING DISPATCH')

    def test_failure_not_retried(self):
        from newsegsmodelapp.backend import db
        request = self._add_request()
        # A first failure is retried
        self.assertTrue(self.request_handler.increment_failure(request.request_id))

        prevent_request_retry(db.get_engine(writer = True), request.request_id)

        self.assertFalse(self.request_handler.increment_failure(request.request_id))
        self.assertEqual(self._request_status(request.request_id), 'CANCELLED')

    def test_is_retryable(self):
        self.assertTrue(is_retryable(ValueError('a bug')))
        self.assertFalse(is_retryable(EnvironmentDataUnavailableError('no response')))

class TestResultsStatus(unittest.TestCase):

    def test_calculating(self):
        self.assertEqual(
            results_status(True, ['an earlier failure'], True, '1 jobs underway.'),
            ('CALCULATING', 'Computing...', '1 jobs underway.')
        )
        self.assertEqual(
            results_status(True, [], False, '1 jobs underway.'),
            ('CALCULATING', no_update, '1 jobs underway.')
        )

    def test_failed(self):
        status, title, subtitle = results_status(False, ['Unable to obtain wind speeds from NEWA'], False, no_update)
        self.assertEqual(status, 'FAILED')
        self.assertEqual(title, 'A job failed')
        self.assertEqual(subtitle, 'Unable to obtain wind speeds from NEWA')

    def test_failed_messages_not_repeated(self):
        status, title, subtitle = results_status(False, ['a', 'b', 'a'], False, no_update)
        self.assertEqual(title, '3 jobs failed')
        self.assertEqual(subtitle, 'a | b')

    def test_idle(self):
        self.assertEqual(results_status(False, [], False, no_update), ('IDLE', no_update, no_update))
