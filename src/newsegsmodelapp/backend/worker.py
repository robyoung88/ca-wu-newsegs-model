"""A worker process for performing background computations."""
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
from newsegsmodelapp.backend.db.db_component_provider import FromDatabaseNewsegsProjectProvider
from newsegsmodelapp.backend.db.db_jobs import generate_claim_ticket
from newsegsmodelapp.backend.db.db_result_provider import FromDatabaseResultProvider

import newsegsmodelapp.register_plugins # Ensure this always gets imported
import newsegsmodelapp.registers as registers

def worker_process(worker_id: str, server: str = DISPATCHSERVER, port: str = BACKENDPORT):
    context = zmq.Context()
    socket = context.socket(zmq.REP)
    socket.connect(f'tcp://{server}:{port}')

    print(f'Worker listening on {server}:{port}')

    engine = db.get_engine()
    print(db.db._connected_db_path)
    print(engine.url)

    proj_provider = FromDatabaseNewsegsProjectProvider(db.get_engine)
    result_provider = FromDatabaseResultProvider(db.get_engine, RESULTS_STORE)

    while True:
        request = cast(registers.RunRequest, socket.recv_pyobj())

        # Generate a claim ticket in the results table
        job_id = generate_claim_ticket(engine, request)

        # Fulfill the ZeroMQ REQ/REP contract
        # Send the ticket back to client via the proxy
        socket.send_pyobj({
            'status': 'started',
            'job_id': job_id
        })

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
                return _update_calculation_progress(engine, job_id, step, total, message)
                
            def check_cancel_status() -> bool:
                """Return True if cancel_requested where result_id == job_id."""
                return _get_cancel_status(engine, job_id)
                
            is_ok = runner(
                request,
                proj_provider,
                result_provider,
                job_id,
                update_progress,
                check_cancel_status,
            )

            # Update the database with the final status and file pointer
            _set_status_completed(engine, job_id)
            print(f"Worker {worker_id} finished Job {job_id} with message {is_ok}. Ready for next request.")

        except Exception as e:
            _set_status_failed(engine, job_id, str(e))

            print(f"Worker {worker_id} failed Job {job_id}. Error {e}.")
            
        # Process loops back to recv, signalling to dealer that worker is free

def _update_calculation_progress(engine: sa.Engine, job_id: int, step, total, message):
    """Pass progress information into the database."""
    stmt = (
        sa.update(runs)
        .values(
            progress = step / total,
            progress_message = message
        )
        .where(runs.c.run_id == job_id)
    )

    with engine.begin() as conn:
        conn.execute(stmt)

def _get_cancel_status(engine: sa.Engine, job_id: int):
    stmt = (
        sa.select(runs.c.cancel_requested)
        .where(runs.c.run_id == job_id)
        .limit(1)
    )
    with engine.connect() as conn:
        result = conn.execute(stmt).fetchone()
        return bool(result and result[0])

def _set_status_completed(engine: sa.Engine, job_id: int):
    stmt = (
        sa.update(runs)
        .values(
            status = 'SUCCESS', 
            progress = 1.0,
        )
        .where(runs.c.run_id == job_id)
    )

    with engine.begin() as conn:
        conn.execute(stmt)

def _set_status_failed(engine: sa.Engine, job_id: int, message: str | None):
    update_vals = dict(
        status = 'FAILED',
        progress = 0.0
    )
    if message is not None:
        update_vals['progress_message'] = message
    stmt = (
        sa.update(runs)
        .values(
            **update_vals
        )
        .where(runs.c.run_id == job_id)
    )

    with engine.begin() as conn:
        conn.execute(stmt)
    