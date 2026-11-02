"""
Persistence of per-configuration process staleness.

Each (metamodel, process) pair records two times:
- inputs_changed_ns: the latest input change that is meaningful to the process
- last_run_ns: the start time of the latest completed run of the process

A process is stale for a metamodel when its inputs have changed since its last
run started. Times come from time.time_ns(), so callers in the app and in the
dispatcher workers must share a clock.
"""
import logging
logger = logging.getLogger(__name__)

from collections.abc import Iterable
import time
from typing import Optional

import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import insert

from newsegsmodelapp.backend.db.db import read_transaction, write_transaction
from newsegsmodelapp.backend.db import tables as tbls

PROCESSES = ('deterministic', 'dsa', 'psa', 'optim')

_table = tbls.process_staleness

def _as_list(x: str | Iterable[str]) -> list[str]:
    return [x] if isinstance(x, str) else list(x)

def mark_inputs_changed(
    metamodel_ids: str | Iterable[str],
    processes: str | Iterable[str],
    changed_ns: Optional[int] = None,
    engine: Optional[sa.Engine] = None,
) -> None:
    """Record that inputs meaningful to the processes have changed for the metamodels"""
    metamodel_ids, processes = _as_list(metamodel_ids), _as_list(processes)
    if not metamodel_ids or not processes:
        return
    changed_ns = changed_ns or time.time_ns()

    stmt = insert(_table).values([
        {'metamodel_id': mm_id, 'process': process, 'inputs_changed_ns': changed_ns}
        for mm_id in metamodel_ids for process in processes
    ])
    stmt = stmt.on_conflict_do_update(
        index_elements = [_table.c.metamodel_id, _table.c.process],
        set_ = {'inputs_changed_ns': stmt.excluded.inputs_changed_ns},
    )
    with write_transaction(engine) as conn:
        conn.execute(stmt)

    logger.debug('Marked inputs changed for processes %s on metamodels %s', processes, metamodel_ids)

def record_process_run(
    metamodel_ids: str | Iterable[str],
    process: str,
    started_ns: int,
    engine: Optional[sa.Engine] = None,
) -> None:
    """
    Record a completed run of the process for the metamodels.

    started_ns is when the run read its inputs; changes made while it ran
    remain newer and so keep the process stale. Failures are logged rather
    than raised, so that bookkeeping cannot fail a completed run.
    """
    metamodel_ids = _as_list(metamodel_ids)
    if not metamodel_ids:
        return

    stmt = insert(_table).values([
        {'metamodel_id': mm_id, 'process': process, 'last_run_ns': started_ns}
        for mm_id in metamodel_ids
    ])
    stmt = stmt.on_conflict_do_update(
        index_elements = [_table.c.metamodel_id, _table.c.process],
        # Runs may complete out of order; keep the latest start
        set_ = {'last_run_ns': sa.func.max(sa.func.coalesce(_table.c.last_run_ns, 0), stmt.excluded.last_run_ns)},
    )
    try:
        with write_transaction(engine) as conn:
            conn.execute(stmt)
    except Exception:
        logger.exception('Unable to record %s run for metamodels %s', process, metamodel_ids)
        return

    logger.debug('Recorded %s run started at %d for metamodels %s', process, started_ns, metamodel_ids)

def get_process_times(
    metamodel_ids: Iterable[str],
    processes: Iterable[str] = PROCESSES,
    engine: Optional[sa.Engine] = None,
) -> dict[tuple[str, str], tuple[int | None, int | None]]:
    """(inputs_changed_ns, last_run_ns) keyed by (metamodel_id, process), for recorded pairs only"""
    metamodel_ids, processes = list(metamodel_ids), list(processes)
    if not metamodel_ids or not processes:
        return {}

    stmt = (
        sa.select(_table)
        .where(_table.c.metamodel_id.in_(metamodel_ids))
        .where(_table.c.process.in_(processes))
    )
    with read_transaction(engine) as conn:
        rows = conn.execute(stmt).fetchall()

    return {(x.metamodel_id, x.process): (x.inputs_changed_ns, x.last_run_ns) for x in rows}

def results_exist(
    result_type: str,
    component_config_ids: Iterable[str],
    engine: Optional[sa.Engine] = None,
) -> set[str]:
    """The subset of component_config_ids holding a result of result_type, at any revision"""
    component_config_ids = list(component_config_ids)
    if not component_config_ids:
        return set()

    results = tbls.results
    stmt = (
        sa.select(results.c.component_config_id)
        .where(results.c.result_type == result_type)
        .where(results.c.component_config_id.in_(component_config_ids))
        .distinct()
    )
    with read_transaction(engine) as conn:
        return {x.component_config_id for x in conn.execute(stmt)}
