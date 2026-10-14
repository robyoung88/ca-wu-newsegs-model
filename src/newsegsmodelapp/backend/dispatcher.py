"""proxy between client and workers"""
import multiprocessing
import time
import zmq

from pathlib import Path
import sqlalchemy as sa

from config import settings
DISPATCHSERVER = settings['DISPATCHSERVERS'][0]
FRONTENDPORT = settings['FRONTENDPORT']
BACKENDPORT = settings['BACKENDPORT']
DB_PATH = Path(str(settings['DB_PATH']))
SUPERVISOR_INTERVAL_SECONDS = 5
DEAD_CALCULATION_INTERVAL_SECONDS = 300
HEARTBEAT_FILE = Path(str(settings['HEARTBEAT_FILE']))

from newsegsmodelapp import APP_ROOT
import os
os.environ['ROOT_PATH_FOR_DYNACONF'] = str(APP_ROOT)

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db import write_transaction
from newsegsmodelapp.backend.db.db_tables import runs

import newsegsmodelapp.register_plugins # Ensure this always gets imported
from newsegsmodelapp.backend.worker import worker_process, POISON_PILL

def run_proxy(server = DISPATCHSERVER, frontendport = FRONTENDPORT, backendport = BACKENDPORT):
    """Runs isolated in its own process."""
    context = zmq.Context()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind(f'tcp://{server}:{frontendport}')
    backend = context.socket(zmq.DEALER)
    backend.bind(f'tcp://{server}:{backendport}')
    try:
        print(f'Proxy establishing on {server} between {frontendport} and {backendport}')
        zmq.proxy(frontend, backend)
    except zmq.ContextTerminated:
        pass
    finally:
        frontend.close()
        backend.close()
        context.term()

def _send_poison_pills(num_workers, server, backendport):
    """Sends poison pill messages through the backend socket to unblock workers."""
    context = zmq.Context()
    # Connect as a client to the backend DEALER socket
    killer = context.socket(zmq.DEALER)
    killer.connect(f'tcp://{server}:{backendport}')

    for _ in range(num_workers):
        # Format: empty delimiter frame + payload frame (matches standard DEALER/REQ conventions)
        killer.send_multipart([b"", POISON_PILL])

    time.sleep(0.2)  # Give ZeroMQ I/O thread time to flush frames
    killer.close()
    context.term()

def run_dispatcher(
        num_workers = 4,
        server = DISPATCHSERVER,
        frontendport = FRONTENDPORT,
        backendport = BACKENDPORT,
        db_path: str | None = None,
        stop_event = None,
        clean_interval_s = 60,
    ):
    """Supervisor to the proxy and workers"""

    engine = db.get_engine(db_path)

    # Start Proxy in the background
    proxy_process = multiprocessing.Process(
        target = run_proxy, 
        kwargs = {
            'server': server, 
            'frontendport': frontendport, 
            'backendport': backendport
        }
    )
    proxy_process.start()

    worker_server = "127.0.0.1"

    # Start workers
    workers = {}
    workers_stop = {}
    for idx in range(num_workers):
        wstop_event = multiprocessing.Event()
        p = multiprocessing.Process(
            target = worker_process,
            args = (idx, worker_server, backendport, db_path, wstop_event)
        )
        p.start()
        workers[idx] = p
        workers_stop[idx] = wstop_event
    
    print("Supervisor online. Monitoring workers...")
    last_cleaned = time.time()
    try:
        # The supervisor loop
        while stop_event is None or not stop_event.is_set():
            
            for idx in range(num_workers):
                # Check if process has died
                if not workers[idx].is_alive():
                    print(f"CRITICAL: Worker {idx} died! Restarting...")

                    # Spawn a replacement worker
                    wstop_event = multiprocessing.Event()
                    p = multiprocessing.Process(
                        target = worker_process,
                        args = (idx, worker_server, backendport, db_path, wstop_event)
                    )
                    p.start()
                    workers[idx] = p
                    workers_stop[idx] = wstop_event

            # Check if proxy has died
            if not proxy_process.is_alive():
                print(f"CRITICAL: Proxy died! Restarting...")
                proxy_process = multiprocessing.Process(
                    target = run_proxy,
                    kwargs = {
                        'server': server, 
                        'frontendport': frontendport, 
                        'backendport': backendport
                    })
                proxy_process.start()

            # Check for dead jobs
            now = time.time()
            if now - last_cleaned > clean_interval_s:
                n_cleaned = _cleanup_dead_jobs(engine, DEAD_CALCULATION_INTERVAL_SECONDS)
                if n_cleaned:
                    print(f'Killed {n_cleaned} jobs due to timeout')
                last_cleaned = now

            # Touch the heartbeat file
            HEARTBEAT_FILE.touch()

            # Repeat every N seconds
            time.sleep(SUPERVISOR_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print('\nShutting down supervisor...')
        
    finally:
        # Ensure all subprocesses are terminated upon exit
        print('Supervisor is shutting down cleanly...')

        # Set stop events to cancel ongoing jobs on next check_cancel_status()
        for st in workers_stop.values():
            st.set()

        # For workers not in a job, send a poison pill to break out of receive loop and close
        try:
            _send_poison_pills(len(workers), server, backendport)
        except Exception as e:
            print(f"Failed to send poison pills: {e}")

        # Check workers have ended processes, and send a terminate if not.
        for idx, p in workers.items():
            p.join(timeout = settings.get('WORKER_SHUTDOWN_TIMEOUT_S', 3))
            if p.is_alive():
                print(f"Worker {idx} did not exit in time; terminating forcefully.")
                p.terminate()
                p.join(timeout = 1)

        engine.dispose()

        # Hard termination of the proxy process - no resources to worry about.
        if proxy_process.is_alive():
            proxy_process.terminate()
            proxy_process.join(timeout = 1)
            
def _cleanup_dead_jobs(engine, dead_interval_seconds: int) -> int:
    stmt = (
        sa.update(runs)
        .values(status = 'FAILED')
        .where(
            runs.c.status == 'CALCULATING',
            (sa.func.strftime('%s', 'now') - sa.func.strftime('%s', runs.c.modified_at)) > dead_interval_seconds
        )
    )

    with write_transaction(engine) as conn:
        result = conn.execute(stmt)
    return result.rowcount

if __name__ == '__main__':
    db.init_db()
    run_dispatcher()
