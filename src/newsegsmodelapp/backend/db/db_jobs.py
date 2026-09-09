from dataclasses import asdict

import sqlalchemy as sa

from newsegsmodelapp.registers import RunRequest
from newsegsmodelapp.backend.db import tables as tbls

def generate_claim_ticket(engine: sa.Engine, job: RunRequest) -> int:
    """Generate a claim ticket in the results table and return result (job) id."""

    jobval = asdict(job)
    del jobval['run_id']
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
