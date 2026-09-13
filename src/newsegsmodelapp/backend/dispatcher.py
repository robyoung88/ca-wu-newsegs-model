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

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_tables import runs

import newsegsmodelapp.register_plugins # Ensure this always gets imported
from newsegsmodelapp.backend.worker import worker_process

def run_proxy(server = DISPATCHSERVER, frontendport = FRONTENDPORT, backendport = BACKENDPORT):
    """Runs isolated in its own process."""
    context = zmq.Context()
    frontend = context.socket(zmq.ROUTER)
    frontend.bind(f'tcp://{server}:{frontendport}')
    backend = context.socket(zmq.DEALER)
    backend.bind(f'tcp://{server}:{backendport}')
    zmq.proxy(frontend, backend)

def run_dispatcher(
        num_workers = 4,
        server = DISPATCHSERVER,
        frontendport = FRONTENDPORT,
        backendport = BACKENDPORT,
        stop_event = None,
    ):
    """Supervisor to the proxy and workers"""
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

    # Start workers
    workers = {}
    for idx in range(num_workers):
        p = multiprocessing.Process(
            target = worker_process,
            args = (idx, server, backendport)
        )
        p.start()
        workers[idx] = p

    
    print("Supervisor online. Monitoring workers...")

    try:
        # The supervisor loop
        while stop_event is None or not stop_event.is_set():
            
            for idx in range(num_workers):
                # Check if process has died
                if not workers[idx].is_alive():
                    print(f"CRITICAL: Worker {idx} died! Restarting...")

                    # Spawn a replacement worker
                    p = multiprocessing.Process(
                        target = worker_process,
                        args = (idx, server, backendport)
                    )
                    p.start()
                    workers[idx] = p

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
            n_cleaned = _cleanup_dead_jobs(db.get_engine(), DEAD_CALCULATION_INTERVAL_SECONDS)
            if n_cleaned:
                print(f'Killed {n_cleaned} jobs due to timeout')

            # Touch the heartbeat file
            HEARTBEAT_FILE.touch()

            # Repeat every N seconds
            time.sleep(SUPERVISOR_INTERVAL_SECONDS)

    except KeyboardInterrupt:
        print('\nShutting down supervisor...')
    finally:
        # Ensure all subprocesses are terminated upon exit
        if proxy_process.is_alive():
            proxy_process.terminate()
            proxy_process.join(timeout=1)
        for p in workers.values():
            if p.is_alive():
                p.terminate()
                p.join(timeout=1)
            
def _cleanup_dead_jobs(engine, dead_interval_seconds: int) -> int:
    stmt = (
        sa.update(runs)
        .values(status = 'FAILED')
        .where(
            runs.c.status == 'CALCULATING',
            (sa.func.strftime('%s', 'now') - sa.func.strftime('%s', runs.c.modified_at)) > dead_interval_seconds
        )
    )

    with engine.connect() as conn:
        result = conn.execute(stmt)
        conn.commit()
    return result.rowcount

if __name__ == '__main__':
    db.init_db()
    run_dispatcher()
