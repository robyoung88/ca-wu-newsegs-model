"""
Unit tests of the handling of cancelled requests.
"""

import os
from pathlib import Path
import tempfile
import threading
import time
import unittest

import sqlalchemy as sa
import zmq

from config import settings
# The plugins import the action callbacks, so are loaded first, as by the app
from newsegsmodelapp import APP_ROOT
from newsegsmodelapp.backend import dispatcher
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestCancelledError
import newsegsmodelapp.register_plugins  # noqa: F401
from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_request_handler import FromDatabaseRequestHandler

class TestCancel(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors = True)
        cls.db_path = Path(cls.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(cls.db_path)
        settings.reload()

        from newsegsmodelapp.backend import db
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES

        # Create all tables
        db_tables.create_all_tables(db.get_engine(writer = True))

        # # Proxy
        # cls.context = zmq.Context.instance()
        # # Bind frontend and backend on dynamically allocated ports (port=0)
        # # Allocate ephemeral ports dynamically
        # frontend_socket = cls.context.socket(zmq.ROUTER)
        # backend_socket = cls.context.socket(zmq.DEALER)
        # cls.frontend_port = frontend_socket.bind_to_random_port("tcp://127.0.0.1")
        # cls.backend_port = backend_socket.bind_to_random_port("tcp://127.0.0.1")
        # frontend_socket.close(linger=0)
        # backend_socket.close(linger=0)

        # # Start proxy in a daemon thread
        # cls.stop_dispatcher_event = threading.Event()
        # cls.dispatcher_thread = threading.Thread(
        #     target = cls.run_proxy,
        #     args = (cls.frontend_port, cls.backend_port, cls.stop_dispatcher_event),
        #     daemon = True
        # )
        # cls.dispatcher_thread.start()
        # # Give the proxy thread a moment to initialise
        # time.sleep(0.5)

        cls.proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        cls.proj = PROJECT_FACTORIES['sprake']()
        cls.proj_provider.add_component(cls.proj)
        cls.request_handler = FromDatabaseRequestHandler(db.get_engine)

        cls._writer = db.get_engine(writer = True)

    @classmethod
    def tearDownClass(cls):
        from newsegsmodelapp.backend import db

        for writer in (False, True):
            db.get_engine(writer = writer, db_path = cls.db_path).dispose()
    
        # cls.stop_dispatcher_event.set()
        # # Wait for the thread and its underlying multiprocessing children to terminate
        # cls.dispatcher_thread.join(timeout=10.0)
        # cls.context.term()

        cls.db_dir.cleanup()

    # def setUp(self) -> None:
    #     """Create a temporary directory to hold results, which should not really get generated."""
    #     os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
    #     settings.reload()
    #     self.temp_dir = tempfile.TemporaryDirectory()
    #     self.test_dir = Path(self.temp_dir.name)

    # def tearDown(self):
    #     """Clean up temporary directory after each test."""
        
    #     self.temp_dir.cleanup()

    @staticmethod
    def run_proxy(frontendport, backendport, stop_event):
        """Proxy worker thread executing zmq proxy."""
        os.environ['ROOT_PATH_FOR_DYNACONF'] = str(APP_ROOT)
        try:
            dispatcher.run_dispatcher(
                server = '127.0.0.1',
                frontendport = frontendport,
                backendport = backendport,
                db_path = str(settings['DB_PATH']),
                stop_event = stop_event
            )
        except zmq.ZMQError:
            pass # Expected when sockets are closed during cleanup

    def _add_request(self):
        return self.request_handler.add_request(
            'deterministic_run_metamodel', self.proj.id, self.proj_provider, 'run'
        )

    def _cancel_request(self, request_id):
        self.request_handler.cancel_requests(request_id)

    def _request_status(self, request_id):
        from newsegsmodelapp.backend import db
        with read_transaction(db.get_engine()) as conn:
            return conn.execute(
                sa.select(db_tables.requests.c.status)
                .where(db_tables.requests.c.request_id == request_id)
            ).scalar()

    def test_cancel_not_dispatched(self):
        request = self._add_request()
        # Check request is good to go
        self.assertEqual(self._request_status(request.request_id), 'AWAITING DISPATCH')
        # Cancel the job
        self._cancel_request(request.request_id)
        # Check status is set
        self.assertEqual(self._request_status(request.request_id), 'CANCELLED')
        # Try to generate the claim ticket directly - pretend we are a worker who has been delayed until after cancellation
        # Expect some form of exception due to starting a cancelled job.
        with self.assertRaises(RequestCancelledError):
            job_id, job_exists = generate_claim_ticket(self._writer, request)
