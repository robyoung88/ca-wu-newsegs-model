"""Provides functions for pruning old results from the database and the results store.

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

The statements are SQLAlchemy Core, so that they are not tied to SQLite.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field
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
            sa.not_(sa.func.coalesce(r.c.retain, sa.false())),
            ~is_last_result,
            ~request_active,
        )
    )


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
        ids = [row.result_id for row in prunable]
        for chunk in _chunks(ids, _DELETE_CHUNK_SIZE):
            conn.execute(sa.delete(tbls.results).where(tbls.results.c.result_id.in_(chunk)))
        report.deleted_rows = len(ids)
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


if __name__ == '__main__':
    from config import settings
    logging.basicConfig(level = logging.INFO)
    prune_old_results(Path(str(settings['RESULTS_STORE'])))
