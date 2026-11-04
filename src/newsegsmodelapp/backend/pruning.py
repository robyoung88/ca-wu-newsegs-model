"""Provides functions for pruning the database and the results store.

`prune_all` runs, in order:

- `prune_orphan_configurations`: configurations (metamodels, energy and finance models, components, variables) that
  nothing live refers to.
- `prune_old_results`: superseded results and their files.
- `prune_old_requests`: finished requests that are no longer relevant, with their runs.
- `prune_old_runs`: runs that have been superseded, or whose request is gone.

Throughout, the statements are SQLAlchemy Core, so that they are not tied to SQLite. With SQLite, a rowid primary key
is reused if the row holding the largest id is deleted, so the row with the largest id of `results`, `requests` and
`runs` is never pruned: ids such as `results.request_id` would otherwise come to name a new, unrelated row.

Results
-------

A result is a row of the `results` table and the file in the results store that its `result_file` names. Each row is the
result of a successful calculation of one type (`result_type`) for one component (`component_config_id`). When a
component is recalculated a new row is added, and the older rows for the same component and type are superseded.

Pruning removes:

1. Rows superseded by a later row for the same component and result type.
2. Rows whose component no longer exists.
3. The files of the removed rows, unless another row still names them (`duplicate_result` and snapshots copy rows,
   and with them the file name).
4. Files in the results store that no row names (orphans), once older than a grace period.

A row is never removed if it is marked `retain`, is the `last_result_id` of a component, or belongs to a request that
has not finished (later requests of a chain read the results of earlier ones by request id). Files named by
`snapshot_results` are never removed.

Configurations
--------------

Projects are the roots. A configuration is live if a live parent refers to it through the foreign-key columns or
junction tables; ids held in payloads are not references, as they are replaced by the columns on reconstruction. Orphans
arise because cascading deletes span several transactions, because upserts do not delete the children they replace, and
because processes (such as optimisation) write copies that are attached to the project only on success. As such a
process may hold unattached configurations, configurations are not pruned while any request is active. Configurations
marked `retain` are kept, and so are their children. Snapshot tables are separate copies and are not touched.

Requests and runs
-----------------

A finished request (`FAILED`, `CANCELLED` or `FULFILLED`) is pruned once older than the retention period if no request
of its chain is still active and either it failed or was cancelled, its project is gone, or no result names its chain
(results are stored under the id of the request that started the chain). Its runs are deleted with it. A run is pruned
once older than the retention period if its request is gone, or if it is not the current run of its request and either
it failed or its request is finished.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
import datetime
import logging
from pathlib import Path
import time
from typing import Optional

import sqlalchemy as sa

from newsegsmodelapp.backend.db import tables as tbls
from newsegsmodelapp.backend.db.db import write_transaction, read_transaction

logger = logging.getLogger(__name__)

# Statuses of a request that may still be followed by steps that read its results.
ACTIVE_REQUEST_STATUSES = ('AWAITING DISPATCH', 'DISPATCHED')
FINISHED_REQUEST_STATUSES = ('FAILED', 'CANCELLED', 'FULFILLED')

# Finished requests and runs younger than this are kept, so that the interface can still poll them.
DEFAULT_REQUEST_RETENTION_DAYS = 7

# Prefix of the files written to the results store by the result provider.
RESULT_FILE_PREFIX = 'res-'

# Orphan files younger than this are kept: the result provider saves the file before inserting its row.
DEFAULT_ORPHAN_GRACE_SECONDS = 24 * 60 * 60

# Number of ids per DELETE statement, to stay within the bound-parameter limits of the backends.
_DELETE_CHUNK_SIZE = 500


@dataclass
class PruneReport:
    """What a pruning run removed, and what it failed to remove."""
    deleted_rows: int = 0
    deleted_files: list[Path] = field(default_factory = list)
    deleted_orphans: list[Path] = field(default_factory = list)
    failed_files: list[Path] = field(default_factory = list)


def _prunable_results_stmt() -> sa.Select:
    """Select the `result_id` and `result_file` of every row of `results` that may be pruned."""
    r = tbls.results
    later = tbls.results.alias('later')
    cc = tbls.component_configs
    req = tbls.requests

    superseded = sa.exists().where(
        later.c.component_config_id == r.c.component_config_id,
        later.c.result_type == r.c.result_type,
        # result_id follows insertion order; created_at does not, as duplicate_result copies it
        later.c.result_id > r.c.result_id,
    )
    config_exists = sa.exists().where(cc.c.id == r.c.component_config_id)
    is_last_result = sa.exists().where(cc.c.last_result_id == r.c.result_id)
    request_active = sa.exists().where(
        req.c.status.in_(ACTIVE_REQUEST_STATUSES),
        sa.or_(
            req.c.request_id == r.c.request_id,
            req.c.trigger_request_id == r.c.request_id,
        ),
    )

    return (
        sa.select(r.c.result_id, r.c.result_file)
        .where(
            sa.or_(superseded, ~config_exists),
            _not_retained(r),
            ~is_last_result,
            ~request_active,
            r.c.result_id < _max_id(r.c.result_id),
        )
    )


def _not_retained(table: sa.Table) -> sa.ColumnElement[bool]:
    return sa.not_(sa.func.coalesce(table.c.retain, sa.false()))


def _max_id(column: sa.Column) -> sa.ScalarSelect:
    """The largest value of an id column, from an alias of its table so that it does not correlate."""
    alias = column.table.alias()
    return sa.select(sa.func.max(alias.c[column.name])).scalar_subquery()


def _delete_ids(conn: sa.Connection, column: sa.Column, ids: list) -> int:
    """Delete the rows of the table of `column` whose `column` is in `ids`, in chunks; return the number deleted."""
    n = 0
    for chunk in _chunks(ids, _DELETE_CHUNK_SIZE):
        n += conn.execute(sa.delete(column.table).where(column.in_(chunk))).rowcount
    return n


def _referenced_file_names(conn: sa.Connection) -> set[str]:
    """Names of the files named by any row of `results` or `snapshot_results`."""
    names: set[str] = set()
    for table in (tbls.results, tbls.snapshot_results):
        rows = conn.execute(
            sa.select(table.c.result_file)
            .where(table.c.result_file.is_not(None))
            .distinct()
        )
        names.update(Path(f).name for (f,) in rows)
    return names


def _chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _delete_file(path: Path, report: PruneReport, *, orphan: bool) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        logger.exception('Failed to delete result file %s', path)
        report.failed_files.append(path)
        return
    if orphan:
        report.deleted_orphans.append(path)
        logger.info('Removed orphan result file: %s', path)
    else:
        report.deleted_files.append(path)
        logger.info('Pruned old result file: %s', path)


def prune_old_results(
    results_store: Path,
    engine: Optional[sa.Engine] = None,
    orphan_grace_seconds: float = DEFAULT_ORPHAN_GRACE_SECONDS,
) -> PruneReport:
    """Delete superseded results, and their files, and orphaned files in the results store.

    See the module docstring for what is and is not pruned.

    Args:
        results_store: Directory of the results store.
        engine: The SQLAlchemy engine, used for writing and reading; `db.get_engine(writer = True)` and
            `db.get_engine()` respectively if None.
        orphan_grace_seconds: Minimum age (by modification time) of a file with no row before it is deleted.

    Returns:
        What was removed, and the files that could not be.
    """
    report = PruneReport()

    # 1-2. Remove the prunable rows, and find which files are still named, in one transaction so that the rows cannot
    # change between selection and deletion.
    with write_transaction(engine) as conn:
        prunable = conn.execute(_prunable_results_stmt()).all()
        report.deleted_rows = _delete_ids(conn, tbls.results.c.result_id, [row.result_id for row in prunable])
        referenced = _referenced_file_names(conn)

    if report.deleted_rows:
        logger.info('Pruned %d superseded or orphaned result rows.', report.deleted_rows)

    # 3. Remove the files of the deleted rows that no remaining row names. The rows are removed first, so a file whose
    # deletion fails is left as an orphan, to be removed on a later run, rather than a row naming a missing file.
    for file_text in {row.result_file for row in prunable if row.result_file}:
        stored = Path(file_text)
        if stored.name in referenced:
            continue
        # The stored path is as it was when the result was saved; fall back to the current store if it has moved.
        path = stored if stored.exists() else results_store / stored.name
        _delete_file(path, report, orphan = False)

    # 4. Remove orphan files. They are matched by name, not full path, so that a moved store is not mistaken for orphans.
    if not results_store.is_dir():
        logger.warning('Results store does not exist or is not a directory: %s', results_store)
        return report

    # Re-read the names, in case results were added since the transaction above.
    with read_transaction(engine) as conn:
        referenced = _referenced_file_names(conn)

    cutoff = time.time() - orphan_grace_seconds
    for path in results_store.glob(f'{RESULT_FILE_PREFIX}*'):
        if path.name in referenced or not path.is_file():
            continue
        try:
            if path.stat().st_mtime > cutoff:
                continue
        except OSError:
            continue
        _delete_file(path, report, orphan = True)

    if report.failed_files:
        logger.warning(
            'Failed to delete %d result files: %s',
            len(report.failed_files), ', '.join(str(p) for p in report.failed_files)
        )
    return report


# -----------------------------------------------------------------------------
# Configurations
# -----------------------------------------------------------------------------

def _any_request_active(conn: sa.Connection) -> bool:
    req = tbls.requests
    return bool(conn.execute(sa.select(sa.exists().where(req.c.status.in_(ACTIVE_REQUEST_STATUSES)))).scalar())


def _unreferenced_ids(conn: sa.Connection, table: sa.Table, referrers: list[sa.Column]) -> list:
    """Ids of the rows of `table`, not marked retain, that no column in `referrers` names."""
    stmt = sa.select(table.c.id).where(_not_retained(table))
    for col in referrers:
        stmt = stmt.where(~sa.exists().where(col == table.c.id))
    return list(conn.execute(stmt).scalars())


def prune_orphan_configurations(engine: Optional[sa.Engine] = None) -> dict[str, int]:
    """Delete configurations that no live project refers to, directly or through their parents.

    Nothing is deleted while any request is active. See the module docstring.

    Args:
        engine: The SQLAlchemy writer engine; `db.get_engine(writer = True)` if None.

    Returns:
        The number of rows deleted, by table; empty if skipped.
    """
    p, mm, em, fm, cc = tbls.projects, tbls.metamodels, tbls.em_configs, tbls.fm_configs, tbls.component_configs
    pm, pv, mv = tbls.project_metamodels, tbls.project_variables, tbls.metamodel_variables
    counts: dict[str, int] = {}

    # Parents are removed before children, in one transaction, so that each step sees the deletions of the last.
    with write_transaction(engine) as conn:
        if _any_request_active(conn):
            logger.warning('Requests are active; orphan configurations not pruned.')
            return counts

        # Junction rows of projects that are gone
        for jct in (pm, pv):
            ids = list(conn.execute(
                sa.select(jct.c.project_id).where(~sa.exists().where(p.c.id == jct.c.project_id)).distinct()
            ).scalars())
            counts[jct.name] = _delete_ids(conn, jct.c.project_id, ids)

        mm_ids = _unreferenced_ids(conn, mm, [pm.c.metamodel_id, p.c.focussed_metamodel_id])
        # Junction rows of these metamodels, and of metamodels that were already gone
        dangling = list(conn.execute(
            sa.select(mv.c.metamodel_id).where(~sa.exists().where(mm.c.id == mv.c.metamodel_id)).distinct()
        ).scalars())
        counts[mv.name] = _delete_ids(conn, mv.c.metamodel_id, mm_ids + dangling)
        counts[mm.name] = _delete_ids(conn, mm.c.id, mm_ids)

        staleness = tbls.process_staleness
        stale_ids = list(conn.execute(
            sa.select(staleness.c.metamodel_id)
            .where(~sa.exists().where(mm.c.id == staleness.c.metamodel_id))
            .distinct()
        ).scalars())
        counts[staleness.name] = _delete_ids(conn, staleness.c.metamodel_id, stale_ids)

        counts[em.name] = _delete_ids(conn, em.c.id, _unreferenced_ids(conn, em, [mm.c.em_config_id]))
        counts[fm.name] = _delete_ids(conn, fm.c.id, _unreferenced_ids(conn, fm, [mm.c.fm_config_id]))

        cc_ids = _unreferenced_ids(conn, cc, [
            em.c.grid_config_id, em.c.generation_config_id, em.c.cs_config_id,
            em.c.modeldata_config_id, em.c.table_config_id,
            fm.c.financedata_config_id, fm.c.table_config_id,
            mm.c.table_config_id, mm.c.optim_config_id,
            p.c.dsa_component_config_id, p.c.psa_component_config_id, p.c.table_config_id,
        ])
        # Their results reference them; the rows go here, and the files go as orphans in prune_old_results.
        _delete_ids(conn, tbls.results.c.component_config_id, cc_ids)
        counts[cc.name] = _delete_ids(conn, cc.c.id, cc_ids)

        var = tbls.variable_configs
        counts[var.name] = _delete_ids(
            conn, var.c.id, _unreferenced_ids(conn, var, [pv.c.variable_config_id, mv.c.variable_config_id])
        )

    deleted = {k: v for k, v in counts.items() if v}
    if deleted:
        logger.info('Pruned orphan configurations: %s', deleted)
    return counts


# -----------------------------------------------------------------------------
# Requests and runs
# -----------------------------------------------------------------------------

def _chain_root(req: sa.Table | sa.Alias) -> sa.ColumnElement:
    """Id of the request that started the chain of a request, under which the chain's results are stored."""
    return sa.case(
        (sa.or_(req.c.trigger_request_id.is_(None), req.c.trigger_request_id == -1), req.c.request_id),
        else_ = req.c.trigger_request_id,
    )


