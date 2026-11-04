"""A worker process for performing background computations."""
import logging
import random
import time
logger = logging.getLogger(__name__)

import copy
import pickle
from sqlalchemy.exc import OperationalError
from typing import cast

import zmq

from pathlib import Path

from config import settings
RESULTS_STORE = Path(str(settings['RESULTS_STORE']))
if not RESULTS_STORE.exists():
    RESULTS_STORE.mkdir(parents=True, exist_ok=True)
DISPATCHSERVER = settings['DISPATCHSERVERS'][0]
BACKENDPORT = str(settings['BACKENDPORT'])

from newsegsmodelapp.backend import db
from newsegsmodelapp.backend.db.db_component_provider import CachedFromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket, is_retryable, prevent_request_retry, set_cancel_request_status, update_calculation_progress, get_cancel_status, set_status_success, set_status_failed
from newsegsmodelapp.backend.db.db_result_provider import CachedFromDatabaseResultProvider

import newsegsmodelapp.register_plugins # Ensure this always gets imported  # noqa: F401
import newsegsmodelapp.registers as registers


POISON_PILL = b"__STOP__"

class RunAlreadyExistsError(BaseException):
    """Raised (as an exception which is not caught by ordinary handlers) when a run already exists for a request, so that the request is not run twice.
    """
    pass

def worker_process(
    worker_id: str,
    server: str = DISPATCHSERVER, 
    port: str = BACKENDPORT, 
    db_path: str | None = None, 
    stop_event = None
):
    """The main loop of a worker process.

    Connects to the dispatcher over ZeroMQ, and for each request received: creates a run, looks up the run, postprocess or table draw
    procedure registered for the request, executes it with progress and cancellation callbacks, and records the outcome in the
    database. Runs until `stop_event` is set or a stop message is received.

    Args:
        worker_id: Identifier of the worker, for logging.
        server: Address of the dispatcher.
        port: Port on which the dispatcher serves workers.
        db_path: Path of the database file; the default if None.
        stop_event: Event which, when set, tells the worker to stop.
    """
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.setsockopt(zmq.RCVTIMEO, settings.get('WORKER_RECEIVE_TIMEOUT_MS', -1))
    socket.connect(f'tcp://{server}:{port}')

    logger.info('Worker %d listening on %s:%s', worker_id, server, port)

    write_engine = db.get_engine(writer = True, db_path = db_path)
    read_engine = db.get_engine(writer = False, db_path = db_path)

    proj_provider = CachedFromDatabaseNewsegsProjectProvider(db.get_engine)
    result_provider = CachedFromDatabaseResultProvider(db.get_engine, RESULTS_STORE)

    try: # Alive try - ensure that 'finally' runs even if we don't go into the while
        while stop_event is None or not stop_event.is_set():
            try: # Receive try
                frames = socket.recv_multipart()

                # Handle poison pill
                if frames[-1] == POISON_PILL:
                    logger.info('Worker %d received poison pill. Shutting down...', worker_id)
                    break

                # Extract envelope frames and payload frame
                client_envelope = frames[:-1]
                payload_bytes = frames[-1]

                request = cast(registers.RunRequest, pickle.loads(payload_bytes))

                job_id, job_exists = generate_claim_ticket(write_engine, request)

                response_data = {
                    'status': 'started',
                    'worker': worker_id if not job_exists else None,
                    'job_id': job_id,
                    'prexisting': job_exists
                }

                response_bytes = pickle.dumps(response_data)

                retries = 5
                # TODO: Sort out this mess. What's it to do with the database?
                
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

                if job_exists:
                    # Loop back
                    raise RunAlreadyExistsError

                logger.info(
                    'Worker %d initiating procedure %s for Request ID = %d; Run ID = %d, Triggering Request ID = %d',
                    worker_id, request.request_type, request.request_id,
                    job_id, request.trigger_request_id
                )

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
                        return update_calculation_progress(write_engine, job_id, step, total, message)
                        
                    def check_cancel_status() -> bool:
                        """Return True if cancel_requested where result_id == job_id."""
                        # Check if supervisor would like worker to terminate.
                        if stop_event is not None and stop_event.is_set():
                            # Set the job to cancelled and then return true
                            set_cancel_request_status(write_engine, job_id, True)
                            return True
                        else:
                            return get_cancel_status(read_engine, job_id)

                    rq = copy.copy(request)
                    rq.run_id = job_id

                    # Hold back to allow the client to mark the job(s) as dispatched
                    time.sleep(settings.get('WORKER_HOLDBACK_TIME_S', 0.00) + random.random() * settings.get('WORKER_HOLDBACK_JITTER', 0.00) )
                    
                    is_ok = runner(
                        rq,
                        proj_provider,
                        result_provider,
                        job_id,
                        update_progress,
                        check_cancel_status,
                    )

                    # Update the database marking the run successful
                    set_status_success(write_engine, job_id)
                    logger.info(
                        'Worker %d Completed procedure %s for Request ID = %d; with message %s; Run ID = %d; Triggering Request ID = %d. Ready for next request.',
                        worker_id, request.request_type, request.request_id, is_ok,
                        job_id, request.trigger_request_id
                    )

                except Exception as e:
                    if not is_retryable(e):
                        prevent_request_retry(write_engine, request.request_id)
                    set_status_failed(write_engine, job_id, str(e))
                    logger.warning(
                        'Worker %d Failed procedure %s for Request ID = %d; Run ID = %d; Triggering Request ID = %d;',
                        worker_id, rq.request_type, rq.request_id,
                        job_id, rq.trigger_request_id,
                        exc_info = True
                    )
            
            except (zmq.Again, RunAlreadyExistsError):
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
                logger.error('Worker %d encountered an error', worker_id, exc_info = True)
            # Process loops back to recv, signalling to dealer that worker is free


    finally:
        logger.info('Worker %d disposing engines and closing sockets.', worker_id)
        write_engine.dispose()
        read_engine.dispose()
        socket.close()
        context.term()
