"""Provides functions for pruning database and files."""

from pathlib import Path
import sqlite3

def prune_old_jobs(db_path: Path, results_store: Path):
    """Delete any result files that are not the latest for a configuration which exists.
    
    1. For all config_id and type in table calculation_results, find latest row with run_status 'SUCCESS'
    2. Find all rows with equal config_id and type with last_updated_timestamp prior to this row
    3. For each of these rows, if result_directory_path exists, check if file exists and delete. If delete successful, set row for deletion from calculation_results.
    4. Delete rows marked for deletion.
    5. List all remaining files in result directory ending with .npy
    6. If any files in this list are not present in list of 'result_directory_path' of calculation_results, attempt deletion
    7. Log any files which were attempted to be deleted but could not be.
    """

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # 1. Identify older rows for the same config_id / type using the database.
        cursor.execute(
            """
            SELECT r.result_id, r.config_id, r.type, r.result_directory_path, r.last_updated_timestamp
            FROM calculation_results AS r
            WHERE EXISTS (
                SELECT 1
                FROM calculation_results AS latest
                WHERE latest.run_status = 'SUCCESS'
                  AND latest.config_id = r.config_id
                  AND (
                        (latest.type = r.type)
                        OR (latest.type IS NULL AND r.type IS NULL)
                      )
                  AND latest.last_updated_timestamp > r.last_updated_timestamp
            )
            """
        )
        rows_to_prune = cursor.fetchall()

        deleted_row_ids: list[int] = []
        for row in rows_to_prune:
            path_text = row['result_directory_path']
            if not path_text:
                continue

            row_path = Path(path_text)
            if not row_path.is_absolute():
                row_path = results_store / row_path

            if row_path.exists():
                try:
                    row_path.unlink()
                    deleted_row_ids.append(row['result_id'])
                    print(f"Pruned old result file: {row_path}")
                except OSError as exc:
                    print(f"Failed to delete old result file {row_path}: {exc}")

        # 4. Delete rows for files that were successfully removed.
        if deleted_row_ids:
            placeholders = ','.join('?' for _ in deleted_row_ids)
            cursor.execute(
                f"DELETE FROM calculation_results WHERE result_id IN ({placeholders})",
                tuple(deleted_row_ids),
            )
            conn.commit()

        # 5. Prune orphan files in the results directory.
        if not results_store.exists() or not results_store.is_dir():
            print(f"Results store does not exist or is not a directory: {results_store}")
            return

        cursor.execute(
            "SELECT result_directory_path FROM calculation_results WHERE result_directory_path IS NOT NULL"
        )
        referenced_paths = {
            Path(row[0]).resolve() if Path(row[0]).is_absolute() else (results_store / Path(row[0])).resolve()
            for row in cursor.fetchall()
        }

        for file_path in results_store.glob('*.npy'):
            try:
                resolved_path = file_path.resolve()
            except OSError:
                resolved_path = file_path

            if resolved_path not in referenced_paths:
                try:
                    file_path.unlink()
                    print(f"Removed orphan result file: {file_path}")
                except OSError as exc:
                    print(f"Failed to remove orphan result file {file_path}: {exc}")

if __name__ == '__main__':
    from config import settings
    DB_PATH = Path(str(settings['DB_PATH']))
    RESULTS_STORE = Path(str(settings['RESULTS_STORE']))
    prune_old_jobs(DB_PATH, RESULTS_STORE)
