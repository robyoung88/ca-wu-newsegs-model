"""
Unit tests of the handling of cancelled requests.
"""

import multiprocessing
import os
import queue
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
from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.components.callbacks.action_callbacks import _get_run_statuses, send_to_dispatcher, spawn_job
from newsegsmodelapp.components.requesthandler.requesthanderinterface import RequestCancelledError
import newsegsmodelapp.register_plugins  # noqa: F401
from newsegsmodelapp.backend.db import db_tables
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_request_handler import FromDatabaseRequestHandler

class TestCancel(unittest.TestCase):
    num_workers = 1

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

        # Proxy
        cls.context = zmq.Context.instance()
        # Bind frontend and backend on dynamically allocated ports (port=0)
        # Allocate ephemeral ports dynamically
        frontend_socket = cls.context.socket(zmq.ROUTER)
        backend_socket = cls.context.socket(zmq.DEALER)
        cls.frontend_port = frontend_socket.bind_to_random_port("tcp://127.0.0.1")
        cls.backend_port = backend_socket.bind_to_random_port("tcp://127.0.0.1")
        frontend_socket.close(linger=0)
        backend_socket.close(linger=0)

        # Start proxy in a daemon thread
        cls.stop_dispatcher_event = threading.Event()
        cls.worker_ready_queue = multiprocessing.get_context("spawn").Queue()
        cls.dispatcher_thread = threading.Thread(
            target = cls.run_proxy,
            args = (
                cls.frontend_port,
                cls.backend_port,
                cls.stop_dispatcher_event,
                cls.worker_ready_queue,
            ),
            daemon = True
        )
        cls.dispatcher_thread.start()
        ready_worker_ids = set()
        deadline = time.monotonic() + 30
        while len(ready_worker_ids) < cls.num_workers and time.monotonic() < deadline:
            try:
                ready_worker_ids.add(
                    cls.worker_ready_queue.get(
                        timeout = max(0, deadline - time.monotonic())
                    )
                )
            except queue.Empty:
                break
        if len(ready_worker_ids) < cls.num_workers:
            cls.stop_dispatcher_event.set()
            cls.dispatcher_thread.join(timeout = 10.0)
            cls.worker_ready_queue.close()
            cls.worker_ready_queue.join_thread()
            cls.context.term()
            db.get_engine(writer = True, db_path = cls.db_path).dispose()
            cls.db_dir.cleanup()
            raise RuntimeError(
                f'Only {len(ready_worker_ids)} of {cls.num_workers} dispatcher workers became ready to receive requests.'
            )

        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.test_dir = Path(cls.temp_dir.name)

        cls.proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        cls.proj = PROJECT_FACTORIES['sprake']()
        cls.proj_provider.add_component(cls.proj)
        cls.request_handler = FromDatabaseRequestHandler(db.get_engine)
        cls.results_provider = FromDatabaseResultProvider(db.get_engine, cls.test_dir)

        cls._writer = db.get_engine(writer = True)

    @classmethod
    def tearDownClass(cls):
        from newsegsmodelapp.backend import db

        for writer in (False, True):
            db.get_engine(writer = writer, db_path = cls.db_path).dispose()
    
        cls.stop_dispatcher_event.set()
        # Wait for the thread and its underlying multiprocessing children to terminate
        cls.dispatcher_thread.join(timeout=10.0)
        cls.worker_ready_queue.close()
        cls.worker_ready_queue.join_thread()
        cls.context.term()

        cls.db_dir.cleanup()
        cls.temp_dir.cleanup()        

    @staticmethod
    def run_proxy(frontendport, backendport, stop_event, worker_ready_queue):
        """Proxy worker thread executing zmq proxy."""
        os.environ['ROOT_PATH_FOR_DYNACONF'] = str(APP_ROOT)
        try:
            dispatcher.run_dispatcher(
                num_workers = TestCancel.num_workers,
                server = '127.0.0.1',
                frontendport = frontendport,
                backendport = backendport,
                db_path = str(settings['DB_PATH']),
                stop_event = stop_event,
                worker_ready_queue = worker_ready_queue,
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

    def test_slow_reraise_request(self):
        request_1 = self._add_request()
        request_2 = self._add_request()
        # Dispatch first request
        spawn_job(
            request_1, 
            self.proj_provider, self.results_provider, self.request_handler,
            '127.0.0.1',  self.frontend_port
        )
        # Ensure a clear first dispatched
        time.sleep(0.01)
        # Dispatch second request
        spawn_job(
            request_2, 
            self.proj_provider, self.results_provider, self.request_handler,
            '127.0.0.1',  self.frontend_port
        )
        # Wait enough time for the first job to be picked up and a reasonable resolution for slow requests
        time.sleep(0.1)
        # Check request_statuses
        request_list = self.request_handler.get_active_requests()
        request_dict = {x.request_id: x for x in request_list}
        self.assertEqual(request_dict[request_1.request_id].status, 'PROCESSING')
        self.assertEqual(request_dict[request_2.request_id].status, 'AWAITING WORKER')

        # Check second request is not picked up as a slow one yet
        self.assertEqual(len(self.request_handler.get_slow_requests(self.proj.id)),0)
        # Check second request is now picked up as a slow one
        self.assertEqual(len(self.request_handler.get_slow_requests(self.proj.id, 0.1)), 1)

        p1run = request_dict[request_1.request_id].run_id

        while True:
            run_stat = _get_run_statuses([p1run])
            request_list = self.request_handler.get_active_requests()
            request_dict = {x.request_id: x for x in request_list}
            if request_dict[request_2.request_id].status == 'PROCESSING':
                self.assertEqual(run_stat[p1run]['status'], 'SUCCESS')
                break
            self.assertIn(run_stat[p1run]['status'], ['CALCULATING','SUCCESS'])

        self.request_handler.cancel_requests()
        