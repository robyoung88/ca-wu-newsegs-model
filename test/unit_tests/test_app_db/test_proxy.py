"""
Unit tests for the ZeroMQ proxy
"""
import os
from pathlib import Path
import pickle
import tempfile
import threading
import time
import unittest

import sqlalchemy as sa
import zmq

from config import settings

from newsegsmodelapp import registers
from newsegsmodelapp.backend import dispatcher
from newsegsmodelapp.backend.db.db import read_transaction
from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider

APP_ROOT = Path(__file__).parent.parent.parent.parent.resolve() / 'src'

class TestProxy(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.db_dir = tempfile.TemporaryDirectory()
        cls.db_path = Path(cls.db_dir.name) / 'tempdb.db'

        os.environ['DYNACONF_DB_PATH'] = str(cls.db_path)
        settings.reload()

        # Create the database
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        metadata = tbls.metadata

        # Create all tables
        metadata.create_all(db.get_engine(writer = True))

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
        
        cls.dispatcher_thread = threading.Thread(
            target = cls.run_proxy,
            args = (cls.frontend_port, cls.backend_port, cls.stop_dispatcher_event),
            daemon = True
        )
        cls.dispatcher_thread.start()

        # Give the proxy thread a moment to initialise
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls) -> None:
        """Clean up proxy threads"""
        from newsegsmodelapp.backend import db
        print('Setting stop event for supervisor.')
        cls.stop_dispatcher_event.set()

        # Wait for the thread and its underlying multiprocessing children to terminate
        cls.dispatcher_thread.join(timeout=10.0)
        cls.context.term()

        for writer in (True, False):
            engine = db.get_engine(writer = writer, db_path = cls.db_path)
            engine.dispose()

        cls.db_dir.cleanup()

    def setUp(self) -> None:
        os.environ['DYNACONF_DB_PATH'] = str(self.db_path)
        settings.reload()
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_dir = Path(self.temp_dir.name)

    def tearDown(self):
        """Clean up temporary directory after each test."""
        
        self.temp_dir.cleanup()

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

    def send_to_dispatcher(self, payload) -> dict:
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.connect(f'tcp://{"127.0.0.1"}:{self.frontend_port}')

        payload_bytes = pickle.dumps(payload)
        socket.send(payload_bytes)
        
        reply_bytes = socket.recv()
        reply_data = pickle.loads(reply_bytes)

        socket.close()
        context.term()

        return reply_data

    def test_dispatched_process(self):
        import newsegsmodelapp.register_plugins
        from newsegsmodelapp.backend import db
        from newsegsmodelapp.backend.db import tables as tbls
        from newsegsmodelframework.plugins.registers import PROJECT_FACTORIES
        
        proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
        result_provider = FromDatabaseResultProvider(db.get_engine, self.test_dir)
        proj = PROJECT_FACTORIES['sprake']()
        proj_provider.add_component(proj)

        request_creator = registers.RUN_REQUEST_REGISTER['deterministic_run_metamodel']
        request = request_creator(proj.id, proj_provider)

        prox_resp = self.send_to_dispatcher(request)
        self.assertEqual(prox_resp.get('status'), 'started')
        job_id = prox_resp['job_id']
        if isinstance(job_id, int):
            job_id = [job_id,]
        
        while True:
            stmt = (
                sa.select(
                    tbls.runs.c.run_id,
                    tbls.runs.c.progress,
                    tbls.runs.c.status,
                    tbls.runs.c.modified_at,
                    tbls.runs.c.progress_message,
                )
                .where(tbls.runs.c.run_id.in_(job_id))
            )
            with read_transaction(db.get_engine()) as conn:
                rows = conn.execute(stmt).all()

            if len(rows) < 1:
                raise ValueError(f'Run not present in database: {job_id}')
            print(rows[0]._mapping['progress'], ' at ', rows[0]._mapping['modified_at'], ' with message ', rows[0]._mapping['progress_message'], ' and status ', rows[0]._mapping['status'])
            if rows[0].status == 'SUCCESS':
                break
            elif rows[0].status == 'FAILED':
                raise ValueError(f'Run failed')
            time.sleep(0.1)
        
        proj = proj_provider.get_project(proj.id)

        generation = proj.metamodels[0].model.generation
        generation_res, verstring = result_provider.get_result('deterministic_generation', generation, True)

        self.assertEqual(generation.revision, verstring)
        self.assertGreater(len(generation_res.meters_to_pandas()), 8760) # pyright: ignore[reportOptionalMemberAccess]