def _run_time(run: sa.Table | sa.Alias) -> sa.ColumnElement:
    return sa.func.coalesce(run.c.modified_at, run.c.created_at)


def _cutoff(retention_days: float) -> datetime.datetime:
    # runs.modified_at is written with datetime.datetime.now
    return datetime.datetime.now() - datetime.timedelta(days = retention_days)


def _prunable_requests_stmt(cutoff: datetime.datetime) -> sa.Select:
    r = tbls.requests
    other = tbls.requests.alias('other')
    run = tbls.runs
    res = tbls.results
    p = tbls.projects

    chain_active = sa.exists().where(
        other.c.status.in_(ACTIVE_REQUEST_STATUSES),
        _chain_root(other) == _chain_root(r),
    )
    irrelevant = sa.or_(
        r.c.status.in_(('FAILED', 'CANCELLED')),
        ~sa.exists().where(p.c.id == r.c.project_id),
        ~sa.exists().where(res.c.request_id == _chain_root(r)),
    )
    # Requests have no timestamp: one is old if a run of it, or of a later request, ended before the cutoff,
    # and no run of it ended after.
    old = sa.and_(
        sa.exists().where(run.c.request_id >= r.c.request_id, _run_time(run) < cutoff),
        ~sa.exists().where(run.c.request_id == r.c.request_id, _run_time(run) >= cutoff),
    )
    return (
        sa.select(r.c.request_id)
        .where(
            r.c.status.in_(FINISHED_REQUEST_STATUSES),
            ~chain_active,
            irrelevant,
            old,
            r.c.request_id < _max_id(r.c.request_id),
        )
    )


