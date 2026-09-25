import copy
from dataclasses import asdict
import json

import sqlalchemy as sa

from newsegsmodelapp.registers import RunRequest
from newsegsmodelapp.backend.db import tables as tbls

def generate_claim_ticket(engine: sa.Engine, job: RunRequest) -> int:
    """Generate a claim ticket in the results table and return result (job) id."""

    jobval = asdict(job)
    del jobval['run_id']
    jobval['payload'] = json.dumps(jobval)
    jobval['status'] = 'CALCULATING'
    valid_cols = set(tbls.runs.columns.keys())
    for key in list(jobval.keys()):
        if key not in valid_cols:
            del jobval[key]

    stmt = (
        sa.insert(tbls.runs)
        .values(jobval)
        .returning(tbls.runs.c.run_id)
    )

    with engine.begin() as conn:
        result = conn.execute(stmt)
        row = result.fetchone()
        if row is None:
            raise ValueError(f'Claim ticket not generated for job {job}')
        run_id = row[0]

    job.run_id = run_id
    return run_id

def update_calculation_progress(engine: sa.Engine, job_id: int, step, total, message):
    """Pass progress information into the database."""
    stmt = (
        sa.update(tbls.runs)
        .values(
            progress = step / total,
            progress_message = message
        )
        .where(tbls.runs.c.run_id == job_id)
    )

    with engine.begin() as conn:
        conn.execute(stmt)

def set_cancel_status(engine: sa.Engine, job_id: int, status: bool = True):
    stmt = (
        sa.update(tbls.runs)
        .where(tbls.runs.c.run_id == job_id)
        .values(cancel_requested = status)
    )
    with engine.begin() as conn:
        conn.execute(stmt)

def get_cancel_status(engine: sa.Engine, job_id: int):
    stmt = (
        sa.select(tbls.runs.c.cancel_requested)
        .where(tbls.runs.c.run_id == job_id)
        .limit(1)
    )
    with engine.connect() as conn:
        result = conn.execute(stmt).fetchone()
        return bool(result and result[0])

def set_status_completed(engine: sa.Engine, job_id: int):
    stmt = (
        sa.update(tbls.runs)
        .values(
            status = 'SUCCESS', 
            progress = 1.0,
        )
        .where(tbls.runs.c.run_id == job_id)
    )

    with engine.begin() as conn:
        conn.execute(stmt)

def set_status_failed(engine: sa.Engine, job_id: int, message: str | None):
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

    with engine.begin() as conn:
        conn.execute(stmt)
