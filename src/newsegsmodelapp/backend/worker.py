"""A worker process for performing background computations."""
import copy
import pickle
from sqlalchemy.exc import OperationalError
from typing import cast

import zmq

from pathlib import Path
import sqlalchemy as sa

from config import settings
RESULTS_STORE = Path(str(settings['RESULTS_STORE']))
if not RESULTS_STORE.exists():
    RESULTS_STORE.mkdir(parents=True, exist_ok=True)
DISPATCHSERVER = settings['DISPATCHSERVERS'][0]
BACKENDPORT = str(settings['BACKENDPORT'])

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_tables import runs
from newsegsmodelapp.backend.db.db_component_provider import CachedFromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket, set_cancel_status, update_calculation_progress, get_cancel_status, set_status_completed, set_status_failed
from newsegsmodelapp.backend.db.db_result_provider import CachedFromDatabaseResultProvider

import newsegsmodelapp.register_plugins # Ensure this always gets imported
import newsegsmodelapp.registers as registers

POISON_PILL = b"__STOP__"

def worker_process(
    worker_id: str,
    server: str = DISPATCHSERVER, 
    port: str = BACKENDPORT, 
    db_path: str | None = None, 
    stop_event = None
):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.RCVTIMEO, settings.get('WORKER_RECEIVE_TIMEOUT_MS', -1))
    socket.connect(f'tcp://{server}:{port}')

    print(f'Worker {worker_id} listening on {server}:{port}')

    engine = db.get_engine(db_path)

    proj_provider = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)
    result_provider = CachedFromDatabaseResultProvider(db.get_engine, RESULTS_STORE)

    try: # Alive try - ensure that 'finally' runs even if we don't go into the while
        while stop_event is None or not stop_event.is_set():
            try: # Receive try
                frames = socket.recv_multipart()

                # Handle poison pill
                if frames[-1] == POISON_PILL:
                    print(f'Worker {worker_id} received poison pill. Shutting down...')
                    break

                # Extract envelope frames and payload frame
                client_envelope = frames[:-1]
                payload_bytes = frames[-1]

                request = cast(registers.RunRequest, pickle.loads(payload_bytes))

                job_id = generate_claim_ticket(engine, request)

                response_data = {
                    'status': 'started',
                    'worker': worker_id,
                    'job_id': job_id,
                }

                response_bytes = pickle.dumps(response_data)

                retries = 5
                
                while retries > 0:
                    try:
                        socket.send_multipart(client_envelope + [response_bytes])
                        send_completed = True
                        break
                    except OperationalError:
                        retries -= 1
                        continue
                    except Exception as e:
                        raise e
                else:
                    send_completed = False

                if not send_completed:
                    try:
                        socket.setsockopt(zmq.LINGER, 0)
                        socket.close()
                    except:
                        pass
                    socket = context.socket(zmq.REP)
                    socket.connect(f'tcp://{server}:{port}')
                    raise ValueError(f'Cannot send claim ticket back to client - database is unresponsive.')

                print(f'Worker {worker_id} starting job {job_id} - {request}')

                try:
                    if job_id is None:
                        raise ValueError(f'Calculation results not set for request {request}')

                    match request.request_class:
                        case 'run':
                            runner = registers.RUN_PROCEDURE_REGISTER.get(request.request_type)
                        case 'postprocess':
                            runner = registers.get_postprocess_procedure(request.request_type, request)
                        case 'tabledraw':
                            runner = registers.get_table_draw(request.request_type, request)
                        case _:
                            raise ValueError(f'Request class {request.request_class} not recognised.')
                    if runner is None:
                        raise ValueError(f'Runner not found: {request.request_type} - available runners are {list[registers.RUN_PROCEDURE_REGISTER.keys()]}')

                    def update_progress(step, total, message):
                        # Update SQLite with the new progress
                        return update_calculation_progress(engine, job_id, step, total, message)
                        
                    def check_cancel_status() -> bool:
                        """Return True if cancel_requested where result_id == job_id."""
                        # Check if supervisor would like worker to terminate.
                        if stop_event is not None and stop_event.is_set():
                            # Set the job to cancelled and then return true
                            set_cancel_status(engine, job_id)
                            return True
                        else:
                            return get_cancel_status(engine, job_id)

                    rq = copy.copy(request)
                    rq.run_id = job_id
                    
                    is_ok = runner(
                        rq,
                        proj_provider,
                        result_provider,
                        job_id,
                        update_progress,
                        check_cancel_status,
                    )

                    # Update the database with the final status and file pointer
                    set_status_completed(engine, job_id)
                    print(f"Worker {worker_id} finished Job {job_id} with message {is_ok}. Ready for next request.")

                except Exception as e:
                    set_status_failed(engine, job_id, str(e))

                    print(f"Worker {worker_id} failed Job {job_id}. Error {e}.")
            
            except zmq.Again:
                # Timeout hit (no message in 1 sec). Re-evaluate stop_event loop condition.
                continue
            except Exception as e:
                try:
                    socket.setsockopt(zmq.LINGER, 0)
                    socket.close()
                except:
                    pass
                socket = context.socket(zmq.REP)
                socket.connect(f'tcp://{server}:{port}')
                print(f"Worker {worker_id} encountered an error: {e}")
            # Process loops back to recv, signalling to dealer that worker is free
    
    finally:
        print(f'Worker {worker_id} disposing engine.')
        engine.dispose()
        socket.close()
        context.term()