def prune_old_requests(
    engine: Optional[sa.Engine] = None,
    retention_days: float = DEFAULT_REQUEST_RETENTION_DAYS,
) -> int:
    """Delete finished requests that are no longer relevant, with their runs. See the module docstring.

    Args:
        engine: The SQLAlchemy writer engine; `db.get_engine(writer = True)` if None.
        retention_days: Minimum age of a request before it is deleted.

    Returns:
        The number of requests deleted.
    """
    with write_transaction(engine) as conn:
        ids = list(conn.execute(_prunable_requests_stmt(_cutoff(retention_days))).scalars())
        _delete_ids(conn, tbls.runs.c.request_id, ids)
        n = _delete_ids(conn, tbls.requests.c.request_id, ids)
    if n:
        logger.info('Pruned %d old requests.', n)
    return n


def _prunable_runs_stmt(cutoff: datetime.datetime) -> sa.Select:
    run = tbls.runs
    r = tbls.requests
    return (
        sa.select(run.c.run_id)
        .select_from(run.outerjoin(r, r.c.request_id == run.c.request_id))
        .where(
            _run_time(run) < cutoff,
            run.c.run_id < _max_id(run.c.run_id),
            sa.or_(
                r.c.request_id.is_(None),
                sa.and_(
                    sa.func.coalesce(r.c.run_id, -1) != run.c.run_id,
                    # A run that has not failed may be reclaimed by its active request (generate_claim_ticket)
                    sa.or_(run.c.status == 'FAILED', r.c.status.in_(FINISHED_REQUEST_STATUSES)),
                ),
            ),
        )
    )


