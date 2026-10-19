import logging
from typing import Sequence
logger = logging.getLogger(__name__)

from dataclasses import asdict
import json

import sqlalchemy as sa

from newsegsmodelapp.backend.db.db import read_transaction, write_transaction, write_with_retries
from newsegsmodelapp.registers import RunRequest
from newsegsmodelapp.backend.db import tables as tbls

def generate_claim_ticket(
    engine: sa.Engine, 
    request: RunRequest
) -> tuple[int, bool]:
    """Generate a claim ticket in the results table and return run (job) id and whether run is already existing."""

    run_val = {
        'request_id': request.request_id,
        'status': 'CALCULATING'
    }

    run_exists_stmt = (
        sa.select(tbls.runs.c.run_id)
        .where(
            tbls.runs.c.request_id == request.request_id,
            tbls.runs.c.status.in_(['READY', 'CALCULATING', 'SUCCESS', 'COMPLETED'])
        )
    )

    insert_stmt = (
        sa.insert(tbls.runs)
        .values(run_val)
        .returning(tbls.runs.c.run_id)
    )

    with write_transaction(engine) as conn:
        existing = conn.execute(run_exists_stmt).scalar()
        if existing:
            return existing, True
        
        result = conn.execute(insert_stmt)
        row = result.fetchone()
        if row is None:
            raise ValueError(f'Claim ticket not generated for Request ID = {request.request_id}')
        run_id = row[0]
        logger.debug('Claim Ticket Run ID = %d; generated for Request ID = %s;', run_id, request.request_id)

        # Update the corresponding request record if request_id is available
        if request.request_id is not None:
            update_stmt = (
                sa.update(tbls.requests)
                .where(tbls.requests.c.request_id == request.request_id)
                .values(
                    status="DISPATCHED",
                    run_id=run_id
                )
            )
            conn.execute(update_stmt)

    request.run_id = run_id
    return run_id, False

def update_calculation_progress(engine: sa.Engine, job_id: int, step, total, message):
    """Pass progress information into the database."""
    logger.debug(
        'Updating Run Progress: Run ID = %d; Step = %s; Total = %s; Message = %s',
        job_id, step, total, message
    )
    stmt = (
        sa.update(tbls.runs)
        .values(
            progress = step / total,
            progress_message = message
        )
        .where(tbls.runs.c.run_id == job_id)
    )
    write_with_retries(engine, stmt, base_sleep = 0.02)

def set_cancel_request_status(engine: sa.Engine, job_id: int, status: bool = True):
    logger.info('Setting Run Cancel Request Status to %s: Run ID = %d;', status, job_id)
    stmt = (
        sa.update(tbls.runs)
        .where(tbls.runs.c.run_id == job_id)
        .values(cancel_requested = status)
    )
    write_with_retries(engine, stmt)

def get_cancel_status(engine: sa.Engine, job_id: int):
    stmt = (
        sa.select(tbls.runs.c.cancel_requested)
        .where(tbls.runs.c.run_id == job_id)
        .limit(1)
    )
    with read_transaction(engine)as conn:
        result = conn.execute(stmt).fetchone()
    return bool(result and result[0])

def set_status_success(engine: sa.Engine, run_id: int | Sequence[int]):
    """Call when run has completed request, but before postprocessing triggers have been applied."""
    run_id = [run_id] if isinstance(run_id, int) else run_id
    
    for rid in run_id:
        logger.debug('Setting Run Status to "SUCCESS": Run ID = %d;', rid)
    
    stmt = (
        sa.update(tbls.runs)
        .values(
            status = 'SUCCESS', 
            progress = 1.0,
        )
        .where(tbls.runs.c.run_id.in_(run_id))
    )

    write_with_retries(engine, stmt)

def set_status_completed(engine: sa.Engine, run_id: int | Sequence[int]):
    """Call after run has had postprocess triggers applied and is safe to archive."""
    run_id = [run_id] if isinstance(run_id, int) else run_id
    
    for rid in run_id:
        logger.debug('Setting Run Status to "COMPLETED": Run ID = %d;', rid)
    
    stmt = (
        sa.update(tbls.runs)
        .values(
            status = 'COMPLETED'
        )
        .where(tbls.runs.c.run_id.in_(run_id))
    )

    write_with_retries(engine, stmt)

def set_status_failed(engine: sa.Engine, job_id: int, message: str | None):
    logger.debug('Setting Run Status to "FAILED": Run ID = %d; Message = %s', job_id, message)
    update_vals = dict(
        status = 'FAILED',
        progress = 0.0
    )
    if message is not None:
        update_vals['progress_message'] = message
    stmt = (
        sa.update(tbls.runs)
        .values(
            **update_vals
        )
        .where(tbls.runs.c.run_id == job_id)
    )

    write_with_retries(engine, stmt)