def prune_old_runs(
    engine: Optional[sa.Engine] = None,
    retention_days: float = DEFAULT_REQUEST_RETENTION_DAYS,
) -> int:
    """Delete runs that have been superseded, or whose request is gone. See the module docstring.

    Args:
        engine: The SQLAlchemy writer engine; `db.get_engine(writer = True)` if None.
        retention_days: Minimum age of a run before it is deleted.

    Returns:
        The number of runs deleted.
    """
    with write_transaction(engine) as conn:
        ids = list(conn.execute(_prunable_runs_stmt(_cutoff(retention_days))).scalars())
        n = _delete_ids(conn, tbls.runs.c.run_id, ids)
    if n:
        logger.info('Pruned %d old runs.', n)
    return n


# -----------------------------------------------------------------------------
# All
# -----------------------------------------------------------------------------

def prune_all(
    results_store: Path,
    engine: Optional[sa.Engine] = None,
    retention_days: float = DEFAULT_REQUEST_RETENTION_DAYS,
) -> None:
    """Run every pruning step, in an order in which each can act on what the previous ones removed.

    Configurations go first, as their removal orphans results; results before requests, as a request is kept while
    results name it. A failing step is logged and does not stop the others.

    Args:
        results_store: Directory of the results store.
        engine: The SQLAlchemy engine; those of `db.get_engine` if None.
        retention_days: Minimum age of a request or run before it is deleted.
    """
    steps = (
        ('configurations', lambda: prune_orphan_configurations(engine)),
        ('results', lambda: prune_old_results(results_store, engine)),
        ('requests', lambda: prune_old_requests(engine, retention_days)),
        ('runs', lambda: prune_old_runs(engine, retention_days)),
    )
    for name, step in steps:
        try:
            step()
        except Exception:
            logger.exception('Pruning of %s failed.', name)


if __name__ == '__main__':
    from config import settings
    logging.basicConfig(level = logging.INFO)
    prune_all(Path(str(settings['RESULTS_STORE'])))
